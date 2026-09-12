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
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

# Hard cap on combined stdout/stderr read from the `agy` CLI, to bound memory
# use if the process is hostile or wedged and keeps producing output.
MAX_OUTPUT_BYTES = 2 * 1024 * 1024  # 2 MiB

# Hard cap on the cached usage JSON we will read back, so a huge or
# never-ending cache file (e.g. a FIFO) can't exhaust the helper's memory.
CACHE_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB

# Only binaries resolving (after following symlinks) into one of these
# directories are trusted to run as `agy`. This intentionally excludes the
# rest of PATH, since an arbitrary PATH entry may be user- or world-writable.
_TRUSTED_AGY_DIRS = [
    Path.home() / ".local/share/mise/installs/antigravity-cli",
    Path.home() / ".local/share/mise/shims",
    Path.home() / ".gemini/antigravity-cli/bin",
    Path("/usr/local/bin"),
    Path("/usr/bin"),
    Path.home() / ".local/bin",
]


def get_cache_dir() -> Path:
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "omarchy"
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(cache_dir, 0o700)
    except OSError:
        pass
    return cache_dir


def get_cache_path() -> Path:
    return get_cache_dir() / "antigravity-usage.json"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _verify_trusted_binary(candidate: Path) -> Optional[str]:
    """Resolve `candidate` and verify it is safe to execute as `agy`.

    Requires: resolves to a real regular file, owned by root or the current
    user, not group/other writable, executable, and located inside one of
    the fixed trusted install directories (never an arbitrary PATH entry).
    """
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    try:
        st = resolved.stat()
    except OSError:
        return None

    if not stat.S_ISREG(st.st_mode):
        return None
    if st.st_uid not in (0, os.getuid()):
        return None
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None
    if not os.access(resolved, os.X_OK):
        return None

    for trusted_dir in _TRUSTED_AGY_DIRS:
        try:
            resolved_dir = trusted_dir.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if _is_within(resolved, resolved_dir):
            return str(resolved)

    return None


def find_agy_binary() -> Optional[str]:
    seen = set()
    candidates = []

    which_agy = shutil.which("agy")
    if which_agy:
        candidates.append(Path(which_agy))

    candidates.extend(
        [
            Path.home() / ".local/share/mise/installs/antigravity-cli/latest/agy",
            Path.home() / ".local/share/mise/shims/agy",
            Path.home() / ".gemini/antigravity-cli/bin/agy",
            Path("/usr/local/bin/agy"),
            Path("/usr/bin/agy"),
            Path.home() / ".local/bin/agy",
        ]
    )

    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        verified = _verify_trusted_binary(candidate)
        if verified:
            return verified

    return None


def _read_capped(proc: subprocess.Popen, timeout: float, max_bytes: int) -> tuple[bytes, bool]:
    """Read proc.stdout/stderr with a byte cap and overall deadline.

    Returns (stdout_bytes, truncated). Never raises on timeout/overflow;
    the caller is responsible for killing the process group afterwards.
    """
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
    sel.register(proc.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    open_streams = {"stdout", "stderr"}
    deadline = time.monotonic() + timeout
    truncated = False

    while open_streams:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            truncated = True
            break
        for key, _ in sel.select(timeout=min(remaining, 0.5)):
            name = key.data
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except OSError:
                chunk = b""
            if not chunk:
                sel.unregister(key.fileobj)
                open_streams.discard(name)
                continue
            buffers[name].extend(chunk)
            if len(buffers[name]) > max_bytes:
                truncated = True
                open_streams.clear()
                break

    return bytes(buffers["stdout"][:max_bytes]), truncated


def run_agy_command(
    agy_bin: str, cmd: str, timeout: int = 15, max_bytes: int = MAX_OUTPUT_BYTES
) -> Optional[Dict[str, Any]]:
    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            [agy_bin, "-p", cmd, "--output-format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # own process group, for clean teardown
        )
        stdout_b, truncated = _read_capped(proc, timeout, max_bytes)
        if truncated:
            return None
        try:
            returncode = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return None
        if returncode == 0 and stdout_b.strip():
            return json.loads(stdout_b.decode("utf-8", errors="replace"))
    except Exception:
        pass
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
    return None


def read_cache(cache_file: Path) -> Optional[Dict[str, Any]]:
    """Read the cache file without following symlinks, with a size cap."""
    try:
        fd = os.open(cache_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        if st.st_uid != os.getuid():
            return None
        if st.st_size > CACHE_MAX_BYTES:
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = -1  # ownership transferred to the file object
            return json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    finally:
        if fd != -1:
            os.close(fd)


def write_cache(cache_file: Path, data: Dict[str, Any]) -> None:
    """Write the cache atomically via an exclusive, randomly named temp file
    in the same directory, so a predictable-path symlink attack can't
    redirect the write."""
    cache_dir = cache_file.parent
    fd, tmp_path = tempfile.mkstemp(prefix=".antigravity-usage-", suffix=".tmp", dir=cache_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, cache_file)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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


def format_exact_time(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        clean_iso = iso_str.replace("Z", "+00:00")
        target_dt = datetime.fromisoformat(clean_iso)
        local_dt = target_dt.astimezone()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_abbr = months[local_dt.month - 1]
        time_part = local_dt.strftime("%H:%M")
        return f"{local_dt.day}, {month_abbr} at {time_part}"
    except Exception:
        return ""


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
            exact_reset = format_exact_time(reset_time)

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
                "reset_exact": exact_reset,
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
    if args.cached or args.cached_only:
        cached_data = read_cache(cache_file)
        if cached_data is not None:
            cached_ts = cached_data.get("timestamp", 0)
            age = datetime.now().timestamp() - cached_ts
            if args.cached_only or (args.cached and age < args.max_age and not args.force):
                print(json.dumps(cached_data, indent=2))
                return

    agy_bin = find_agy_binary()
    if not agy_bin:
        # Fallback to cache if available
        cached = read_cache(cache_file)
        if cached is not None:
            cached["stale"] = True
            cached["warning"] = "Antigravity binary 'agy' not found; displaying cached data"
            print(json.dumps(cached, indent=2))
            return

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
            cached = read_cache(cache_file)
            if cached is not None:
                cached["stale"] = True
                print(json.dumps(cached, indent=2))
                return

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
        write_cache(cache_file, result)

        print(json.dumps(result, indent=2))

    except Exception as e:
        cached = read_cache(cache_file)
        if cached is not None:
            cached["stale"] = True
            print(json.dumps(cached, indent=2))
            return

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
