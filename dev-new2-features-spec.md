# ScreenAlert: dev-new2-features Branch Specification

## Overview

This document specifies all features, enhancements, and improvements to be implemented in the new `dev-new2-features` branch, based on prior work and user requests. It serves as the authoritative reference for development and testing.

## Completion Status (March 2, 2026)

Implementation status for this branch: **Complete**.

- All UI/UX, monitoring, alerting, and persistence requirements in this spec are implemented.
- Optional features requested in prior summaries are implemented, including plugin hook scaffolding and optional update checks.
- Core automated tests are present and passing for maintained tests under `tests/`.
- Known non-pytest-compatible legacy root test script (`test_api_integration.py`) remains outside the maintained `tests/` suite.

### Post-completion Addendum (dev-new3 integration)

Follow-on UX and reliability work was implemented under `dev-new3-next-level-spec.md` and is now part of the active branch behavior:

- Main action controls moved from top-button strip into menu/context-menu workflows.
- Region cards include explicit `Name:` and `Alert Text:` fields with per-region TTS template persistence.
- Add Window dialog was redesigned to show inline title + indented size rows, remove the separate details panel, and persist filter state.
- Window selection metadata (`window_class`, `window_size`, `monitor_id`) is persisted for stronger reconnect matching.
- Windows TTS reliability decision: switched to isolated `System.Speech` PowerShell invocation for each utterance to avoid repeated-alert pyttsx3/SAPI lockups.

### Latest Stabilization Updates (March 2, 2026)

The following runtime issues were reproduced and fixed after the initial completion pass:

1. **Region cards showed "No image"**
    - **Root cause:** UI detail rendering relied only on short-lived cache entries.
    - **Fix:** Added UI capture fallback that attempts a direct window capture when cache is empty, then stores that image back into cache for reuse.
    - **Result:** Region thumbnails populate even when monitoring has not been running long enough to warm cache.

2. **Window Info preview showed no image**
    - **Root cause:** Window preview path also depended solely on cache availability.
    - **Fix:** Reused the same cache-first + capture-fallback image path for Window Info preview rendering.
    - **Result:** Window preview image is displayed whenever capture is available, including single-window "All windows" view.

3. **Target application not visible while selecting a region**
    - **Root cause:** Region selection overlay was fully opaque and could obscure the target window.
    - **Fix:** Updated selection flow and overlay behavior:
      - Minimize ScreenAlert before selection, then restore/focus after selection.
      - Use a semi-transparent overlay so the target app remains visible.
      - Draw a highlighted rectangle around the target window area.
      - Correct overlay drawing coordinates for non-primary monitor offsets.
    - **Result:** Region selection is now visually aligned with the target app and usable across monitor layouts.

4. **High-frequency monitor enumeration warnings during diagnostics**
    - **Root cause:** Incorrect call signature used for Win32 monitor enumeration.
    - **Fix:** Replaced callback-style call with pywin32-compatible monitor enumeration and robust rectangle extraction.
    - **Result:** Eliminated repeated monitor-info exceptions and reduced diagnostic log churn.

5. **Alert state machine redesigned to deterministic lifecycle**
    - **Implemented flow:** `PAUSED/N/A -> OK -> ALERT -> WARNING -> OK`
    - **Behavior:**
      - ALERT (red) is held for configurable seconds and resets when new changes keep arriving.
      - WARNING (orange) follows ALERT after no new changes for hold duration.
      - OK (green) follows WARNING after an additional hold period of no new changes.
      - PAUSED and N/A remain separate non-alerting states.
    - **Config:** Added `alert_hold_seconds` to settings/config (default 10s).

6. **Small visual changes were not always detected**
    - **Root cause:** SSIM/pHash global similarity could miss tiny text changes in large regions.
    - **Fix:** Added pixel-difference pre-check in change detection path.
    - **Result:** Small numeric/text updates inside monitored regions now trigger alert transitions reliably.

7. **Region card/toolbar status UX refinement**
    - **Implemented:**
      - Added in-card countdown text under ALERT/WARNING status.
      - Removed duplicate secondary status indicator beneath Disable.
      - Added aggregate status badge in top-right toolbar (left of Settings).
      - Aggregate priority now enforced as: ALERT > WARNING > OK > PAUSED/N/A.

8. **Runtime logging volume reduction**
    - **Fix:** Lowered verbosity for high-frequency render/UI/window loggers in startup logging configuration.
    - **Result:** Diagnostics remain useful while avoiding excessive per-frame log noise.

---

## 2. Logging and Diagnostics

- Creates logging and config directories in `%APPDATA%`.
- log files should always have time and date stamp of when the app was started
- Logging to both file and console, with log rotation.
- Verbose/debug logging mode for troubleshooting.
- Log startup, shutdown, and all major actions.
- Log all exceptions and errors with tracebacks.

**Status:** Implemented


## 3. UI/UX Enhancements

- Modern, dark-themed interface (gaming style).
- Window and region selection overlays with live previews.
- Multi-monitor support with robust monitor enumeration.
- Window picker dialog with filtering and search.
- Region editor with drag-resize and visual feedback.
- Status bar with real-time monitoring state.
- Tooltips and help popups for all controls.
- Settings dialog for all configurable options.
- Keyboard shortcuts for all major actions.
- Accessibility: High-contrast mode and screen reader support.
- Responsive layout for different DPI/scale settings.

**Status:** Implemented

## 4. Window/Region Monitoring

- Monitor specific windows (not just the desktop).
- Robust window reconnection logic (title, class, size, monitor).
- Region monitoring with per-region status (OK, Alert, Warning, Paused, Disabled, Unavailable).
- Deterministic alert lifecycle state machine with timed transitions and configurable hold duration.
- Visual indicators for each region.
- Individual controls to pause or disable regions.
- Thumbnail previews for each monitored region.
- Window/region availability checks and error handling.
- Countdown display for timed ALERT/WARNING states.

**Status:** Implemented

## 5. Alert System

- Visual change detection using SSIM and pHash.
- Pixel-difference pre-check to catch very small text/number changes.
- Configurable sound alerts (per region and global).
- Text-to-speech (TTS) alerts with customizable messages.
- Adjustable alert thresholds and sensitivity.
- Configurable alert hold timer used by ALERT and WARNING transitions.
- Pause reminder tones with interval settings.
- Option to capture screenshots on alert/green.
- Configurable capture directory and filename format.

## 5.1 Aggregate Status

- Global aggregate status shown in top toolbar.
- Priority resolution implemented as:
    1. ALERT
    2. WARNING
    3. OK
    4. PAUSED/N/A (only when no OK/WARNING/ALERT regions exist)

**Status:** Implemented

**Status:** Implemented

## 6. Configuration and Persistence

- All settings and regions saved to a config file in `%APPDATA%`.
- Auto-migrate config from old locations if needed.
- Export/import configuration for backup and sharing.
- Backward compatibility with previous config versions.

**Status:** Implemented

## 7. Code Quality and Maintainability

- Modular code structure (core, UI, monitoring, rendering, utils).
- Type annotations and docstrings for all public methods.
- Defensive programming: handle all exceptions gracefully.
- Automated tests for core logic (where feasible).
- Clean up all temporary and cache files on exit/uninstall.

**Status:** Implemented

## 8. Additional Features (from previous summaries)

- Thumbnail region previews in main UI.
- Enhanced region editor with live feedback.
- Improved monitor enumeration (fix EnumDisplayMonitors usage).
- Fix all known startup and initialization order bugs (e.g., UI variable initialization).
- Add verbose logging for all startup and UI actions.
- Ensure all window/region actions are robust to missing/invalid windows.
- Support for future plugin/extension system (design hooks, not implementation).

**Status:** Implemented

---

## Development Notes

- All features must be implemented incrementally with clear commits.
- Each feature should be tested independently.
- Use this document as the checklist for branch completion.

## Validation Summary

- Maintained test suite: `10 passed` (`pytest -q tests`)
- Added test coverage for plugin hooks, update checker, config features, image detection, and cache/temp cleanup
- Revalidated after dev-new3 stabilization updates: `10 passed` (`pytest -q tests`)

---

*End of specification.*

