# ScreenAlert

ScreenAlert is a desktop monitoring tool for tracking visual changes in selected regions of application windows.

It is designed for situations where you need quick visual awareness across multiple windows and multiple monitored zones.

ScreenAlert does not automate actions in target applications. It observes, compares, and reports.

## Current Features

- Multi-window monitoring with persistent window identity metadata.
- Region-based change detection with configurable threshold and detection method.
- Runtime controls for pause/resume, per-region enable/disable, and focus behavior.
- Alerting pipeline with status visualization and configurable alert text.
- Live thumbnail overlays with title/status, opacity, border, and topmost controls.
- Theme presets (including high-contrast) with saved settings and runtime apply.
- Region management from the main UI (add/remove/select) with active-region detail view.
- Configuration persistence for app settings, windows, and monitored regions.

## Screenshots

Settings dialog

![ScreenAlert Settings](docs/images/screenalert-settings.png)

Window selection dialog

![Select Window to Monitor](docs/images/select-window-dialog.png)

Main dashboard with active region

![Main Dashboard](docs/images/main-dashboard.png)

## Installation (Windows)

Run the installer to create a virtual environment and install all dependencies:

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

The launcher will automatically use the virtual environment.

## 🚀 Building ScreenAlert

ScreenAlert uses **ACT (local GitHub Actions)** for consistent, reproducible builds:

```powershell
.\run-github-actions.ps1
```

This runs the complete build process in a containerized environment.

📖 See [BUILD.md](BUILD.md) for detailed build instructions.
