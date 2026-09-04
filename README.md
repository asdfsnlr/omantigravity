# OmaAntigravity — Antigravity CLI Usage & Quota Plugin for Omarchy

An Omarchy shell bar widget and panel plugin that monitors and displays **Google Antigravity CLI** (`agy`) limits, 5-hour rolling windows, weekly quotas, and active model status in real time.

## Benefits

- **At-a-Glance Quota in Your Bar**: See remaining quota directly in your status bar (`󰒋 73%`). Quota percentage adapts automatically or tracks the most limiting constraint.
- **Model Group Breakdown**: Clean cards detailing each model family:
  - **Gemini Models**: Gemini Flash, Gemini Pro
  - **Claude and GPT models**: Claude Opus, Claude Sonnet, GPT-OSS
- **5-Hour & Weekly Windows**: Clear progress meters for both the 5-hour burst smoothing window and the weekly tier quota.
- **Reset Countdowns**: Real-time countdowns showing when limits refresh (e.g. `Resets in 4h 55m` or `Resets in 5d 19h`).
- **Active Model Detection**: Displays current active model (e.g. `Gemini 3.8 Flash (Medium)`) and reasoning effort tier.
- **Urgent & Warning Thresholds**: Dynamic color cues (normal foreground, warning yellow under 30%, urgent red under 15%).
- **Instant Launch via Local Cache**: Loads immediately from cache without delay, refreshing fresh data in the background.
- **Keyboard-First Controls**: Full keyboard shortcuts (`[R]` to force refresh, `[Esc]` to close).

---

## Installation

### 1. Symlink or copy to Omarchy plugins directory

For development or direct usage:

```bash
mkdir -p ~/.config/omarchy/plugins
ln -s "/home/slanger/source/repos/omarchy-plugins/omaantigravity" ~/.config/omarchy/plugins/omaantigravity
```

### 2. Enable in Omarchy status bar

Add the plugin to your desired section (e.g., `right`):

```bash
omarchy plugin enable omaantigravity --section right
```

Or edit `~/.config/omarchy/shell.json` directly under `bar.layout.right`:

```json
{
  "id": "omaantigravity",
  "showPercentageInBar": true,
  "pollIntervalSec": 300,
  "barMetric": "lowest"
}
```

Omarchy will hot-reload automatically on save.

---

## Configuration Options

Settings can be customized directly in the panel UI (clicking the group chips or any limit row), via `omarchy bar set`, or in `~/.config/omarchy/shell.json`:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `pollIntervalSec` | integer | `300` | Background refresh interval in seconds (30s – 3600s) |
| `showPercentageInBar` | boolean | `true` | Display remaining percentage next to the bar icon |
| `barMetric` | enum | `"gemini"` | Quota group or limit to show in the bar: `gemini`, `3p`, `lowest`, `gemini-5h`, `gemini-weekly`, `3p-5h`, `3p-weekly` |
| `barIcon` | string | `"λ"` | Icon glyph displayed on the bar |

### Configure via CLI

```bash
# Show Gemini's available limit (default)
omarchy bar set omaantigravity barMetric gemini

# Show Claude and GPT models available limit
omarchy bar set omaantigravity barMetric 3p

# Show the lowest remaining quota overall
omarchy bar set omaantigravity barMetric lowest

# Lock to a specific window
omarchy bar set omaantigravity barMetric gemini-5h
omarchy bar set omaantigravity barMetric gemini-weekly
```

---

## Panel Controls & Shortcuts

| Action | Shortcut / Trigger |
| --- | --- |
| **Open / Close Panel** | Click bar icon or <kbd>Esc</kbd> |
| **Force Refresh** | Right-click / Middle-click bar button or press <kbd>r</kbd> / <kbd>R</kbd> in panel |
| **IPC Controls** | `omarchy-shell omaantigravity refresh`, `open`, `close`, `toggle` |

---

## CLI Script Usage

The helper script `scripts/fetch_usage.py` can also be run directly from terminal:

```bash
# Return cached data if fresh, or query agy
./scripts/fetch_usage.py --cached

# Force a real-time fetch from agy
./scripts/fetch_usage.py --force

# Return current cache immediately
./scripts/fetch_usage.py --cached-only
```

---

## License

MIT
