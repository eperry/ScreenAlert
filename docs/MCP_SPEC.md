# ScreenAlert MCP Server — Specification & Implementation Plan

## Overview

An MCP (Model Context Protocol) server embedded directly inside the running ScreenAlert
application. Exposes the full ScreenAlert feature set to Claude Desktop, Claude Code, and
any MCP-compliant client — allowing an AI agent to query status, manage windows and regions,
change settings, and analyze alert captures from a natural language conversation.

The MCP server runs as a daemon thread inside ScreenAlert, listening on a local HTTPS port.
No separate process, no IPC. When ScreenAlert is not running the server is unavailable;
when ScreenAlert starts the server comes up automatically.

---

## Architecture

```text
Claude Desktop / Claude Code / Other MCP Client
        │
        │  HTTPS + Bearer token   localhost:8765/v1  (no internet)
        ▼
┌──────────────────────────────────────────────────┐
│  ScreenAlert (running app)                       │
│                                                  │
│  MCPServer  (daemon thread)                      │
│    ├── /v1/sse          SSE transport            │
│    ├── /v1/mcp          Streamable HTTP          │
│    ├── /v1/skills       Tool introspection       │
│    ├── /v1/health       Health check             │
│    ├── /v1/status       Server diagnostics       │
│    └── /v1/resources/   Capture file browser     │
│         │                                        │
│         ├── ScreenAlertEngine                    │
│         ├── ConfigManager                        │
│         ├── EventLogger  (JSONL)                 │
│         └── CaptureStore (filesystem)            │
└──────────────────────────────────────────────────┘
```

### Startup

The MCP server is started from the ScreenAlert entry point as a daemon thread:

```python
from screenalert_core.mcp.server import MCPServer
mcp_server = MCPServer(engine=engine, config=config, event_logger=event_logger)
mcp_server.start()  # non-blocking
```

---

## Security

### TLS / HTTPS

HTTPS is the **default and only** transport. Plain HTTP is disabled unless explicitly
enabled as a redirect-only listener.

**Self-signed certificate — auto-generated on first startup:**

- Generated using the `cryptography` Python package (**explicit new dependency** — not
  provided by Pillow or any existing transitive dependency; must be added to requirements)
- EC 256-bit key (faster than RSA 2048 for local use)
- Subject Alternative Names: `localhost`, `127.0.0.1`
- Validity: 10 years (local-only cert, no CA rotation needed)
- No private key password
- Stored in the ScreenAlert data directory:

```text
C:/Users/<user>/AppData/Roaming/ScreenAlert/mcp_cert.pem
C:/Users/<user>/AppData/Roaming/ScreenAlert/mcp_key.pem
```

- Regenerated automatically if either file is missing or the cert is expired
- SHA-256 fingerprint shown in Settings > MCP for client-side verification

**HTTP redirect (optional):**

If `mcp_http_redirect` is enabled, a second listener on `mcp_http_port` returns
`301 Moved Permanently` to the HTTPS URL. Disabled by default.

### API Key Authentication

Every request requires a Bearer token in the `Authorization` header:

```text
Authorization: Bearer <api-key>
```

**Key lifecycle:**

- Generated as a random 32-character hex string on first startup (or if missing from config)
- Saved to config as `mcp_api_key`
- Displayed in Settings > MCP with a **Copy** button
- **Regenerate Key** button in Settings rotates immediately; all connected clients disconnect

**Auth failure:** Returns `401 Unauthorized` with standard error body. Logged once at
DEBUG level per unique source address per 60 seconds (to suppress log spam).

### Connection Limits

Maximum concurrent connections: configurable via `mcp_max_connections` (default `5`).
Excess connections receive `429 Too Many Connections`. Limit applies across all clients
combined, not per-client.

---

## Server Endpoints & Versioning

All endpoints are versioned under `/v1/`. Future breaking changes increment the version.

| Endpoint | Method | Description |
| --- | --- | --- |
| `/v1/sse` | GET | SSE transport (MCP 2024-11-05 spec) |
| `/v1/mcp` | POST | Streamable HTTP transport (MCP 2025-03-26 spec) |
| `/v1/skills` | GET | Tool introspection — full schema for all tools |
| `/v1/health` | GET | Returns `{"status":"ok"}` if server is healthy |
| `/v1/status` | GET | Server diagnostics (see below) |
| `/v1/resources/` | GET | HTML file browser for captures directory |
| `/v1/resources/{path}` | GET | Download a specific capture or diagnostic file |

**`/v1/status` response:**

```json
{
  "status": "ok",
  "version": "2.0.7",
  "uptime_seconds": 3600,
  "active_connections": 1,
  "max_connections": 5,
  "cert_fingerprint": "sha256:abcd1234...",
  "cert_expires": "2036-03-27",
  "event_log_enabled": true,
  "event_log_entries": 142,
  "monitoring_state": "running"
}
```

**`/v1/skills` response:**

```json
[
  {
    "name": "list_windows",
    "description": "List all monitored windows with their current state...",
    "parameters": { "filter": { "type": "str", "optional": true } },
    "returns": "[{id, name, status, overlay_visible, hwnd, slot}]"
  }
]
```

---

## Error Handling

All endpoints return errors in a standard JSON format:

```json
{
  "error": "window_id is required",
  "code": 400,
  "field": "window_id"
}
```

| Code | Meaning |
| --- | --- |
| 400 | Bad Request — missing or invalid parameter; `field` indicates which one |
| 401 | Unauthorized — missing or invalid API key |
| 404 | Not Found — unknown window_id, region_id, event_id, or endpoint |
| 409 | Conflict — operation not valid in current state (e.g. add duplicate window) |
| 422 | Unprocessable — parameter value out of valid range; `valid_range` field included |
| 429 | Too Many Connections |
| 500 | Internal Server Error — includes `detail` field with safe error description |

For `set_*` operations that fail validation, the error includes the valid values or range:

```json
{
  "error": "overlay_scaling_mode must be one of: Fit, Stretch, Letterbox",
  "code": 422,
  "field": "value",
  "valid_values": ["Fit", "Stretch", "Letterbox"]
}
```

---

## SSE Event Stream

The `/v1/sse` endpoint delivers a real-time push stream of ScreenAlert events to
connected clients. Events match the Event Log schema exactly — the same JSON objects
that appear in the JSONL file are pushed over SSE as they occur.

### Event format

```text
event: <type>
data: <json-object-on-one-line>

```

### Event types

| Type | When sent | Payload |
| --- | --- | --- |
| `alert` | Region enters or clears alert state | Event log entry |
| `window` | Window connected, disconnected, discovered | Event log entry |
| `region` | Region added, removed, state changed | Event log entry |
| `settings` | Any setting changed | Event log entry |
| `monitoring` | Paused, resumed, muted, unmuted | Event log entry |
| `system` | App started/stopped | Event log entry |
| `mcp` | Tool called | Event log entry |
| `heartbeat` | Every 30 seconds | `{"timestamp":"...", "status":"ok", "monitoring_state":"running"}` |

**Subscription filtering (optional query param):**

```text
GET /v1/sse?categories=alert,window
```

Omitting `categories` delivers all event types.

### Client responsibilities

- Maintain a persistent connection; reconnect automatically on drop
- Use `Last-Event-ID` header on reconnect to resume from last seen event
- Ignore unknown event types for forward compatibility

### Example events

```text
event: alert
data: {"id":"a1b2","timestamp":"2026-03-27T14:32:01.123","category":"alert","event":"region_alert","source":"engine","window_id":"abc","window_name":"EVE - Edward Perry","region_id":"def","region_name":"local-chat","previous_state":"ok","new_state":"alert","capture_file":"C:/captures/2026-03-27_143201.png"}

event: heartbeat
data: {"timestamp":"2026-03-27T14:33:00.000","status":"ok","monitoring_state":"running"}

```

---

## Tool Catalogue

### Coordinate system

All `rect` values use **window client-area coordinates**: pixels measured from the
top-left corner of the window's drawable area (excluding title bar and borders), at
100% DPI scale. For example, `{x:0, y:0, width:100, height:50}` is a 100×50 pixel
region at the top-left of the window's content area, regardless of system DPI scaling.

### Window lookup

All tools that accept `window_id` also accept `window_name` (case-insensitive, partial
match allowed). If both are provided, `window_id` takes precedence. If the name matches
multiple windows, the tool returns a `409` listing the ambiguous matches.

---

### Windows

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `list_windows` | `filter?: str` | `[{id, name, status, overlay_visible, hwnd, slot}]` | List all monitored windows. `status`: `connected`, `disconnected`, `error`. Optional `filter` matches against name. |
| `find_desktop_windows` | `filter?: str`, `limit?: int=50` | `[{hwnd, title, class, size, monitor}]` | Enumerate open desktop windows available to add. `filter` matches title substring. `limit` caps results (max 200). |
| `add_window` | `title: str`, `hwnd?: int` | `{id, name}` | Add a window to monitoring by title. If `hwnd` is provided it is used directly; otherwise ScreenAlert searches by title. |
| `remove_window` | `window_id: str`, `confirm: bool=false` | `{ok: bool, regions_deleted: int}` \| dry-run preview | **Destructive and irreversible.** Deletes the window and all its regions. If `confirm=false`, returns a preview `{name, regions_count}` without deleting. Pass `confirm=true` to execute. |
| `reconnect_window` | `window_id: str` | `{result: "already_valid"\|"reconnected"\|"failed"\|"missing"}` | Force reconnect one window. |
| `reconnect_all_windows` | — | `{total, reconnected, failed, already_valid}` | Force reconnect all disconnected windows. |
| `get_window_settings` | `window_id: str` | `{key: {value, type, description}}` | All configurable settings for a window with current values and types. |
| `set_window_setting` | `window_id: str`, `key: str`, `value: any` | `{ok: bool, error?: str}` | Set any window setting by key. Returns 422 with valid values if value is out of range. |

**Window setting keys:**

| Key | Type | Valid values | Description |
| --- | --- | --- | --- |
| `name` | str | non-empty | Display name / window title |
| `overlay_visible` | bool | — | Whether the overlay is currently shown |
| `opacity` | float | 0.0–1.0 | Overlay opacity |
| `always_on_top` | bool | — | Overlay always on top |
| `show_border` | bool | — | Show border on overlay |
| `window_slot` | int\|null | — | Assigned slot number |
| `enabled` | bool | — | Whether this window is actively monitored |

---

### Regions

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `list_regions` | `window_id?: str` | `[{id, window_id, name, enabled, state, rect}]` | All regions, optionally filtered by window. |
| `add_region` | `window_id: str`, `name: str`, `rect: {x, y, width, height}` | `{id, name}` | Add a region. Coordinates are window client-area pixels (see Coordinate system above). |
| `remove_region` | `region_id: str` | `{ok: bool}` | Remove a region permanently. |
| `copy_region` | `region_id: str`, `target_window_id: str`, `name?: str` | `{id, name}` | Copy a region (with all its alert settings) to another window. `name` defaults to the source region name. Useful for windows with identical layouts. |
| `list_alerts` | — | `[{window_id, window_name, region_id, region_name, since}]` | All currently active (uncleared) alerts. |
| `acknowledge_alert` | `region_id: str` | `{ok: bool}` | Mark an active alert as acknowledged. Clears the alert state and logs an `alert_acknowledged` event. |
| `get_region_settings` | `region_id: str` | `{key: {value, type, description, valid_values?}}` | All configurable settings for a region. |
| `set_region_setting` | `region_id: str`, `key: str`, `value: any` | `{ok: bool, error?: str}` | Set any region setting by key. |

**Region setting keys:**

| Key | Type | Description |
| --- | --- | --- |
| `name` | str | Region display name |
| `rect` | {x, y, width, height} | Position/size in window client-area coordinates |
| `enabled` | bool | Whether this region is actively monitored |
| `tts_message` | str | TTS message template spoken on alert |
| `sound_file` | str | Path to sound file played on alert |
| `sound_enabled` | bool | Sound enabled for this region |
| `tts_enabled` | bool | TTS enabled for this region |
| `alert_hold_seconds` | float | How long alert state is held after trigger |

---

### Monitoring Control

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `pause_monitoring` | — | `{ok: bool}` | Pause region analysis. Overlays stay visible. |
| `resume_monitoring` | — | `{ok: bool}` | Resume region analysis. |
| `mute_alerts` | `seconds: int` (1–3600) | `{muted_until: str (ISO)}` | Mute all alert sounds and TTS. If already muted, **extends** the mute (does not reset). |
| `get_monitoring_status` | — | `{state, muted, mute_remaining_seconds, uptime_seconds, active_windows, active_regions}` | Current state. `state`: `"running"`, `"paused"`, `"stopped"`. |

---

### Global Settings

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `get_global_settings` | — | `{key: {value, type, description, valid_values?}}` | All global settings with metadata. |
| `set_global_setting` | `key: str`, `value: any` | `{ok: bool, error?: str}` | Set a global setting. Applied immediately at runtime — no restart required. |

**Global setting keys:**

| Key | Type | Valid values | Description |
| --- | --- | --- | --- |
| `opacity` | float | 0.0–1.0 | Default overlay opacity |
| `always_on_top` | bool | — | Overlays always on top |
| `show_borders` | bool | — | Show borders on overlays |
| `overlay_scaling_mode` | str | Fit, Stretch, Letterbox | Overlay scaling mode |
| `refresh_rate_ms` | int | 50–5000 | Monitoring loop refresh rate |
| `log_level` | str | TRACE, DEBUG, INFO, WARNING, ERROR | Active log level |
| `show_overlay_when_unavailable` | bool | — | Show placeholder when window unavailable |
| `show_overlay_on_connect` | bool | — | Auto-show overlay on reconnect |
| `alert_hold_seconds` | float | 0–3600 | Default alert hold duration |
| `enable_sound` | bool | — | Global sound toggle |
| `enable_tts` | bool | — | Global TTS toggle |
| `default_tts_message` | str | — | Default TTS template |
| `suppress_fullscreen` | bool | — | Suppress alerts during fullscreen apps |
| `auto_discover` | bool | — | Enable background window discovery |
| `auto_discover_interval_seconds` | int | 10–300 | Discovery scan frequency |
| `size_tolerance_px` | int | 0–500 | Window size match tolerance |
| `capture_on_alert` | bool | — | Save screenshot on alert |
| `save_alert_diagnostics` | bool | — | Save diagnostic images on alert |
| `event_log_enabled` | bool | — | Enable JSONL event logging |
| `event_log_max_rows` | int | 100–100000 | Max entries before pruning (default: 5000) |
| `mcp_max_connections` | int | 1–20 | Max concurrent MCP client connections (default: 5) |

---

### General / Utility

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `ping` | — | `{version, uptime_seconds, cert_fingerprint, monitoring_state}` | Verify connectivity and get basic server info. Good first call for any client. |

---

### Event Log

| Tool | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `get_event_log` | `limit?: int=100`, `offset?: int=0`, `after_id?: str`, `since?: str (ISO)`, `category?: str`, `window_id?: str`, `region_id?: str` | `{events: [...], total: int, has_more: bool}` | Query event log with filters. Use `after_id` for cursor-based polling or `offset` for paging. |
| `get_event_summary` | `since?: str (ISO)` | `{counts_by_category, counts_by_event, counts_by_window, alerts_with_captures, total}` | Aggregated counts including per-window breakdown. |
| `clear_event_log` | `category?: str` | `{entries_deleted: int}` | Clear all or one category. The clear action itself is logged as a `system` event before deletion. |
| `get_alert_image` | `event_id?: str`, `window_id?: str`, `region_id?: str` | image (base64 PNG) | Return capture screenshot. Pass `event_id` for a specific alert, or `window_id`+`region_id` for the most recent capture for that region. `max_width` resizes before encoding (default: 1920px, max: original). |
| `get_alert_diagnostic_images` | `event_id: str` | `[{filename, image (base64 PNG)}]` | All diagnostic images for an alert event. |

**`get_alert_image` parameters:**

| Parameter | Type | Description |
| --- | --- | --- |
| `event_id` | str \| null | Specific alert event ID |
| `window_id` | str \| null | Used with `region_id` to get latest capture |
| `region_id` | str \| null | Used with `window_id` to get latest capture |
| `max_width` | int | Resize image to this width before encoding (default: 1920) |

---

## MCP Prompts

MCP Prompts are pre-built conversation starters that appear in the Claude Desktop UI
(and any client that supports MCP prompts). They let users trigger common workflows
with one click.

| Prompt name | Arguments | Description |
| --- | --- | --- |
| `analyse_alert_history` | `since?: str`, `window_name?: str` | Asks Claude to summarise and interpret recent alert activity |
| `what_needs_attention` | — | Asks Claude to check all windows and regions and report anything that looks wrong |
| `show_recent_captures` | `window_name?: str` | Asks Claude to retrieve and show recent alert screenshots |
| `diagnose_window` | `window_name: str` | Asks Claude to check a specific window's connection, regions, and recent history |
| `daily_summary` | — | Asks Claude to produce a full activity report for the current day |

---

## Event Log Schema

### Storage — JSONL (newline-delimited JSON)

```text
C:/Users/<user>/AppData/Roaming/ScreenAlert/event_log.jsonl
```

One JSON object per line, appended on every event. Python `json` stdlib only — no
database dependency.

- **Append-only** — no lock contention, no rewrite on every event
- **Schemaless** — each event carries whatever fields are relevant
- **Rotation** — when entries exceed `event_log_max_rows` (default 5000), a full
  rewrite trims the oldest entries. This is infrequent and happens on a background thread.
- **Flush interval** — in-memory buffer flushed to disk every 5 seconds or when buffer
  reaches 50 events, whichever comes first.

### Minimum required fields

Every event **must** have these five fields. Everything else is free-form:

| Field | Type | Description |
| --- | --- | --- |
| `id` | str (uuid4) | Unique event identifier |
| `timestamp` | str (ISO 8601) | When the event occurred |
| `category` | str | `alert`, `window`, `region`, `settings`, `monitoring`, `system`, `mcp` |
| `event` | str | Specific event name within the category |
| `source` | str | `engine`, `user`, `auto_discovery`, `mcp`, `system` |

### Known event names (non-exhaustive)

| Category | Event | Typical extra fields |
| --- | --- | --- |
| `alert` | `region_alert` | `window_id`, `window_name`, `region_id`, `region_name`, `previous_state`, `new_state`, `capture_file?`, `diagnostic_files?` |
| `alert` | `region_cleared` | `window_id`, `region_id`, `previous_state`, `new_state` |
| `alert` | `alert_acknowledged` | `window_id`, `region_id` |
| `alert` | `alert_suppressed` | `window_id`, `region_id`, `reason` (fullscreen \| muted) |
| `window` | `window_added` | `window_id`, `window_name`, `hwnd` |
| `window` | `window_removed` | `window_id`, `window_name`, `regions_deleted` |
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
| `region` | `region_copied` | `source_region_id`, `new_region_id`, `target_window_id` |
| `region` | `region_state_changed` | `window_id`, `region_id`, `from`, `to` |
| `settings` | `setting_changed` | `key`, `old_value`, `new_value`, `scope` (global \| window \| region), `window_id?`, `region_id?` |
| `monitoring` | `monitoring_started` | — |
| `monitoring` | `monitoring_paused` | — |
| `monitoring` | `monitoring_resumed` | — |
| `monitoring` | `alerts_muted` | `duration_seconds`, `muted_until` |
| `monitoring` | `alerts_unmuted` | — |
| `system` | `app_started` | `version` |
| `system` | `app_stopped` | — |
| `system` | `event_log_cleared` | `category?`, `entries_deleted` |
| `mcp` | `tool_called` | `tool`, `args`, `result_status`, `duration_ms` |
| `mcp` | `client_connected` | `remote_addr` |
| `mcp` | `client_disconnected` | `remote_addr` |

### Capture linkage

Alert events include capture references as top-level fields. Fields are **omitted** (not
null) when capture is disabled:

```json
{
  "id": "a1b2c3",
  "timestamp": "2026-03-27T14:32:01.123",
  "category": "alert",
  "event": "region_alert",
  "source": "engine",
  "window_id": "abc",
  "window_name": "EVE - Edward Perry",
  "region_id": "def",
  "region_name": "local-chat",
  "previous_state": "ok",
  "new_state": "alert",
  "capture_file": "C:/captures/2026-03-27_143201_edward-perry_local-chat.png",
  "diagnostic_files": [
    "C:/captures/diag/2026-03-27_143201_window.png",
    "C:/captures/diag/2026-03-27_143201_edges.png"
  ]
}
```

Images are saved **before** the log entry is written so paths are always valid.

---

## MCP Resources

The MCP server exposes the captures directory as browsable MCP resources:

```text
screenalert://captures/{filename}
screenalert://captures/diag/{filename}
```

`list_resources` and `read_resource` follow the standard MCP protocol. Claude Desktop
shows these in its sidebar.

The `/v1/resources/` HTTP endpoint provides a simple read-only HTML file browser for
the same files — useful for non-MCP clients and direct browser access.

---

## Settings Summary

All MCP-related settings are configurable in Settings > MCP and via `set_global_setting`:

| Key | Default | Description |
| --- | --- | --- |
| `mcp_enabled` | `true` | Start MCP server with the app |
| `mcp_port` | `8765` | HTTPS listener port |
| `mcp_api_key` | auto-generated | Bearer token for all connections |
| `mcp_ssl_cert_path` | auto | TLS cert PEM path (auto-generated if absent/expired) |
| `mcp_ssl_key_path` | auto | TLS key PEM path |
| `mcp_http_redirect` | `false` | Enable HTTP→HTTPS redirect listener |
| `mcp_http_port` | `8766` | Port for the HTTP redirect listener |
| `mcp_max_connections` | `5` | Max concurrent client connections |
| `event_log_enabled` | `true` | Enable JSONL event logging |
| `event_log_max_rows` | `5000` | Max log entries before oldest are pruned |

---

## Client Configuration Examples

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "screenalert": {
      "url": "https://localhost:8765/v1/sse",
      "headers": {
        "Authorization": "Bearer YOUR_KEY_HERE"
      }
    }
  }
}
```

**Claude Code** (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "screenalert": {
      "url": "https://localhost:8765/v1/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer YOUR_KEY_HERE"
      }
    }
  }
}
```

**Other clients:** Use `https://localhost:8765/v1/sse`. If the client rejects
self-signed certs, either trust `mcp_cert.pem` in the system/client trust store,
or use the client's equivalent of `insecure: true`. The API key provides the actual
access control.

---

## File Structure

```text
screenalert_core/
  mcp/
    __init__.py
    server.py          ← MCPServer class, HTTP/SSE/Streamable listeners, middleware
    tls.py             ← ensure_cert() — auto-generates EC256 self-signed cert
    event_logger.py    ← EventLogger class, JSONL write/query, ring buffer
    resources.py       ← MCP resource handlers and /v1/resources/ HTTP browser
    tools/
      __init__.py
      windows.py       ← list_windows, find_desktop_windows, add_window, remove_window, ...
      regions.py       ← list_regions, add_region, remove_region, copy_region, ...
      monitoring.py    ← pause, resume, mute, get_status
      settings.py      ← get_global_settings, set_global_setting
      event_log.py     ← get_event_log, get_event_summary, clear_event_log
      images.py        ← get_alert_image, get_alert_diagnostic_images
      utility.py       ← ping
    prompts/
      __init__.py
      definitions.py   ← MCP prompt templates
```

---

## Dependencies

New dependency required (not currently in the project):

| Package | Version | Purpose |
| --- | --- | --- |
| `mcp[cli]` | ≥1.0 | MCP server protocol implementation |
| `cryptography` | ≥42.0 | EC256 TLS certificate generation |

---

## Implementation Plan

### Phase 1 — Event Logger

**Files:** `screenalert_core/mcp/event_logger.py`

- `EventLogger` class with JSONL backend
- In-memory ring buffer; flush to disk every 5 seconds or every 50 events
- `log(category, event, source, **kwargs)` — accepts free-form keyword args beyond the 5 required fields
- Query method: filters by category, window_id, region_id, since (ISO), after_id, limit, offset
- `get_summary(since)` — counts by category, event, and window
- Rotation: background thread trims oldest rows when max exceeded
- Add `event_log_enabled` and `event_log_max_rows` to config defaults
- Instrument `screening_engine.py`, `config_manager.py`, `main_window.py` at all key transition points

### Phase 2 — MCP Server Skeleton

**Files:** `screenalert_core/mcp/server.py`, `screenalert_core/mcp/tls.py`

- `tls.py`: `ensure_cert(cert_path, key_path)` — EC256, SANs localhost+127.0.0.1, 10yr, no password
- `MCPServer` class with `start()` / `stop()` — daemon thread, HTTPS listener
- API key middleware: validates Bearer token on every request; 401 on mismatch
- Connection limit middleware: 429 when `mcp_max_connections` exceeded
- Auth failure rate-limited logging (once per source address per 60s)
- Both `/v1/sse` and `/v1/mcp` endpoints
- `/v1/health`, `/v1/status` endpoints
- Optional HTTP redirect listener
- Tool registry: decorated functions, auto-registered with `/v1/skills`
- Test stub: `ping` tool verified in Claude Desktop

### Phase 3 — Window & Region Tools

**Files:** `screenalert_core/mcp/tools/windows.py`, `regions.py`

- All 8 window tools including `remove_window` dry-run/confirm pattern
- All 8 region tools including `copy_region` and `acknowledge_alert`
- `window_id` OR `window_name` lookup on all relevant tools
- `get_window_settings` / `set_window_setting` with full validation and 422 responses
- `get_region_settings` / `set_region_setting` with full validation
- `find_desktop_windows` with `filter` and `limit` params

### Phase 4 — Monitoring & Global Settings Tools

**Files:** `screenalert_core/mcp/tools/monitoring.py`, `settings.py`, `utility.py`

- `pause`, `resume`, `mute` (extend-not-reset behaviour), `get_monitoring_status`
- `get_global_settings` / `set_global_setting` — immediate runtime apply
- `ping` tool returning version + cert fingerprint + state

### Phase 5 — Event Log & Image Tools

**Files:** `screenalert_core/mcp/tools/event_log.py`, `images.py`, `resources.py`

- `get_event_log` with cursor (`after_id`) and offset pagination
- `get_event_summary` with per-window counts
- `clear_event_log` — logs the clear action before deleting
- `get_alert_image` — by event_id or window_id+region_id; `max_width` resize
- `get_alert_diagnostic_images` — returns list with filenames
- MCP Resources for captures directory
- `/v1/resources/` HTML browser

### Phase 6 — MCP Prompts

**Files:** `screenalert_core/mcp/prompts/definitions.py`

- Implement all 5 prompt templates
- Register with MCP server prompt registry

### Phase 7 — UI Integration

**Files:** `screenalert_core/ui/main_window.py`, `screenalert_core/ui/settings_dialog.py`

**Main window bottom bar — MCP toggle button:**

- `● MCP` green — running and accepting connections
- `○ MCP` grey — disabled
- `⚠ MCP` amber — failed to start (port in use, cert error, etc.)
- Click toggles `mcp_enabled` live; tooltip shows state + port + active connection count

**Settings > MCP panel:**

All settings from the Settings Summary table, plus:

- API Key: read-only field + **Copy** button
- **Regenerate Key** button
- Certificate Fingerprint: read-only field
- **Regenerate Certificate** button (restarts listener)

### Phase 8 — Integration & Docs

- Wire `EventLogger` into all engine/UI callsites
- Add `cryptography` and `mcp[cli]` to `requirements.txt`
- Update `RELEASE_NOTES.md`
- Write `docs/MCP_SETUP.md` — setup guide for Claude Desktop, Claude Code, generic clients

---

## Total Tool Count

| Category | Tools |
| --- | --- |
| Windows | 8 |
| Regions | 8 |
| Monitoring | 4 |
| Global Settings | 2 |
| Utility | 1 |
| Event Log & Images | 5 |
| **Total** | **28** |
