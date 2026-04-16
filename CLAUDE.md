# ScreenAlert Development Guide

## Current Branch: RC-2.0.8

### Purpose
Interface with **llama.cpp** (local language model server) to add intelligent keystroke and mouse action automation based on in-game events and chat monitoring.

### New Feature: Automated Fleet Response System
This branch introduces a new automation capability:

1. **Chat Monitoring & Analysis**
   - Monitor the in-game local chat for new players
   - Use llama.cpp to analyze chat and detect unsafe/unknown players
   - Identify when non-whitelisted players enter the monitored system

2. **Keystroke Simulation**
   - Send keystrokes (e.g., D-Scan hotkey) with **human-like variable timing**
   - Delay range: 0.5 to 3 seconds between actions
   - Prevents detection as bot by randomizing action intervals

3. **Region Monitoring & Change Detection**
   - Monitor a specific UI region (e.g., D-Scan results window)
   - Detect new objects/ships in scan results
   - Trigger conditional actions based on scan findings

4. **Conditional Mouse Actions**
   - If threat detected (new ship in scan) → execute warp command
   - If safe → continue current operation
   - Example: Eve Online mining fleet detection → warp to safe bookmark

### Real-World Example: Eve Online Mining Fleet
```
Scenario: Mining operation with AFK fleet in anomaly

1. Unknown player appears in system local chat
2. llama.cpp analyzes message → marks as "potential threat"
3. Fleet owner's app automatically:
   a. Sends D-Scan hotkey (with 1-2 sec random delay)
   b. Waits for D-Scan window to populate
   c. Monitors D-Scan region for new ship contacts
   d. If ships detected → sends warp command to safe bookmark
   e. Fleet warps away before engagement
```

---

## Project Structure

### Core Directories
- **`screenalert_core/`** — Main application logic
  - `screening_engine.py` — Alert detection and region monitoring
  - `ui/main_window.py` — UI and status display
  - `core/config_manager.py` — Configuration persistence

- **`screenalert_core/mcp/`** — MCP Server (AI integration)
  - `server.py` — MCP server implementation
  - `tools/` — Tool implementations for external AI clients
  - `event_logger.py` — Event logging for audit trail

- **`screenalert_core/rendering/`** — Overlay and window rendering
  - `overlay_window.py` — Native Win32 overlay windows
  - `overlay_manager.py` — Overlay lifecycle management

- **`docs/`** — Documentation
  - `RELEASE_NOTES.md` — Version history and features
  - `MCP_SETUP.md` — MCP server setup guide
  - `ARCHITECTURE.md` — System architecture reference

- **`tests/`** — Automated tests
  - `test_mcp_tools.py` — MCP tool test suite (84 tests)

---

## Key Features (v2.0.7+)

### MCP Server Integration
- 28 MCP tools for external AI client control
- SSE and Streamable HTTP transports
- HTTPS with auto-generated self-signed certs
- Bearer token authentication

### Config File Structure
Three separate JSON files for different concerns:
- `screenalert_config.json` — App settings (monitoring, audio, appearance)
- `screenalert_windows_regions.json` — Window and region definitions
- `mcp_config.json` — MCP server settings (auto-managed)

### DWM Overlay System
- Hardware-composited DWM thumbnails (DirectShow replacement)
- Native Win32 overlay windows with high FPS
- Supports Fit/Stretch/Letterbox scaling modes
- Click-to-interact, drag to move, resize with right-click

### Region Monitoring
- SSIM-based change detection
- Alert triggering on threshold breach
- Per-region sensitivity and debounce settings

---

## RC-2.0.8 Development Tasks

### Phase 1: llama.cpp Integration
- [ ] Add llama.cpp client library to requirements
- [ ] Create `screenalert_core/llm/llama_client.py` for model interaction
- [ ] Implement chat message parsing and analysis
- [ ] MCP tool: `analyze_chat_message(message: str) → {"threat_level": str, "confidence": float}`

### Phase 2: Keystroke & Mouse Automation
- [ ] Create `screenalert_core/automation/keystroke_simulator.py`
  - Variable timing (0.5–3 sec configurable range)
  - Human-like randomization
  - Keystroke queuing system
- [ ] Create `screenalert_core/automation/mouse_action.py`
  - Mouse movement and click simulation
  - Coordinate tracking relative to regions
- [ ] MCP tools: `send_keystroke()`, `send_mouse_action()`

### Phase 3: Region-Triggered Actions
- [ ] Extend region monitoring to support action triggers
- [ ] Add config key: `region.on_alert_action` (keystroke or mouse action)
- [ ] Implement action execution on alert
- [ ] Settings UI: "Action on Alert" configuration

### Phase 4: Testing & Documentation
- [ ] Add tests for keystroke simulator (timing accuracy)
- [ ] Add tests for action trigger logic
- [ ] Update `docs/RELEASE_NOTES.md` with new features
- [ ] Create `docs/LLAMA_INTEGRATION.md` setup guide

---

## Configuration Example

New settings to add to `screenalert_config.json`:

```json
{
  "automation_enabled": true,
  "llm_enabled": true,
  "llm_model_name": "orca-mini",
  "llm_api_url": "http://127.0.0.1:8000/v1",
  "keystroke_min_delay_ms": 500,
  "keystroke_max_delay_ms": 3000,
  "chat_analysis_enabled": true,
  "chat_threat_threshold": 0.7,
  "regions": [
    {
      "name": "DSCAN_Window",
      "window_title": "D-Scan Results",
      "bounds": [100, 100, 400, 300],
      "on_alert_action": {
        "type": "keystroke",
        "key": "w",
        "delay_ms": 1000
      }
    }
  ]
}
```

---

## MCP Tools to Implement

### llama.cpp Integration
- `analyze_chat_message(message: str)` → `{"threat_level": "low|medium|high", "confidence": 0.0–1.0}`
- `get_llm_status()` → connection status and model info

### Keystroke & Mouse Automation
- `send_keystroke(key: str, delay_ms: int = 500)`
- `send_mouse_click(x: int, y: int, button: str = "left")`
- `send_mouse_move(x: int, y: int, duration_ms: int = 500)`
- `queue_action_sequence(actions: List[Dict])` → execute multi-step automation

### Region Automation
- `set_region_action(region_id: str, action: Dict)` — assign action to region
- `get_automation_status()` → active keystroke/mouse operations

---

## Development Workflow

### Before Committing
1. **Update RELEASE_NOTES.md** with changes
2. **Run tests**: `pytest tests/test_mcp_tools.py -v`
3. **Check MCP tools**: Ensure new tools are registered in `server.py`
4. **Test llama.cpp integration**: Verify local model connection

### Commit Message Format
```
[Feature/Fix] Brief description

- Bullet point 1
- Bullet point 2

Relates to: RC-2.0.8 llama.cpp integration
```

### Release Process (when ready)
1. Merge RC-2.0.8 → main
2. Create tag: `git tag -a 2.0.8 -m "Release 2.0.8: llama.cpp integration, keystroke automation"`
3. Push both branch and tag
4. Create GitHub release with RELEASE_NOTES.md content

---

## Key Files Reference

| File | Purpose |
| --- | --- |
| `screenalert.py` | Entry point, CLI args, main loop |
| `screenalert_core/screening_engine.py` | Alert detection, region monitoring |
| `screenalert_core/core/config_manager.py` | Config I/O and validation |
| `screenalert_core/mcp/server.py` | MCP server startup and tool registration |
| `screenalert_core/mcp/tools/` | Tool implementations (windows, regions, monitoring, etc.) |
| `screenalert_core/ui/main_window.py` | UI, status bar, settings dialog |
| `tests/test_mcp_tools.py` | MCP test suite (mock + live modes) |
| `docs/RELEASE_NOTES.md` | **Update this with new features** |

---

## Testing

### Run MCP Tests
```bash
# Mock mode (no external service needed)
pytest tests/test_mcp_tools.py -v

# Live mode (requires running ScreenAlert on port 8443)
pytest tests/test_mcp_tools.py -v --live
```

### Test Keystroke Simulator
```bash
pytest tests/test_keystroke_simulator.py -v
```

### Manual Testing Checklist
- [ ] llama.cpp connects and analyzes messages
- [ ] Keystroke timing falls within 0.5–3 sec range
- [ ] Region alerts trigger actions correctly
- [ ] Mouse/keystroke actions execute in order
- [ ] MCP tools report correct automation status

---

## References & Resources

- **MCP Protocol**: Model Context Protocol specification
- **llama.cpp**: https://github.com/ggerganov/llama.cpp
- **Eve Online D-Scan**: In-game directional scan mechanic (example use case)
- **Win32 Keybd_Event**: Native keystroke simulation API
- **Win32 Mouse_Event**: Native mouse simulation API

---

## Notes for Claude

- **Branch Purpose**: RC-2.0.8 is specifically for llama.cpp integration and keystroke/mouse automation
- **Human Behavior**: All keystroke/mouse timing must include randomization to avoid detection as automated
- **Config Safety**: Automation features should default to `disabled` until explicitly enabled by user
- **Audit Trail**: All automation actions should be logged via `EventLogger` for debugging
- **MCP Integration**: New tools must be registered in `server.py` and added to `tools/__init__.py`
- **Documentation**: Keep RELEASE_NOTES.md in sync as features are added
