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

## llama.cpp Setup & Configuration

### Binary Location

- **Path**: `llama-cpp-binary/` (9GB directory with all executables and DLLs)
- **Key Executable**: `llama-server.exe` — OpenAI-compatible API server
- **Available Tools**: llama-cli, llama-bench, llama-quantize, and more

### Recommended Model: Phi-3 Mini (3.8B)

**Why Phi-3 Mini?**

- Optimized for 8GB VRAM systems (even with Mistral as backup)
- Fast inference (100-200ms per response) → critical for keystroke timing
- Excellent at classification tasks (detecting threats in chat)
- Smaller model = less latency = faster automation triggers

**VRAM Requirements:**

- Q5_K_M quantization: ~4GB VRAM (recommended for quality + speed)
- Q4_K_M quantization: ~3.5GB VRAM (if VRAM-constrained)
- Q6_K quantization: ~5GB VRAM (best quality, slower)

### llama.cpp Server Startup

**Command to start the server (using standard Ollama port 11434):**

```bash
cd llama-cpp-binary
llama-server.exe --model <path-to-model> \
  --ctx-size 2048 \
  --port 11434 \
  --host 127.0.0.1 \
  --threads 4 \
  --gpu-layers 33 \
  --verbose
```

**Key Parameters:**

- `--model`: Path to .gguf model file (e.g., `phi-3-mini.Q5_K_M.gguf`)
- `--port 11434`: API server port (**11434 is the standard Ollama port** — change if needed)
- `--gpu-layers 33`: How many layers to offload to GPU (adjust based on VRAM)
- `--ctx-size 2048`: Context window (2K is sufficient for chat analysis)
- `--threads 4`: CPU threads (adjust to your CPU cores)

### API Endpoint

Once running, the server exposes an **OpenAI-compatible API**:

```
POST http://127.0.0.1:8000/v1/chat/completions
```

**Example Request:**

```json
{
  "model": "phi-3-mini",
  "messages": [
    {
      "role": "system",
      "content": "Analyze if this player is a threat. Respond with JSON: {\"threat_level\": \"low|medium|high\", \"confidence\": 0.0-1.0}"
    },
    {
      "role": "user",
      "content": "Unknown player 'Grimdark' just entered local chat and said 'looking for targets'"
    }
  ],
  "temperature": 0.3
}
```

**Expected Response:**

```json
{
  "choices": [
    {
      "message": {
        "content": "{\"threat_level\": \"high\", \"confidence\": 0.92}"
      }
    }
  ]
}
```

### Configuration in screenalert_config.json

Add these settings for llama.cpp integration (using standard Ollama port **11434**):

```json
{
  "llm_enabled": true,
  "llm_model_name": "phi-3-mini",
  "llm_api_url": "http://127.0.0.1:11434/v1",
  "llm_api_timeout_sec": 5,
  "llm_temperature": 0.3,
  "llm_max_tokens": 200,
  "chat_analysis_enabled": true,
  "chat_threat_threshold": 0.7,
  "known_players": [
    "YourName",
    "AllyPlayer1",
    "AllyPlayer2"
  ]
}
```

### Testing llama.cpp Connection

Once the server is running, test it with:

```bash
curl -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi-3-mini",
    "messages": [{"role": "user", "content": "Hello, are you working?"}],
    "max_tokens": 50
  }'
```

Should return a response within 1-2 seconds.

### Performance Tuning

**If inference is too slow:**

1. Lower `--gpu-layers` (offload fewer layers to GPU, use CPU more)
2. Reduce `--ctx-size` (smaller context = faster)
3. Use lower quantization (Q4_K_M instead of Q5_K_M)
4. Check CPU/GPU utilization with Task Manager

**If VRAM is running out:**

1. Lower `--gpu-layers` to free VRAM
2. Use Q4_K_M quantization instead of Q5_K_M
3. Reduce `--ctx-size` to 1024

---

## Building llama.cpp from Source

The source code is in `llama-cpp-src/` (cloned from [github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)).

### Prerequisites for Windows

#### Required

- **Visual Studio 2022 Community** (free) — [Download](https://visualstudio.microsoft.com/vs/community/)
  - During installation, select:
    - Workload: "Desktop development with C++"
    - Components: CMake Tools for Windows, Git for Windows, Clang Compiler for Windows
  - After installation, always use **Developer Command Prompt for VS2022** for building

- **CMake** (usually included with Visual Studio; if not, [download](https://cmake.org/download/))

#### Optional but recommended

- **OpenSSL Development Libraries** — for HTTPS/TLS support in llama-server
  - Can be skipped; server will build without SSL but without HTTPS support
  - Windows: Use pre-built binaries or package manager

#### Optional for GPU acceleration

- **NVIDIA CUDA Toolkit** — only if you want CUDA GPU support (we already have Vulkan in the binary)
  - [Download CUDA](https://developer.nvidia.com/cuda-downloads)

### Build Steps

#### 1. Open Developer Command Prompt for VS2022

Find it in Start Menu → Visual Studio 2022 → "Developer Command Prompt for VS2022"

#### 2. Navigate to llama-cpp-src

```bash
cd d:\onedrive\Documents\Development\ScreenAlert\llama-cpp-src
```

#### 3. Create a build directory and configure

**Using PowerShell (Recommended):**

```powershell
cmake -B build -G 'Visual Studio 17 2022' -A x64 `
  -DCMAKE_ASM_COMPILER='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/ml64.exe' `
  -DGGML_NATIVE=OFF
```

**Using cmd.exe:**

```cmd
cmake -B build -G "Visual Studio 17 2022" -A x64 ^
  -DCMAKE_ASM_COMPILER="C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/ml64.exe" ^
  -DGGML_NATIVE=OFF
```

**Important:**

- Replace `14.44.35207` with your actual MSVC version:

  ```
  C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\<VERSION>\bin\Hostx64\x64\ml64.exe
  ```

- The `CMAKE_ASM_COMPILER` path is required for MSVC builds

**Optional flags (add to the command above):**

- For Vulkan GPU support: `-DGGML_VULKAN=ON`
- For CUDA GPU support: `-DGGML_CUDA=ON` (requires CUDA Toolkit)
- For static build: `-DBUILD_SHARED_LIBS=OFF`
- For debug: change `Release` in step 4 to `Debug`

**Example with Vulkan:**

```powershell
cmake -B build -G 'Visual Studio 17 2022' -A x64 `
  -DCMAKE_ASM_COMPILER='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/ml64.exe' `
  -DGGML_NATIVE=OFF -DGGML_VULKAN=ON
```

#### 4. Build

```bash
cmake --build build --config Release -j 8
```

The `-j 8` flag runs 8 parallel jobs (adjust based on your CPU cores). This takes 5-15 minutes depending on your hardware.

#### 5. Verify successful build

If successful, you'll have:

- `build/bin/llama-server.exe` — The OpenAI-compatible server
- `build/bin/llama-cli.exe` — Command-line interface
- Other tools in `build/bin/`

#### 6. Copy binaries to llama-cpp-binary (optional)

Once built, you can copy the new binaries:

```bash
xcopy /E /I build\bin\*.exe d:\onedrive\Documents\Development\ScreenAlert\llama-cpp-binary\
xcopy /E /I build\bin\*.dll d:\onedrive\Documents\Development\ScreenAlert\llama-cpp-binary\
```

### Troubleshooting Build Issues

#### "CMake not found"

- Install CMake via Visual Studio installer, or download from cmake.org
- Ensure you're using Developer Command Prompt (not regular PowerShell)

#### "MSVC compiler not found"

- Verify Visual Studio 2022 installed correctly
- Reinstall if needed; ensure "Desktop development with C++" workload is selected

#### "Vulkan headers not found" (if using -DGGML_VULKAN=ON)

- llama.cpp will auto-download Vulkan headers; if this fails:
  - Install [Vulkan SDK](https://vulkan.lunarg.com/sdk/home) separately
  - Rerun `cmake -B build -DGGML_VULKAN=ON`

#### "CUDA not found" (if using -DGGML_CUDA=ON)

- Download and install [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
- Ensure CUDA bin path is in your system PATH
- Rerun cmake

### Performance Notes

- **Release vs Debug**: Release builds are 5-10x faster for inference. Always use Release unless debugging.
- **Parallel jobs**: Adjust `-j N` based on your CPU; `-j 8` is reasonable for modern CPUs.
- **Build time**: Expect 5-15 minutes for full build on modern hardware.
- **Output binary size**: Release builds are ~50-100MB depending on enabled backends.

---

## llama-cpp Server API & Ollama Compatibility

### API Surface

The llama-cpp server exposes **40+ HTTP endpoints** across three API surfaces:

1. **Ollama Native API** (`/api/*`)
2. **OpenAI Compatible API** (`/v1/*`)
3. **Utility endpoints** (tokenize, embeddings, etc.)

### Ollama Alignment

For RC-2.0.8, we're using llama-cpp **as-is** because:

- ✅ **Ollama-compatible** for core endpoints we need
- ✅ **OpenAI-compatible** for standardized `/v1/*` paths
- ✅ **No extra overhead** if unused endpoints aren't called
- ✅ **Future-proof** for expanding functionality

### Endpoints Used in RC-2.0.8

For chat-based threat analysis, you'll use:

| Endpoint | Purpose | Method |
| --- | --- | --- |
| `/v1/models` | List available models | `GET` |
| `/v1/chat/completions` | Send chat message for analysis | `POST` |
| `/health` or `/v1/health` | Health check | `GET` |

### Example: Chat Threat Analysis Request

```bash
curl -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi-3-mini",
    "messages": [
      {
        "role": "system",
        "content": "Analyze if this player is a threat in Eve Online. Respond with JSON only: {\"threat_level\": \"low|medium|high\", \"confidence\": 0.0-1.0}"
      },
      {
        "role": "user",
        "content": "Unknown player just entered local chat and said: '\''looking for targets'\''"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 200
  }'
```

**Response:**

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "{\"threat_level\": \"high\", \"confidence\": 0.92}"
      }
    }
  ],
  "model": "phi-3-mini",
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 15,
    "total_tokens": 60
  }
}
```

### Available Endpoints (Reference)

**Chat & Completion:**

- `POST /v1/chat/completions` — OpenAI-compatible chat
- `POST /api/chat` — Ollama-compatible chat
- `POST /v1/completions` — Text completion

**Models:**

- `GET /v1/models` — List models (OpenAI format)
- `GET /api/tags` — List models (Ollama format)
- `POST /api/show` — Get model details

**Utilities (not needed for RC-2.0.8):**

- `POST /v1/embeddings` — Generate embeddings
- `POST /tokenize` — Tokenize text
- `POST /detokenize` — Detokenize tokens
- `POST /infill` — Code infill
- `POST /rerank` — Reranking
- And 20+ more endpoints

**Health:**

- `GET /health` — Basic health check
- `GET /v1/health` — OpenAI-compatible health check
- `GET /metrics` — Prometheus metrics

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
