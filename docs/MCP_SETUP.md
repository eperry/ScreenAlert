# ScreenAlert MCP Server — Setup Guide

The ScreenAlert MCP server runs automatically when ScreenAlert starts (if enabled).
It exposes all ScreenAlert features as MCP tools to any compatible AI client — Claude Desktop,
Claude Code CLI, or any other MCP-compatible application.

---

## Prerequisites

1. ScreenAlert 2.0.7 or later must be running.
2. The MCP toggle in the status bar must show **MCP: On**.
3. You need the **API key** and **server URL** — both are available in **Help → MCP Server…**.

---

## Finding Your API Key and Server URL

### Easiest method — Help menu

Open **Help → MCP Server…** in the ScreenAlert menu bar. The dialog shows:

- Server status (running / stopped)
- Listen address and port
- Clickable links to open the health check and SSE endpoint in a browser
- The bearer token with a **Copy** button

Copy the token from this dialog and paste it into your client configuration.

### Manual method — config file

The API key is saved in:

```text
C:\Users\<YourName>\AppData\Roaming\ScreenAlert\mcp_config.json
```

Look for `"mcp_api_key"`. Copy the 64-character hex string.

To read it from PowerShell:

```powershell
(Get-Content "$env:APPDATA\ScreenAlert\mcp_config.json" | ConvertFrom-Json).mcp_api_key
```

---

## TLS / Certificate

The server uses a self-signed TLS certificate generated automatically on first start.
All clients must be configured to trust it or skip certificate verification.

The certificate is stored at:

```text
C:\Users\<YourName>\AppData\Roaming\ScreenAlert\mcp_cert.pem
```

The SHA-256 fingerprint is shown in the `/v1/status` response and in the **Help → MCP Server…** dialog.

---

## Client Configuration

### Claude Desktop

Locate (or create) `claude_desktop_config.json`:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

Add a `mcpServers` entry:

```json
{
  "mcpServers": {
    "ScreenAlert": {
      "url": "https://localhost:8443/v1/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key-here>"
      }
    }
  }
}
```

Replace `<your-api-key-here>` with the key from **Help → MCP Server…**.

> **TLS note:** Claude Desktop connects over HTTPS with a self-signed certificate.
> If you see a TLS error, verify the URL uses `https://` and the port matches your
> `mcp_port` setting (default `8443`).

After saving the config, restart Claude Desktop. ScreenAlert should appear in the tools panel.

### Claude Code (CLI)

Add the server once using the CLI:

```bash
claude mcp add ScreenAlert \
  --transport sse \
  --url "https://localhost:8443/v1/sse" \
  --header "Authorization: Bearer <your-api-key-here>"
```

Or add it manually to your project's `.mcp.json` (project-scoped) or
`~/.claude/mcp.json` (user-scoped):

```json
{
  "mcpServers": {
    "ScreenAlert": {
      "transport": "sse",
      "url": "https://localhost:8443/v1/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key-here>"
      }
    }
  }
}
```

> **TLS note:** Claude Code will warn about the self-signed certificate. You may need to
> set `NODE_TLS_REJECT_UNAUTHORIZED=0` in the shell where Claude Code runs, or import
> `mcp_cert.pem` into the system trust store.

### Other MCP Clients (SSE)

Any client that supports MCP over SSE (protocol version 2024-11-05) can connect:

- **SSE endpoint:** `https://localhost:8443/v1/sse`
- **Auth header:** `Authorization: Bearer <api-key>`
- **TLS:** Self-signed cert — configure your client to skip verification or trust the cert

---

## Verifying Connectivity

### Health check (no auth required)

```bash
curl -k https://localhost:8443/v1/health
# Expected: {"status":"ok"}
```

### Status (auth required)

```bash
curl -k https://localhost:8443/v1/status \
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

### List available tools

```bash
curl -k https://localhost:8443/v1/skills \
  -H "Authorization: Bearer <your-api-key>"
```

---

## Available Tools (28 total)

| Category | Tools |
| --- | --- |
| Utility | `ping` |
| Windows (8) | `list_windows`, `find_desktop_windows`, `add_window`, `remove_window`, `reconnect_window`, `reconnect_all_windows`, `get_window_settings`, `set_window_setting` |
| Regions (8) | `list_regions`, `add_region`, `remove_region`, `copy_region`, `list_alerts`, `acknowledge_alert`, `get_region_settings`, `set_region_setting` |
| Monitoring (4) | `pause_monitoring`, `resume_monitoring`, `mute_alerts`, `get_monitoring_status` |
| Settings (2) | `get_global_settings`, `set_global_setting` |
| Event Log (3) | `get_event_log`, `get_event_summary`, `clear_event_log` |
| Images (2) | `get_alert_image`, `get_alert_diagnostic_images` |

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

Navigate to `https://localhost:8443/v1/resources/` in a browser to browse captured alert images.

Direct file access: `https://localhost:8443/v1/resources/<relative-path>`

The **Browse** link in **Help → MCP Server…** opens this URL directly.

---

## Settings Reference

All settings are configurable in **Settings → MCP Server** or via the `set_global_setting` tool.

| Setting | Default | Description |
| --- | --- | --- |
| `mcp_enabled` | `true` | Enable/disable the MCP server |
| `mcp_listen_host` | `127.0.0.1` | IP address to bind to. Use `0.0.0.0` to accept connections from other machines on the network |
| `mcp_port` | `8443` | HTTPS listen port |
| `mcp_max_connections` | `5` | Maximum simultaneous client connections |
| `mcp_http_redirect` | `false` | Enable plain HTTP → HTTPS redirect listener |
| `mcp_http_port` | `8080` | Port for the HTTP redirect listener |

The following are managed automatically and not shown in the UI:

| Setting | Description |
| --- | --- |
| `mcp_api_key` | Bearer token (auto-generated 64-char hex, stored in `mcp_config.json`) |
| `mcp_ssl_cert_path` | Path to the auto-generated TLS certificate |
| `mcp_ssl_key_path` | Path to the auto-generated TLS private key |

### Config files

ScreenAlert stores configuration across three separate files in `%APPDATA%\ScreenAlert\`:

| File | Contents |
| --- | --- |
| `screenalert_config.json` | App settings (monitoring, audio, appearance, logging, UI state) |
| `screenalert_windows_regions.json` | Window and region definitions |
| `mcp_config.json` | All MCP settings (connection, auth, TLS) |

---

## Remote Access (LAN)

By default the server only accepts connections from `127.0.0.1` (this machine).
To allow connections from other machines on your local network:

1. Open **Settings → MCP Server → Listen Address**
2. Change the value to `0.0.0.0`
3. Restart the MCP server (click **MCP: On** to toggle off, then on)

Then update your client config to use the machine's LAN IP instead of `localhost`.

> Keep `mcp_listen_host = 127.0.0.1` unless you specifically need remote access.
> Even with TLS and bearer auth, exposing the server on `0.0.0.0` means any
> machine on your network can attempt connections.

---

## Troubleshooting

**Connection refused:** ScreenAlert is not running, or MCP is disabled.
Check the status bar — it should show **MCP: On**. Click to toggle if needed.

**401 Unauthorized:** API key is wrong or missing.
Re-copy it from **Help → MCP Server…** or from `mcp_config.json`.

**TLS error / certificate verify failed:** Your client is rejecting the self-signed cert.
Configure the client to skip verification (`verify: false` / `--insecure`), or import `mcp_cert.pem` into the system or client trust store.

**Too many connections (connection error after many requests):** The `mcp_max_connections` limit (default 5) is reached. Disconnect idle clients or increase the limit in **Settings → MCP Server**.

**Port conflict:** Another application is using port 8443. Change `mcp_port` in **Settings → MCP Server** and restart ScreenAlert.

**Wrong host in client config:** If you changed `mcp_listen_host` from the default, your client URL must match. `127.0.0.1` and `localhost` resolve the same way for most clients — if in doubt, use `127.0.0.1` explicitly.
