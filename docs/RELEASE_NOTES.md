# Release Notes

## 2.0.7

### MCP Server (New)

ScreenAlert now embeds a full MCP (Model Context Protocol) server, allowing Claude Desktop, Claude Code, and any MCP-compatible AI client to monitor, query, and control ScreenAlert in real time.

#### Architecture decisions made during development

- **Embedded server, not a separate launcher.** The MCP server runs inside the ScreenAlert process on a daemon thread (uvicorn + asyncio). No separate executable or Python script to install.
- **HTTPS only by default.** A self-signed TLS certificate is auto-generated on first start and stored in `%APPDATA%\ScreenAlert\`. All clients connect with `https://`. An optional HTTP→HTTPS redirect listener can be enabled for clients that cannot use HTTPS directly.
- **Bearer token authentication.** A 64-character hex API key is generated automatically on first run. It is stored in `mcp_config.json` and must be included in every request as `Authorization: Bearer <key>`.
- **Dual transport.** Both SSE (`/v1/sse`) and Streamable HTTP (`/v1/mcp`) endpoints are exposed. Claude Desktop uses SSE; Claude Code CLI also uses SSE. The Streamable HTTP endpoint is available for future clients.
- **FastMCP tooling layer.** Tools are registered via FastMCP closures that capture the live engine, config, and event logger. Return type annotations drive FastMCP's serialisation — `dict` (builtin) returns a single JSON object; `List[dict]` (typing) returns one `TextContent` item per list element.

#### Transport endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health` | Public liveness check — no auth |
| `GET /v1/status` | Server info, uptime, cert fingerprint — auth required |
| `GET /v1/skills` | List all registered tools — auth required |
| `GET /v1/sse` | SSE transport (MCP 2024-11-05) |
| `POST /v1/mcp` | Streamable HTTP transport (MCP 2025-03-26) |
| `GET /v1/resources/…` | Browse and download captured alert images |

#### Tools (28 total)

| Category | Tools |
| --- | --- |
| Utility | `ping` |
| Windows (8) | `list_windows`, `find_desktop_windows`, `add_window`, `remove_window`, `reconnect_window`, `reconnect_all_windows`, `get_window_settings`, `set_window_setting` |
| Regions (8) | `list_regions`, `add_region`, `remove_region`, `copy_region`, `list_alerts`, `acknowledge_alert`, `get_region_settings`, `set_region_setting` |
| Monitoring (4) | `pause_monitoring`, `resume_monitoring`, `mute_alerts`, `get_monitoring_status` |
| Settings (2) | `get_global_settings`, `set_global_setting` |
| Event Log (3) | `get_event_log`, `get_event_summary`, `clear_event_log` |
| Images (2) | `get_alert_image`, `get_alert_diagnostic_images` |

#### Prompts (5 total)

Built-in prompt templates exposed to MCP clients: `analyse_alert_history`, `what_needs_attention`, `show_recent_captures`, `diagnose_window`, `daily_summary`.

#### Event logging

A JSONL event log (`event_log.jsonl`) records every significant event — alerts, reconnects, settings changes, MCP actions. Queryable via `get_event_log` / `get_event_summary`. Configurable retention (`event_log_max_rows`) and enabled/disabled toggle. Events are written by `EventLogger` which is wired into the engine and MCP tools.

#### UI integration

- **MCP status button** in the status bar: shows **MCP: On** / **MCP: Off**. Click to toggle the server without restarting the app.
- **Help → MCP Server…** dialog: shows server status, listen address, clickable browse URL and SSE endpoint link (opens browser), and the bearer token with a one-click **Copy** button.
- **Settings → MCP Server** category: all MCP settings configurable without editing JSON.

#### Settings added

| Setting | Default | Description |
| --- | --- | --- |
| `mcp_enabled` | `true` | Enable/disable the MCP server |
| `mcp_listen_host` | `127.0.0.1` | IP address the server binds to |
| `mcp_port` | `8443` | HTTPS listen port |
| `mcp_max_connections` | `5` | Maximum simultaneous client connections |
| `mcp_http_redirect` | `false` | Enable plain-HTTP → HTTPS redirect listener |
| `mcp_http_port` | `8080` | Port for the HTTP redirect listener |

`mcp_api_key`, `mcp_ssl_cert_path`, and `mcp_ssl_key_path` are managed automatically and not shown in the UI.

---

### Config File Split (New)

ScreenAlert now persists configuration across three separate JSON files:

| File | Contents |
| --- | --- |
| `screenalert_config.json` | App settings (monitoring, audio, appearance, logging, UI state) |
| `screenalert_windows_regions.json` | Window and region definitions |
| `mcp_config.json` | All MCP server settings (connection, auth, TLS) |

**Migration is automatic.** On the first run after upgrading, `mcp_*` values are read from `screenalert_config.json` as before. The next `save()` writes them to `mcp_config.json` and removes them from `screenalert_config.json`. No manual steps required.

**Rationale:** MCP config (API key, TLS paths, port, listen address) has a different lifecycle from application settings — it changes rarely, needs to be read by external tools, and contains the API key. Keeping it separate makes it easier to back up, share, or inspect without touching the main config.

---

### MCP Server — Listen Address Setting (New)

The MCP server now binds to a configurable IP address (Settings → MCP Server → **Listen Address**).

- Default: `127.0.0.1` — accepts connections from this machine only (safest for most users).
- `0.0.0.0` — accepts connections from any network interface (useful for remote AI clients on a LAN).
- Any specific IP on the machine can be specified.

**Decision:** Default changed from the implicit `127.0.0.1` hardcode to an explicit setting so users can expose ScreenAlert to other machines on their network when needed.

---

### MCP Integration Test Suite (New)

84 automated tests covering all 28 MCP tools, HTTP endpoints, error paths, and edge cases.

- **Mock mode** (default): starts an in-process MCPServer with a MockEngine and a real ConfigManager seeded with test data. Fast (~4 seconds for 84 tests), no external dependencies.
- **Live mode** (`--live` flag): connects to a running ScreenAlert instance via SSE. 71 tests run; 13 are automatically skipped when they require direct engine/config access that isn't available over the wire.

```bash
pytest tests/test_mcp_tools.py -v           # mock server
pytest tests/test_mcp_tools.py -v --live    # live ScreenAlert on port 8443
```

**Decisions made during testing:**

- FastMCP return type annotations determine serialisation: `dict` (builtin) → single `TextContent`; `List[dict]` (typing) → one `TextContent` per element. All tool return types audited and corrected.
- `monitor.is_alert` is a `@property`, not a callable. `list_alerts` and `acknowledge_alert` were calling it with `()` — fixed.
- Live mode uses SSE transport (`/v1/sse`); the Streamable HTTP endpoint (`/v1/mcp`) is not reachable from the MCP SDK client in the current FastMCP version.
- Live tests retry up to 3 times with 0.5s backoff to handle the `mcp_max_connections=5` limit when many tests run in rapid succession.

---

### Bug Fixes

- **`list_alerts` crash**: `monitor.is_alert()` was being called as a method; `is_alert` is a `@property`. Fixed in `mcp/tools/regions.py`.
- **`acknowledge_alert` crash**: Same `is_alert()` call pattern. Fixed.
- **`set_global_setting` `UnboundLocalError`**: In `_write_value`, helper functions `_apply_log_level`, `_apply_event_log_enabled`, `_apply_event_log_max_rows` were defined after the `setters` dict that referenced them. Python's scoping rules marked them as locals at compile time, causing `UnboundLocalError` at runtime. Fixed by moving definitions before the dict.

---

### Overlay Visibility Fix

Overlays were not appearing on startup, and enabling them had no effect. Multiple related bugs were found and fixed together:

**Root cause:** `overlay_visible` was never written when a new thumbnail was created by `add_thumbnail()`. On load, `.get("overlay_visible", True)` returns `True` only when the key is *absent* — but when the key exists with value `null` (JSON null / Python `None`), `.get()` returns `None`, and `bool(None)` is `False`. Every overlay therefore started hidden.

**Fixes:**

- **`config_manager`**: `add_thumbnail()` now always writes `"overlay_visible": True` into the new thumbnail dict. Config load sanitizes every existing thumbnail — `None` or absent values are normalised to `True`, and the legacy `overview_visible` key is migrated in the same pass.
- **`overlay_window`**: `OverlayWindow.__init__` now reads `overlay_visible` and `enabled` from config at creation time and sets `_is_user_hidden` accordingly. The Win32 window is shown or hidden immediately without waiting for the engine's async `set_thumbnail_user_visibility` call (which was arriving after window creation due to the async command queue).
- **Disabled windows no longer show an overlay.** A window with `enabled: false` (e.g. a character that is offline) no longer creates a visible but empty overlay shell. `enabled: false` now forces `_is_user_hidden = True` at init regardless of `overlay_visible`.
- **`overlay_manager`**: The DWM thumbnail link is attempted immediately from the config `window_hwnd` during overlay creation, so content appears without waiting for the engine's first `set_source_hwnd` cycle.
- **MCP `set_window_setting`**: Setting `enabled = true` via MCP now also restores live overlay visibility (calls `set_thumbnail_user_visibility`) if `overlay_visible` is `true`.
- **All `overview_visible` fallback chains removed.** Every inline `.get("overlay_visible", .get("overview_visible", True))` pattern replaced with `.get("overlay_visible", True)` — safe now that config load performs the migration.

---

### Repository Restructure

- **Docs consolidated into `docs/`**: `RELEASE_NOTES.md`, `SPEC-DWM-THUMBNAILS.md`, `ARCHITECTURE.md`, and `V2_DEVELOPMENT_SUMMARY.md` moved from the repo root and `screenalert_core/` into `docs/` (history preserved via `git mv`).
- **README updated**: Project structure tree, AI Integration (MCP) section with link to `docs/MCP_SETUP.md`, CLI options table (`--log-level`, `--verbose`, `--diagnostics`), and dependency list brought up to date.
- **Dev artifacts removed**: `SECURITY.md`, `docs/CODE_REVIEW_FIXES.md`, `docs/SCREENALERT_README.md`, `tools/` (three standalone scripts), and stale log/session files deleted from the repo.

---

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

### Fixes

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

### Logging

- **Unified log level**: Multiple per-feature logging flags (`log_verbose`, `diagnostics_enabled`, etc.) replaced with a single **Log Level** dropdown in Settings — `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `ERROR`).
- **TRACE level**: Custom severity below DEBUG for very high-frequency diagnostic output.
- **Runtime log level changes**: Changing the log level in Settings takes effect immediately with no restart required.
- **`--log-level` CLI flag**: Pass `--log-level DEBUG` (or any level) to override the saved config at launch. `--verbose` and `--diagnostics` continue to work as aliases for `DEBUG`.
- **Backward compatibility**: Old configs with `log_verbose: true` automatically migrate to `log_level: DEBUG` on first load.

### Code Quality & Internal

- **`log_setup.py`**: Centralised logging initialisation (`setup_logging`) and runtime level switching (`set_runtime_log_level`) to avoid circular imports.
- **`win32_types.py`**: All Win32 constants, DLL handles, and ctypes struct definitions extracted from `overlay_window.py` into `rendering/win32_types.py` for reuse and clarity.
- **Alert diagnostics**: `save_alert_diagnostics` extracted from `screening_engine` into `utils/diagnostics.py` as a standalone, independently testable pure function.
- **Engine deduplication**: Six copies of the 3-line window identity extraction pattern replaced by `_extract_window_identity()` and `_validate_thumbnail_window()` helpers in `screening_engine`.
- **UI mixins**: `main_window.py` split into focused mixin modules — `WindowSlotMixin` (slot management), `EngineEventMixin` (engine→UI event delivery), `SettingsMixin` (runtime settings application).
- **Error handling**: `reconnect_window`, `reconnect_all_windows`, and `apply_runtime_settings` in the engine are now individually guarded with try/except and full tracebacks; engine event flush handles each event independently so one failure does not abort the rest.
