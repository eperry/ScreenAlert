# ScreenAlert MCP Server — Client Setup Guide

The ScreenAlert MCP server runs automatically when ScreenAlert starts (if enabled).
It exposes all ScreenAlert features as MCP tools to any compatible client.

---

## Prerequisites

1. ScreenAlert 2.0.7 or later must be running.
2. The MCP toggle in the status bar must show **MCP: On**.
3. You need the **API key** shown in **Settings → MCP Server → (key is saved in config)**.

---

## Finding Your API Key

The API key is generated automatically on first start and saved to your config file.
To retrieve it:

```text
C:\Users\<YourName>\AppData\Roaming\ScreenAlert\screenalert_config.json
```

Open the file and look for `"mcp_api_key"`. Copy the 64-character hex string.

Alternatively, you can read it directly:

```powershell
(Get-Content "$env:APPDATA\ScreenAlert\screenalert_config.json" | ConvertFrom-Json).app.mcp_api_key
```

---

## TLS / Certificate

The server uses a self-signed TLS certificate. All MCP clients must be configured to
trust it or skip verification.

The certificate is stored at:

```text
C:\Users\<YourName>\AppData\Roaming\ScreenAlert\mcp_cert.pem
```

The SHA-256 fingerprint is shown in the `/v1/status` response.

---

## Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "ScreenAlert": {
      "url": "https://localhost:8765/v1/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key-here>"
      }
    }
  }
}
```

> **TLS note:** Claude Desktop may warn about the self-signed certificate.
> If you see a connection error, verify the URL uses `https://` and the port matches
> your `mcp_port` setting (default `8765`).

### Claude Code (CLI)

```bash
claude mcp add ScreenAlert \
  --transport sse \
  --url "https://localhost:8765/v1/sse" \
  --header "Authorization: Bearer <your-api-key-here>"
```

Or add to your project's `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "ScreenAlert": {
      "transport": "sse",
      "url": "https://localhost:8765/v1/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key-here>"
      }
    }
  }
}
```

### Generic MCP Client (Streamable HTTP)

For clients that support MCP 2025-03-26 Streamable HTTP transport:

```text
POST https://localhost:8765/v1/mcp
Authorization: Bearer <your-api-key-here>
Content-Type: application/json
```

### OpenClaw / Other Clients

Any client that supports MCP over SSE or Streamable HTTP can connect using:

- **SSE endpoint:** `https://localhost:8765/v1/sse`
- **HTTP endpoint:** `https://localhost:8765/v1/mcp`
- **Auth:** `Authorization: Bearer <api-key>`
- **TLS:** Self-signed cert — configure your client to trust or skip verification

---

## Verifying Connectivity

### Health check (no auth required)

```bash
curl -k https://localhost:8765/v1/health
# {"status":"ok"}
```

### Status (auth required)

```bash
curl -k https://localhost:8765/v1/status \
  -H "Authorization: Bearer <your-api-key>"
```

Expected response:

```json
{
  "status": "ok",
  "version": "2.0.7",
  "uptime_seconds": 120,
  "active_connections": 0,
  "max_connections": 5,
  "cert_fingerprint": "sha256:abcd1234...",
  "cert_expires": "2036-03-27",
  "event_log_enabled": true,
  "monitoring_state": "running"
}
```

### Tool introspection

```bash
curl -k https://localhost:8765/v1/skills \
  -H "Authorization: Bearer <your-api-key>"
```

---

## Available Tools (28 total)

| Category | Tools |
| --- | --- |
| Utility | `ping` |
| Windows | `list_windows`, `find_desktop_windows`, `add_window`, `remove_window`, `reconnect_window`, `reconnect_all_windows`, `get_window_settings`, `set_window_setting` |
| Regions | `list_regions`, `add_region`, `remove_region`, `copy_region`, `list_alerts`, `acknowledge_alert`, `get_region_settings`, `set_region_setting` |
| Monitoring | `pause_monitoring`, `resume_monitoring`, `mute_alerts`, `get_monitoring_status` |
| Settings | `get_global_settings`, `set_global_setting` |
| Event Log | `get_event_log`, `get_event_summary`, `clear_event_log` |
| Images | `get_alert_image`, `get_alert_diagnostic_images` |

## Available Prompts (5 total)

| Prompt | Description |
| --- | --- |
| `analyse_alert_history` | Summarise and interpret recent alert activity |
| `what_needs_attention` | Check all windows and report anything wrong |
| `show_recent_captures` | Retrieve and show recent alert screenshots |
| `diagnose_window` | Full diagnosis of a specific window |
| `daily_summary` | Activity report for today |

---

## Capture File Browser

Navigate to `https://localhost:8765/v1/resources/` in a browser (after adding the
API key as a query parameter or using a browser extension) to browse capture files.

Direct file access: `https://localhost:8765/v1/resources/<relative-path>`

---

## Settings Reference

| Setting | Default | Description |
| --- | --- | --- |
| `mcp_enabled` | `true` | Enable/disable the MCP server |
| `mcp_port` | `8765` | HTTPS port |
| `mcp_api_key` | *(auto)* | Bearer token (auto-generated, 64 hex chars) |
| `mcp_max_connections` | `5` | Max simultaneous connections |
| `mcp_http_redirect` | `false` | Redirect plain HTTP to HTTPS |
| `mcp_http_port` | `8766` | Port for the HTTP redirect listener |

All settings can be changed in **Settings → MCP Server** or via `set_global_setting`.

---

## Troubleshooting

**Connection refused:** ScreenAlert is not running, or MCP is disabled.
Check the status bar — it should show **MCP: On**.

**401 Unauthorized:** API key is wrong. Re-read it from the config file.

**TLS error / certificate verify failed:** Your client is rejecting the self-signed cert.
Configure it to skip verification (`verify: false` or `--insecure`), or import the cert.

**429 Too Many Connections:** Too many clients connected simultaneously.
Increase `mcp_max_connections` in Settings or disconnect idle clients.

**Port conflict:** Another app is using port 8765. Change `mcp_port` in Settings and
restart ScreenAlert.
