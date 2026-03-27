# Release Notes

## 2.0.6

### DWM Overlay System (New)

Replaced the software thumbnail pipeline (PrintWindow → PIL → Tkinter) with hardware-composited DWM thumbnails. The OS compositor now handles rendering at display refresh rate, eliminating the choppy/flashy updates of the old system.

- **DWM thumbnail backend**: New `ThumbnailBackend` abstraction with `DwmThumbnailBackend` implementation using `DwmRegisterThumbnail`, `DwmUpdateThumbnailProperties`, and `DwmQueryThumbnailSourceSize`. Designed for future swappability if Windows changes the compositing API.
- **Native Win32 overlay windows**: Each overlay is a lightweight Win32 `WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_NOACTIVATE` window with a dedicated message pump thread. No Tkinter dependency for overlays.
- **Decoupled display from monitoring**: DWM handles thumbnail display independently; PrintWindow captures continue only for SSIM/region analysis. Closing an overlay does not stop monitoring.
- **All existing interactions preserved**:
  - Left-click: bring source window to foreground
  - Left-click drag: move overlay
  - Right-click drag: resize overlay
  - Shift + right-click drag: sync resize all overlays
  - Close button: hides overlay (monitoring continues)
  - Mouse hover: shows window title
  - Active window: highlighted border on the active overlay
- **Overlay scaling modes** (Settings > Appearance):
  - **Fit**: Aspect ratio locked — resizing adjusts both axes together to match source proportions
  - **Stretch**: Free-form — thumbnail stretches to fill any shape
  - **Letterbox**: Free-form resize with aspect-preserved thumbnail and black bars
- **"Not Available" screen**: When DWM registration fails (e.g. source window closed), the overlay displays a blue placeholder instead of disappearing.
- **DPI awareness**: Overlays respond to `WM_DPICHANGED` for correct scaling on mixed-DPI multi-monitor setups.
- **Source resize tracking**: Periodic `DwmQueryThumbnailSourceSize` polling detects when the source window changes size and updates the dest rect accordingly.

### Auto-Discovery

- **Background window discovery**: A lightweight background thread periodically scans for disconnected thumbnails and automatically reconnects when the monitored application comes back online. Completely separate from the main monitoring loop.
- **Show Overlay on Connect** (Settings > Appearance): When enabled (default), overlays automatically appear when a window is discovered or reconnected. When off, overlays stay hidden until manually enabled.
- **Auto-Discover Windows** (Settings > Appearance): Toggle auto-discovery on/off.
- **Auto-Discovery Interval** (Settings > Appearance): Configurable scan interval (10–300 seconds, default 60).

### Reconnect Improvements

- **Configurable size tolerance**: Window identity validation now allows a configurable pixel tolerance (default 20px) instead of requiring an exact size match. This prevents unnecessary reconnect cycles caused by minor window size fluctuations. Adjustable in Settings > Reconnect.
- **Relaxed reconnect matching**: Automatic reconnection no longer requires an exact size match to find the target window. The stored size is updated after a successful reconnect so future validation cycles pass.
- **Manual replacement on reconnect failure**: When a single-window reconnect fails, the user is prompted to select a replacement window from the window selector. Existing regions and settings are preserved. Can be toggled in Settings > Reconnect.
- **Proportional region scaling**: When a window reconnects at a different size (either automatically or via manual replacement), all monitored regions are scaled proportionally to match the new dimensions.

### Bug Fixes

- **Duplicate thumbnail rejection**: Adding a thumbnail with a title that already exists now correctly returns `None` and logs a warning, instead of silently returning the existing thumbnail's ID.
- **Thumbnail map sync**: The UI thumbnail map is rebuilt after reconnect operations and during periodic updates, keeping HWND keys in sync when the engine updates handles on the background thread.

### UI Improvements

- **"Overview" renamed to "Overlay"** throughout the UI: menu items, status messages, and config keys. Old `overview_visible` config values are read for backward compatibility.
- **Unified reconnect flow**: All reconnect paths (manual, auto-discovery, main loop) now go through a single `_mark_connected` method that consistently updates config, links DWM, sets availability, and shows the overlay.

### Settings

- New **Reconnect** category in the settings dialog with:
  - **Size Tolerance (px)**: Pixel tolerance for window size matching (0–500, default 20).
  - **Prompt on Reconnect Fail**: Toggle the replacement-window prompt after a failed manual reconnect.
- New **Appearance** settings:
  - **Overlay Update Rate (Hz)**: DWM thumbnail update timer frequency (10–60 Hz, default 30).
  - **Overlay Scaling**: Fit / Stretch / Letterbox mode selector.
  - **Auto-Discover Windows**: Enable/disable background window discovery.
  - **Auto-Discovery Interval (sec)**: Scan frequency (10–300s, default 60).
  - **Show Overlay on Connect**: Auto-show overlays when windows are discovered.
