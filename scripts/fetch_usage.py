#!/usr/bin/env python3
"""
Fetch, parse, and cache Antigravity CLI usage limits and quota information.
Designed for the Omarchy Omantigravity bar widget & panel plugin.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional


def get_cache_path() -> Path:
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "omarchy"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "antigravity-usage.json"


def find_agy_binary() -> Optional[str]:
    # Check PATH first
    agy = shutil.which("agy")
    if agy and os.path.isfile(agy) and os.access(agy, os.X_OK):
        return agy

    # Common installation locations
    candidates = [
        Path.home() / ".local/share/mise/installs/antigravity-cli/latest/agy",
        Path.home() / ".local/share/mise/shims/agy",
        Path.home() / ".gemini/antigravity-cli/bin/agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
        Path.home() / ".local/bin/agy",
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def run_agy_command(agy_bin: str, cmd: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    try:
        proc = subprocess.run(
            [agy_bin, "-p", cmd, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return None


def format_countdown(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        clean_iso = iso_str.replace("Z", "+00:00")
        target_dt = datetime.fromisoformat(clean_iso)
        now = datetime.now(timezone.utc)
        diff = target_dt - now
        total_seconds = int(diff.total_seconds())
        if total_seconds <= 0:
            return "ready"

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{max(1, minutes)}m"
    except Exception:
        return ""


def format_local_time(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        clean_iso = iso_str.replace("Z", "+00:00")
        target_dt = datetime.fromisoformat(clean_iso)
        local_dt = target_dt.astimezone()
        return local_dt.strftime("%b %d, %H:%M")
    except Exception:
        return iso_str


def parse_usage_data(
    usage_raw: Dict[str, Any],
    model_raw: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    cmd_data = usage_raw.get("command", {}).get("data", {})
    raw_groups = cmd_data.get("groups", [])
    general_desc = cmd_data.get("description", "")

    parsed_groups: List[Dict[str, Any]] = []
    lowest_pct = 100
    lowest_bucket_name = ""
    lowest_window = ""

    summary_lines = []

    for grp in raw_groups:
        grp_name = grp.get("name", "Unknown Group")
        grp_desc = grp.get("description", "")
        raw_buckets = grp.get("buckets", [])

        # Assign friendly icon
        is_gemini = "gemini" in grp_name.lower()
        grp_icon = "󰘧" if is_gemini else "󰚩"

        parsed_buckets = []
        bucket_summaries = []

        for b in raw_buckets:
            b_id = b.get("id", "")
            b_name = b.get("name", "Limit")
            b_window = b.get("window", "")
            b_desc = b.get("description", "")
            rem_frac = float(b.get("remaining_fraction", 1.0))
            rem_pct = max(0, min(100, int(round(rem_frac * 100))))
            used_pct = 100 - rem_pct
            reset_time = b.get("reset_time", "")
            countdown = format_countdown(reset_time)
            local_reset = format_local_time(reset_time)

            if rem_pct < lowest_pct:
                lowest_pct = rem_pct
                lowest_bucket_name = f"{grp_name} ({b_window})"
                lowest_window = b_window

            # Clean friendly window title
            window_title = "5-Hour Window" if b_window == "5h" else ("Weekly Window" if b_window == "weekly" else b_window.capitalize())

            bucket_obj = {
                "id": b_id,
                "name": b_name,
                "window": b_window,
                "window_title": window_title,
                "description": b_desc,
                "remaining_fraction": rem_frac,
                "remaining_pct": rem_pct,
                "used_pct": used_pct,
                "reset_time": reset_time,
                "reset_countdown": countdown,
                "reset_local": local_reset,
                "alarming": rem_pct <= 15,
                "warning": 15 < rem_pct <= 30,
            }
            parsed_buckets.append(bucket_obj)
            bucket_summaries.append(f"{b_window}: {rem_pct}%")

        if bucket_summaries:
            short_name = "Gemini" if is_gemini else "Claude/GPT"
            summary_lines.append(f"{short_name}: {' · '.join(bucket_summaries)}")

        parsed_groups.append({
            "name": grp_name,
            "description": grp_desc,
            "icon": grp_icon,
            "is_gemini": is_gemini,
            "buckets": parsed_buckets,
        })

    # Active model information
    active_model = None
    if model_raw and "command" in model_raw:
        m_data = model_raw.get("command", {}).get("data", {})
        if m_data:
            active_model = {
                "id": m_data.get("id", ""),
                "label": m_data.get("label", ""),
                "effort": m_data.get("effort", ""),
            }

    tooltip = "Antigravity Quota\n" + ("\n".join(summary_lines) if summary_lines else "No limits reported")

    return {
        "status": "ok",
        "last_updated": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(datetime.now().timestamp()),
        "description": general_desc,
        "overall": {
            "lowest_remaining_pct": lowest_pct,
            "lowest_bucket_name": lowest_bucket_name,
            "lowest_window": lowest_window,
            "alarming": lowest_pct <= 15,
            "warning": 15 < lowest_pct <= 30,
        },
        "active_model": active_model,
        "groups": parsed_groups,
        "tooltip": tooltip,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Antigravity usage limits")
    parser.add_argument("--cached", action="store_true", help="Return cache if recent (<300s)")
    parser.add_argument("--cached-only", action="store_true", help="Return cache immediately if exists")
    parser.add_argument("--force", action="store_true", help="Force fresh fetch from agy")
    parser.add_argument("--max-age", type=int, default=300, help="Max cache age in seconds (default 300)")
    args = parser.parse_args()

    cache_file = get_cache_path()

    # If --cached-only or --cached requested, check cache
    if (args.cached or args.cached_only) and cache_file.is_file():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            cached_ts = cached_data.get("timestamp", 0)
            age = datetime.now().timestamp() - cached_ts
            if args.cached_only or (args.cached and age < args.max_age and not args.force):
                print(json.dumps(cached_data, indent=2))
                return
        except Exception:
            pass

    agy_bin = find_agy_binary()
    if not agy_bin:
        # Fallback to cache if available
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached["stale"] = True
                cached["warning"] = "Antigravity binary 'agy' not found; displaying cached data"
                print(json.dumps(cached, indent=2))
                return
            except Exception:
                pass

        err_resp = {
            "status": "error",
            "error": "Antigravity binary ('agy') not found in PATH or standard locations.",
            "groups": [],
            "overall": {"lowest_remaining_pct": 0, "alarming": False, "warning": False},
            "tooltip": "Antigravity CLI not found",
        }
        print(json.dumps(err_resp, indent=2))
        return

    # Run /usage and /model in parallel
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_usage = executor.submit(run_agy_command, agy_bin, "/usage")
            fut_model = executor.submit(run_agy_command, agy_bin, "/model")
            usage_res = fut_usage.result()
            model_res = fut_model.result()

        if not usage_res or usage_res.get("status") != "SUCCESS":
            # Attempt to use stale cache
            if cache_file.is_file():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    cached["stale"] = True
                    print(json.dumps(cached, indent=2))
                    return
                except Exception:
                    pass

            err_resp = {
                "status": "error",
                "error": "Failed to get usage limits from agy.",
                "groups": [],
                "overall": {"lowest_remaining_pct": 0, "alarming": False, "warning": False},
                "tooltip": "Failed to get Antigravity usage",
            }
            print(json.dumps(err_resp, indent=2))
            return

        result = parse_usage_data(usage_res, model_res)

        # Save to cache
        try:
            temp_file = cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            temp_file.replace(cache_file)
        except Exception:
            pass

        print(json.dumps(result, indent=2))

    except Exception as e:
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached["stale"] = True
                print(json.dumps(cached, indent=2))
                return
            except Exception:
                pass

        err_resp = {
            "status": "error",
            "error": str(e),
            "groups": [],
            "overall": {"lowest_remaining_pct": 0, "alarming": False, "warning": False},
            "tooltip": f"Error: {e}",
        }
        print(json.dumps(err_resp, indent=2))


if __name__ == "__main__":
    main()
