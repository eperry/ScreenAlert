# EPerry's Screen Alert Management System

ScreenAlert is a Windows desktop monitoring tool that watches selected regions of application windows for visual changes and alerts you in real time. It is built for situations where you need to track activity across multiple windows simultaneously — without automating or interacting with those windows.

ScreenAlert observes, compares, and reports. It does not click, type, or automate anything in the monitored applications.

---

## Screenshots

Settings dialog

![ScreenAlert Settings](docs/images/screenalert-settings.png)

Window selection dialog

![Select Window to Monitor](docs/images/select-window-dialog.png)

Main dashboard with active region

![Main Dashboard](docs/images/main-dashboard.png)

---

## Installation (Windows)

**Requirements:** Python 3.9 or higher must be installed and on your PATH.

Run the installer once to set up a virtual environment and install all dependencies:

```bat
install.bat
```

This will:
- Detect your Python installation (3.9+ required)
- Create a `.venv` virtual environment in the project directory
- Install all required packages from `screenalert_requirements.txt`

Once installed, launch the app with:

```bat
launch_ScreenAlert.bat
```

The launcher automatically uses the virtual environment and starts the app in the background. Only one instance can run at a time — duplicate launches are silently ignored.

---

## Features

### Multi-Window Monitoring
- Add any number of open application windows to the monitor list
- Each window is tracked by persistent identity metadata, so monitoring survives window moves, resizes, and minimizes
- Detects when a monitored window is closed or lost and notifies you

### Region-Based Change Detection
- Draw one or more rectangular monitoring regions on any watched window using a visual drag-to-select editor
- Regions can be moved and resized after creation using drag handles
- Each region is monitored independently with its own settings
- Two detection methods available:
  - **SSIM** (Structural Similarity Index) — sensitive to subtle pixel-level changes
  - **pHash** (Perceptual Hash) — robust to minor rendering differences
- Configurable alert threshold per region (0.10–1.00, default 0.99)
- Configurable refresh rate (300–5000ms, default 1000ms)

### Alert State Machine
Each monitored region runs a timed state machine:

| State | Color | Meaning |
|---|---|---|
| OK | Green | No change detected |
| Alert | Red | Change detected — alert is active |
| Warning | Orange | Was alerted, no new change, cooling down |
| Paused | Blue | Monitoring paused by user |
| Disabled | Orange | Region disabled or no window attached |

Transitions:
- **OK → Alert** when a change is detected (alert + sound triggered)
- **Alert → Alert** when another change is detected (hold timer resets, no duplicate sound)
- **Alert → Warning** when no change is detected for the configured hold duration
- **Warning → Alert** if a new change is detected (sound re-triggered)
- **Warning → OK** when no change is detected for the configured hold duration

### Audio Alerts
- **Text-to-Speech (TTS):** Speaks a configurable alert message using Windows SAPI (via PowerShell — no extra engine needed)
- **Sound file playback:** Play any audio file on alert using the pygame mixer
- Both TTS and sound can be enabled or disabled independently per session
- Alerts are queued and serialized to avoid overlapping speech

### Focus-on-Alert
- When an alert fires, ScreenAlert can automatically bring the alerting window to the foreground
- Configurable cooldown prevents focus from thrashing during repeated alerts

### Live Thumbnail Overlays
- Each monitored window gets a floating thumbnail overlay window showing a live preview
- Overlays update in real time (up to 30 FPS)
- Per-overlay controls:
  - Opacity (0.2–1.0)
  - Always-on-top toggle
  - Border display toggle
  - Resizable (100–1280 × 80–800 pixels)
- Overlay visibility can be toggled per window
- Option to hide overlays when the source window is unavailable

### Theme Presets
Four built-in themes selectable at runtime with live preview:
- **Default** — dark with orange accents
- **Slate** — muted blue-grey
- **Midnight** — deep blue-black
- **High Contrast** — maximum visibility for accessibility

### Configuration Persistence
- All settings are saved automatically to JSON config files in `%APPDATA%\ScreenAlert\`
- Persists across restarts: windows, regions, positions, sizes, thresholds, alert text, and UI state
- Multi-monitor position memory — overlays reopen where you left them
- Supports a custom config file path via `--config` command-line flag

### Pause and Resume
- Global pause/resume for all monitoring at once
- Per-region enable/disable toggles
- Configurable pause reminder — alerts you (via TTS) if you leave monitoring paused for too long

### Window Tree and Filtering
- Hierarchical window/region tree in the main UI with status icons
- Filter/search to quickly find windows or regions by name
- Icon strip in the tree shows per-window status at a glance with tooltip details

### Automatic Update Checker
- On startup, quietly checks GitHub for a newer release
- Notifies you in-app if an update is available with a link to the release page

### Headless Mode
Run monitoring without any UI (useful for server use or scripting):

```bat
.venv\Scripts\python.exe screenalert.py --headless
```

### Plugin Hook System
An in-process event hook registry lets developers register callbacks for monitoring events (alerts, region changes, window lost) without modifying core code.

### Diagnostics and Logging
- Structured log files written to `%APPDATA%\ScreenAlert\logs\`
- Verbose and diagnostics modes for troubleshooting
- Thread dump support for debugging hangs:
  ```bat
  .venv\Scripts\python.exe screenalert.py --thread-dump-interval 30
  ```
- UI watchdog that detects and logs unresponsive states

---

## Command-Line Options

| Option | Description |
|---|---|
| `--config PATH` | Use a custom config JSON file |
| `--headless` | Run monitoring without the GUI |
| `--verbose` | Enable verbose logging |
| `--diagnostics` | Enable full diagnostics mode |
| `--thread-dump-interval N` | Dump all thread stacks every N seconds |
| `--dump-threads-now` | Write one immediate thread dump at startup |

---

## Dependencies

| Package | Purpose |
|---|---|
| Pillow | Image capture and processing |
| scikit-image | SSIM change detection |
| numpy | Array operations |
| opencv-python | Image comparison (pHash support) |
| imagehash | Perceptual hashing |
| pywin32 | Windows API (window capture, activation) |
| psutil | Process management |
| pyautogui | Screen utilities |
| pyttsx3 | TTS fallback engine |
| pygame | Audio playback |

---

## Project Structure

```
ScreenAlert/
├── screenalert.py               # Entry point
├── install.bat                  # Windows installer (sets up venv)
├── launch_ScreenAlert.bat       # Launcher (uses venv automatically)
├── screenalert_requirements.txt # Python dependencies
└── screenalert_core/
    ├── screening_engine.py      # Main engine loop
    ├── core/
    │   ├── config_manager.py    # Settings persistence
    │   ├── window_manager.py    # Windows API integration
    │   ├── cache_manager.py     # Image capture cache
    │   └── image_processor.py   # SSIM / pHash processing
    ├── monitoring/
    │   ├── region_monitor.py    # Per-region state machine
    │   └── alert_system.py      # TTS and sound alerts
    ├── rendering/
    │   ├── thumbnail_renderer.py # Floating overlay windows
    │   └── overlay_adapter.py   # Overlay lifecycle management
    ├── ui/
    │   ├── main_window.py       # Main control window
    │   ├── settings_dialog.py   # Settings UI
    │   ├── window_selector_dialog.py
    │   ├── region_editor_dialog.py
    │   ├── region_selection_overlay.py
    │   ├── thumbnail_card.py
    │   └── plugins_dialog.py
    └── utils/
        ├── constants.py         # App-wide constants
        ├── helpers.py
        ├── plugin_hooks.py      # Plugin event registry
        └── update_checker.py    # GitHub release checker
```

---

## Author

Ed Perry — [https://github.com/eperry/ScreenAlert](https://github.com/eperry/ScreenAlert)
