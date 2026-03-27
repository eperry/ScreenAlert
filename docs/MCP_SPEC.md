# ScreenAlert MCP Server — Specification & Implementation Plan

## Overview

An MCP (Model Context Protocol) server that exposes the full ScreenAlert feature set to Claude Desktop and Claude Code. Allows Claude to query status, manage windows and regions, change settings, and analyze alert captures — all from a natural language conversation.

The MCP server runs as a local process on the same machine as ScreenAlert. Communication is via stdio (no network/internet required for the MCP connection itself; only Claude's intelligence routes through Anthropic's API).

---

## Architecture

```
Claude Desktop / Claude Code
        │
        │  stdio (local, no internet)
        ▼
screenalert_mcp_server.py        ← MCP server process
        │
        ├── ScreenAlertEngine    ← shared engine instance (or IPC to running app)
        ├── ConfigManager        ← read/write config
        ├── EventLog (SQLite)    ← transaction/event history
        └── CaptureStore         ← image files on disk
```

### Connection model

Two deployment options (decide before implementation):

| Mode | Description | Pros | Cons |
|---|---|---|---|
| **Embedded** | MCP server imports and wraps the live ScreenAlert engine | Real-time access, no IPC | Must run inside the ScreenAlert process |
| **Standalone** | Separate process, communicates via named pipe or shared SQLite | Independent lifecycle | Slightly more complex wiring |

**Recommendation: Embedded.** Launch the MCP server as a thread inside the running ScreenAlert app. The engine is already available; no IPC needed.

I agree lets do embedded

---

## Tool Catalogue

### Windows

| Tool | Parameters | Returns | Description |
|---|---|---|---|
| `list_windows` | — | `[{id, name, status, overlay_visible, hwnd, slot}]` | All monitored windows and their current state |
| `find_desktop_windows` | `filter?: str` | `[{hwnd, title, class, size, monitor}]` | Scan the desktop for open windows available to add |
| `add_window` | `title: str`, `hwnd?: int` | `{id, name}` | Add a window to monitoring |
| `remove_window` | `window_id: str` | `{ok: bool}` | Remove a window and all its regions |
| `reconnect_window` | `window_id: str` | `{result: "already_valid"\|"reconnected"\|"failed"\|"missing"}` | Force reconnect one window |
| `reconnect_all_windows` | — | `{total, reconnected, failed, already_valid}` | Force reconnect all disconnected windows |
| `get_window_settings` | `window_id: str` | `{key: {value, type, description}}` | All configurable settings for a window |
| `set_window_setting` | `window_id: str`, `key: str`, `value: any` | `{ok: bool, error?: str}` | Set any window setting by key |

**Window setting keys:**

| Key | Type | Description |
|---|---|---|
| `name` | str | Display name / window title |
| `overlay_visible` | bool | Whether the overlay is currently shown |
| `opacity` | float 0–1 | Overlay opacity |
| `always_on_top` | bool | Overlay always on top |
| `show_border` | bool | Show border on overlay |
| `window_slot` | int\|null | Assigned slot number |
| `enabled` | bool | Whether this window is actively monitored |

---

### Regions

| Tool | Parameters | Returns | Description |
|---|---|---|---|
| `list_regions` | `window_id?: str` | `[{id, window_id, name, enabled, state, rect}]` | All regions (optionally filtered by window) |
| `add_region` | `window_id: str`, `name: str`, `rect: {x, y, width, height}` | `{id, name}` | Add a region with window-relative coordinates |
| `remove_region` | `region_id: str` | `{ok: bool}` | Remove a region |
| `list_alerts` | — | `[{window_id, window_name, region_id, region_name, since}]` | All currently active alerts |
| `get_region_settings` | `region_id: str` | `{key: {value, type, description, valid_values?}}` | All configurable settings for a region |
| `set_region_setting` | `region_id: str`, `key: str`, `value: any` | `{ok: bool, error?: str}` | Set any region setting by key |

**Region setting keys:**

| Key | Type | Description |
|---|---|---|
| `name` | str | Region display name |
| `rect` | {x, y, width, height} | Position and size in window-relative coordinates |
| `enabled` | bool | Whether this region is actively monitored |
| `tts_message` | str | TTS message template spoken on alert |
| `sound_file` | str | Path to sound file played on alert |
| `sound_enabled` | bool | Whether sound is enabled for this region |
| `tts_enabled` | bool | Whether TTS is enabled for this region |
| `alert_hold_seconds` | float | How long the alert state is held after trigger |

---

### Monitoring Control

| Tool | Parameters | Returns | Description |
|---|---|---|---|
| `pause_monitoring` | — | `{ok: bool}` | Pause all region monitoring (overlays stay up) |
| `resume_monitoring` | — | `{ok: bool}` | Resume region monitoring |
| `mute_alerts` | `seconds: int` | `{muted_until: str}` | Mute all alert sounds and TTS for N seconds |
| `get_monitoring_status` | — | `{running, paused, muted, mute_remaining_seconds, uptime_seconds}` | Current monitoring state |

---

### Global Settings

| Tool | Parameters | Returns | Description |
|---|---|---|---|
| `get_global_settings` | — | `{key: {value, type, description, valid_values?}}` | All global settings with metadata |
| `set_global_setting` | `key: str`, `value: any` | `{ok: bool, error?: str}` | Set any global setting — applies immediately at runtime |

**Global setting keys:**

| Key | Type | Valid Values | Description |
|---|---|---|---|
| `opacity` | float | 0.0–1.0 | Default overlay opacity |
| `always_on_top` | bool | — | Overlays always on top |
| `show_borders` | bool | — | Show borders on overlays |
| `overlay_scaling_mode` | str | Fit, Stretch, Letterbox | Overlay scaling behaviour |
| `refresh_rate_ms` | int | 50–5000 | Monitoring loop refresh rate |
| `log_level` | str | TRACE, DEBUG, INFO, WARNING, ERROR | Active log level |
| `show_overlay_when_unavailable` | bool | — | Show placeholder when window unavailable |
| `show_overlay_on_connect` | bool | — | Auto-show overlay when window reconnects |
| `alert_hold_seconds` | float | — | Default alert hold duration |
| `enable_sound` | bool | — | Global sound toggle |
| `enable_tts` | bool | — | Global TTS toggle |
| `default_tts_message` | str | — | Default TTS template |
| `suppress_fullscreen` | bool | — | Suppress alerts during fullscreen apps |
| `auto_discover` | bool | — | Enable background window discovery |
| `auto_discover_interval_seconds` | int | 10–300 | Discovery scan frequency |
| `size_tolerance_px` | int | 0–500 | Window size match tolerance |
| `capture_on_alert` | bool | — | Save screenshot on alert |
| `save_alert_diagnostics` | bool | — | Save diagnostic images on alert |
| `event_log_enabled` | bool | — | Enable transaction/event logging |
| `event_log_max_rows` | int | — | Max event log rows before pruning |

---

### Event Log

| Tool | Parameters | Returns | Description |
|---|---|---|---|
| `get_event_log` | `limit?: int`, `since?: str (ISO)`, `category?: str`, `window_id?: str`, `region_id?: str` | `[event]` | Query the event log with filters |
| `get_event_summary` | `since?: str (ISO)` | `{counts_by_category, counts_by_event, alerts_with_captures}` | Aggregated counts — good for "what happened today?" |
| `clear_event_log` | `category?: str` | `{rows_deleted: int}` | Clear all or one category of log entries |
| `get_alert_image` | `event_id: str` | image (base64 PNG) | Return the capture screenshot for an alert event |
| `get_alert_diagnostic_images` | `event_id: str` | `[image (base64 PNG)]` | Return all diagnostic images for an alert event |

---

## Event Log Schema

### Storage — JSONL (newline-delimited JSON)

Each event is one JSON object per line, appended to a single file:

```text
C:/Users/<user>/AppData/Roaming/ScreenAlert/event_log.jsonl
```

- **Append-only writes** — no file locking issues, no rewrite on every event
- **Schemaless** — each event carries whatever fields make sense for its type
- **Human-readable** — open in any text editor or pipe through `jq`
- **No library dependency** — Python stdlib `json` only
- **Rotation** — when the file exceeds `event_log_max_rows`, the oldest entries are trimmed (file is rewritten in-place, infrequent operation)

### Minimum required fields

Every event **must** have these fields — everything else is free-form:

| Field | Type | Description |
|---|---|---|
| `id` | str (uuid) | Unique event identifier |
| `timestamp` | str (ISO 8601) | When the event occurred |
| `category` | str | Broad grouping: `alert`, `window`, `region`, `settings`, `monitoring`, `system`, `mcp` |
| `event` | str | Specific event name within the category |
| `source` | str | What triggered it: `engine`, `user`, `auto_discovery`, `mcp`, `system` |

Beyond these five fields, events include whatever additional context is relevant. There is no enforced schema.

### Example events

**Alert with capture:**

```json
{"id": "a1b2c3", "timestamp": "2026-03-27T14:32:01.123", "category": "alert", "event": "region_alert", "source": "engine", "window_id": "abc", "window_name": "EVE - Edward Perry", "region_id": "def", "region_name": "local-chat", "previous_state": "ok", "new_state": "alert", "capture_file": "C:/captures/2026-03-27_143201.png", "diagnostic_files": ["C:/captures/diag/2026-03-27_143201_edges.png"]}
```

**Setting changed:**

```json
{"id": "b2c3d4", "timestamp": "2026-03-27T14:35:00.000", "category": "settings", "event": "setting_changed", "source": "mcp", "key": "opacity", "old_value": 0.8, "new_value": 0.6, "scope": "global"}
```

**Window reconnected:**

```json
{"id": "c3d4e5", "timestamp": "2026-03-27T14:36:12.456", "category": "window", "event": "reconnect_succeeded", "source": "auto_discovery", "window_id": "abc", "window_name": "EVE - Edward Perry", "old_hwnd": 12345, "new_hwnd": 67890}
```

**MCP tool call:**

```json
{"id": "d4e5f6", "timestamp": "2026-03-27T14:37:00.000", "category": "mcp", "event": "tool_called", "source": "mcp", "tool": "set_global_setting", "args": {"key": "opacity", "value": 0.6}, "result_status": "ok"}
```

### Known event names (non-exhaustive — new events can be added freely)

| Category | Event | Typical extra fields |
| --- | --- | --- |
| `alert` | `region_alert` | `window_id`, `window_name`, `region_id`, `region_name`, `previous_state`, `new_state`, `capture_file`, `diagnostic_files` |
| `alert` | `region_cleared` | `window_id`, `region_id`, `previous_state`, `new_state` |
| `alert` | `alert_suppressed` | `window_id`, `region_id`, `reason` |
| `window` | `window_added` | `window_id`, `window_name`, `hwnd` |
| `window` | `window_removed` | `window_id`, `window_name` |
| `window` | `window_connected` | `window_id`, `hwnd` |
| `window` | `window_disconnected` | `window_id`, `last_hwnd` |
| `window` | `window_discovered` | `window_id`, `hwnd` |
| `window` | `reconnect_attempted` | `window_id` |
| `window` | `reconnect_succeeded` | `window_id`, `old_hwnd`, `new_hwnd` |
| `window` | `reconnect_failed` | `window_id` |
| `window` | `overlay_shown` | `window_id` |
| `window` | `overlay_hidden` | `window_id` |
| `region` | `region_added` | `window_id`, `region_id`, `region_name`, `rect` |
| `region` | `region_removed` | `window_id`, `region_id`, `region_name` |
| `region` | `region_state_changed` | `window_id`, `region_id`, `from`, `to` |
| `settings` | `setting_changed` | `key`, `old_value`, `new_value`, `scope`, `window_id?`, `region_id?` |
| `monitoring` | `monitoring_started` | — |
| `monitoring` | `monitoring_paused` | — |
| `monitoring` | `monitoring_resumed` | — |
| `monitoring` | `alerts_muted` | `duration_seconds`, `muted_until` |
| `monitoring` | `alerts_unmuted` | — |
| `system` | `app_started` | `version` |
| `system` | `app_stopped` | — |
| `mcp` | `tool_called` | `tool`, `args`, `result_status` |

### Capture linkage

Alert events include capture file references as top-level fields (not nested). Fields are omitted entirely if capture was disabled — no null placeholders:

```json
{
  "previous_state": "ok",
  "new_state": "alert",
  "capture_file": "C:/captures/2026-03-27_143201_edward-perry_local-chat.png",
  "diagnostic_files": [
    "C:/captures/diag/2026-03-27_143201_window.png",
    "C:/captures/diag/2026-03-27_143201_edges.png"
  ]
}
```

Images are saved **before** the log entry is written so paths are always valid when present. The `get_alert_image` and `get_alert_diagnostic_images` tools read from these stored paths and return base64-encoded PNG data for Claude to analyze directly.

---

## MCP Resources

Expose the captures directory as browsable MCP resources so Claude Desktop can list and open them:

```
screenalert://captures/{filename}
screenalert://captures/diag/{filename}
```

Resources are listed by `list_resources` and read by `read_resource` — standard MCP protocol. Claude Desktop shows them in a sidebar panel.

---

## File Structure

```
screenalert_core/
  mcp/
    __init__.py
    server.py          ← MCP server entry point, tool registry, stdio loop
    tools/
      __init__.py
      windows.py       ← list_windows, find_desktop_windows, add_window, ...
      regions.py       ← list_regions, add_region, remove_region, ...
      monitoring.py    ← pause, resume, mute, get_status
      settings.py      ← get_global_settings, set_global_setting
      event_log.py     ← get_event_log, get_event_summary, clear_event_log, images
    event_logger.py    ← EventLogger class, SQLite write/query, ring buffer
    resources.py       ← MCP resource handlers for capture files
```

New top-level entry point (for Claude Desktop config):
```
screenalert_mcp.py   ← thin launcher: starts engine + MCP server
```

Claude Desktop config (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "screenalert": {
      "command": "python",
      "args": ["C:/path/to/ScreenAlert/screenalert_mcp.py"]
    }
  }
}
```

---

## Implementation Plan

### Phase 1 — Event Logger
**Files:** `screenalert_core/mcp/event_logger.py`

- `EventLogger` class with SQLite backend
- In-memory ring buffer (last N events) for speed, periodic flush to disk
- `log(category, event, source, window_id, window_name, region_id, region_name, detail)` method
- Query method supporting all filters from `get_event_log`
- Hook into engine: instrument `screening_engine.py`, `config_manager.py`, `main_window.py` to emit events at key transition points
- Global setting keys: `event_log_enabled`, `event_log_max_rows`

### Phase 2 — MCP Server Skeleton
**Files:** `screenalert_core/mcp/server.py`, `screenalert_mcp.py`

- stdio-based MCP server using the `mcp` Python package
- Tool registry — each tool is a decorated function
- Engine reference passed in at startup
- Basic `list_tools` / `call_tool` handlers
- Test with Claude Desktop using a single stub tool

### Phase 3 — Window & Region Tools
**Files:** `screenalert_core/mcp/tools/windows.py`, `regions.py`

- Implement all 8 window tools and 6 region tools
- `get_window_settings` / `set_window_setting` with full key validation and runtime apply
- `get_region_settings` / `set_region_setting` with full key validation
- `find_desktop_windows` — wraps existing `window_manager` enumeration

### Phase 4 — Monitoring & Global Settings Tools
**Files:** `screenalert_core/mcp/tools/monitoring.py`, `settings.py`

- Implement pause/resume/mute/status tools
- Implement `get_global_settings` / `set_global_setting` — all keys must apply immediately via `apply_runtime_settings` / `set_runtime_log_level`

### Phase 5 — Event Log & Image Tools
**Files:** `screenalert_core/mcp/tools/event_log.py`, `resources.py`

- Implement `get_event_log`, `get_event_summary`, `clear_event_log`
- Implement `get_alert_image` and `get_alert_diagnostic_images` — read file, return base64 PNG content block
- Implement MCP Resources for the captures directory

### Phase 6 — Integration & Config
- Wire `EventLogger` into all engine/UI callsites
- Add `screenalert_mcp.py` launcher
- Update `RELEASE_NOTES.md`
- Document Claude Desktop setup in `docs/MCP_SETUP.md`

---

## Total Tool Count

| Category | Tools |
|---|---|
| Windows | 8 |
| Regions | 6 |
| Monitoring | 4 |
| Global Settings | 2 |
| Event Log & Images | 5 |
| **Total** | **25** |
