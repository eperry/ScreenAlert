# Release Notes

## 2.0.6

### Reconnect Improvements

- **Configurable size tolerance**: Window identity validation now allows a configurable pixel tolerance (default 20px) instead of requiring an exact size match. This prevents unnecessary reconnect cycles caused by minor window size fluctuations. Adjustable in Settings > Reconnect.
- **Relaxed reconnect matching**: Automatic reconnection no longer requires an exact size match to find the target window. The stored size is updated after a successful reconnect so future validation cycles pass.
- **Manual replacement on reconnect failure**: When a single-window reconnect fails, the user is prompted to select a replacement window from the window selector. Existing regions and settings are preserved. Can be toggled in Settings > Reconnect.
- **Proportional region scaling**: When a window reconnects at a different size (either automatically or via manual replacement), all monitored regions are scaled proportionally to match the new dimensions.

### Bug Fixes

- **Duplicate thumbnail rejection**: Adding a thumbnail with a title that already exists now correctly returns `None` and logs a warning, instead of silently returning the existing thumbnail's ID.
- **Thumbnail map sync**: The UI thumbnail map is rebuilt after reconnect operations and during periodic updates, keeping HWND keys in sync when the engine updates handles on the background thread.

### Settings

- New **Reconnect** category in the settings dialog with:
  - **Size Tolerance (px)**: Pixel tolerance for window size matching (0–500, default 20).
  - **Prompt on Reconnect Fail**: Toggle the replacement-window prompt after a failed manual reconnect.
