# Omantigravity — Antigravity CLI Usage & Quota Plugin for Omarchy

An Omarchy shell bar widget and popup panel plugin that monitors and displays **Google Antigravity CLI** (`agy`) limits, 5-hour rolling windows, weekly quotas, and active model status in real time.

> **Disclaimer:** *This project is an unofficial community plugin for Omarchy. It is not developed by, endorsed by, affiliated with, or in any way officially connected to [Google LLC](https://google.com), [Anthropic PBC](https://anthropic.com), [OpenAI](https://openai.com), or their respective subsidiaries. All product names, logos, brands, trademarks, and registered trademarks (including Google, Google Antigravity, Gemini, Anthropic, Claude, OpenAI, and GPT) are the property of their respective owners and are used solely for identification, reference, and interoperability purposes.*

<p align="center">
  <img src="preview.png" alt="Omantigravity Preview" />
</p>

## Benefits & Features

- **At-a-Glance Quota in Your Bar**: Real-time remaining quota displayed directly on your status bar (`λ 86%`). Automatically turns urgent red with an alert glyph (`󰀨`) when quota is low.
- **Interactive Metric Selector**: Minimalist rectangular chips in the panel to select which metric the bar tracks:
  - **Gemini**: Shows the most constrained limit for Gemini models (Flash, Pro).
  - **Claude & GPT**: Shows the most constrained limit for third-party models (Opus, Sonnet, GPT-OSS).
  - **Lowest**: Dynamically tracks the absolute lowest limit across all groups and windows.
- **Pin Any Specific Limit**: Click any individual 5-hour or weekly progress bar in the panel to pin that exact limit to the status bar (indicated by a clean `󰄬 On bar` badge).
- **Customizable Alert System**:
  - Configurable alert threshold percentage (default: **20%** remaining).
  - Prominent in-panel alert banner highlighting critical quotas and their exact reset countdown.
  - Native desktop notifications via `notify-send` when limits drop to or below your threshold.
  - In-panel quick selectors (`[10%]`, `[15%]`, `[20%]`, `[25%]`, `[30%]`) and a mute/unmute toggle (`[󰂚 Notify]` / `[󰂛 Muted]`).
- **Antigravity Branding & Active Model**:
  - Displays the clean Lambda (`λ`) glyph, current active model, and reasoning effort tier (e.g. `Gemini 3.8 Flash · Reasoning: Medium`).
- **Compact Non-Scroll Design**: Fully fitted layout tailored to Omarchy's design language (`Style.cornerRadius`, no scrollbars).
- **Instant Launch via Local Cache**: Loads immediately from local cache (`~/.cache/omarchy/antigravity-usage.json`) without lag, refreshing fresh data in the background.
- **Full Keyboard Navigation**: Press <kbd>R</kbd> in the panel to force refresh, <kbd>Esc</kbd> to close.

---

## Requirements

Before using the plugin, ensure the following dependencies and tools are available on your system:

- **Omarchy Linux**: Quickshell-powered desktop shell with third-party plugin support.
- **Google Antigravity CLI (`agy`)**:
  - The `agy` executable must be installed and accessible in your `PATH` (or standard paths such as `~/.local/share/mise/shims/agy`, `~/.gemini/antigravity-cli/bin/agy`, or `/usr/bin/agy`).
  - You must have logged in / authenticated at least once so `agy` can query your usage limits.
- **Python 3**:
  - `python3` (3.8+) for running the background usage fetcher and cache engine (`scripts/fetch_usage.py`). Only uses Python standard library modules; no external `pip` dependencies are needed.
- **Desktop Notifications** *(Optional)*:
  - `libnotify` (`notify-send`) for system notification alerts when quota drops below your configured threshold.
- **Nerd Font**:
  - Any Nerd Font (e.g. `JetBrainsMono Nerd Font`, default in Omarchy) for iconography and status indicators.

---

## Installation

Add and enable the plugin directly in Omarchy using the official plugin manager:

```bash
omarchy plugin add https://github.com/slanger/omantigravity.git --enable
```

If you wish to position it in a specific bar section (e.g. `right`):

```bash
omarchy plugin enable omantigravity --section right
```

To update the plugin to the latest version at any time:

```bash
omarchy plugin update omantigravity
```

---

## Configuration Options

Settings can be toggled directly in the panel UI, configured via `omarchy bar set`, or specified in `~/.config/omarchy/shell.json`:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `barMetric` | enum | `"gemini"` | Quota limit to show on the bar: `gemini`, `3p`, `lowest`, `gemini-5h`, `gemini-weekly`, `3p-5h`, `3p-weekly` |
| `alertThresholdPct` | integer | `20` | Threshold percentage (5% – 50%) for low quota alerts |
| `enableNotifications` | boolean | `true` | Send desktop notifications via `notify-send` when quota is critical |
| `showPercentageInBar` | boolean | `true` | Display remaining percentage next to the bar icon |
| `pollIntervalSec` | integer | `300` | Background refresh interval in seconds (30s – 3600s) |
| `barIcon` | string | `"λ"` | Icon glyph displayed on the bar |

### CLI Configuration Examples

```bash
# Set metric to Gemini models (default)
omarchy bar set omantigravity barMetric gemini

# Set metric to Claude and GPT models
omarchy bar set omantigravity barMetric 3p

# Set metric to overall lowest remaining quota
omarchy bar set omantigravity barMetric lowest

# Pin to a specific window
omarchy bar set omantigravity barMetric gemini-5h
omarchy bar set omantigravity barMetric gemini-weekly

# Change the critical alert threshold (e.g. to 25%)
omarchy bar set omantigravity alertThresholdPct 25 --json

# Toggle desktop notifications
omarchy bar set omantigravity enableNotifications false --json

# Change poll interval (e.g. every 2 minutes)
omarchy bar set omantigravity pollIntervalSec 120 --json
```

---

## Panel Controls & Shortcuts

| Action | Shortcut / Trigger |
| --- | --- |
| **Open / Close Panel** | Left-click bar widget or press <kbd>Esc</kbd> |
| **Force Fresh Refresh** | Right-click / Middle-click bar widget or press <kbd>R</kbd> inside panel |
| **Switch Active Group** | Click `[Gemini]`, `[Claude & GPT]`, or `[Lowest]` chips |
| **Pin Specific Limit** | Click any progress bar row in the panel |
| **Set Alert Threshold** | Click `[10%]`, `[15%]`, `[20%]`, `[25%]`, or `[30%]` chips |
| **Toggle Notifications** | Click `[󰂚 Notify]` / `[󰂛 Muted]` button |
| **IPC Controls** | `omarchy-shell omantigravity toggle`, `open`, `close`, `refresh`, `state` |

---

## CLI Script Usage

The backend query engine `scripts/fetch_usage.py` can also be run standalone:

```bash
# Return cached data if recent (<300s), otherwise fetch fresh from agy
./scripts/fetch_usage.py --cached

# Force a fresh real-time fetch from agy
./scripts/fetch_usage.py --force

# Return current cache immediately without waiting
./scripts/fetch_usage.py --cached-only
```

---

## Plugin Management

```bash
# List all discovered plugins and their status
omarchy plugin list

# Validate plugin manifest and schema
omarchy plugin validate ~/.config/omarchy/plugins/omantigravity

# Disable plugin from status bar
omarchy plugin disable omantigravity

# Remove plugin
omarchy plugin remove omantigravity
```

---

## License

MIT
