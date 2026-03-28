# Specification: DWM Thumbnail Overlay System

## Goal

Replace the current software-rendered thumbnail pipeline (PrintWindow → PIL resize → Tkinter display) with Windows DWM Thumbnail API for smooth, hardware-accelerated, OS-composited live previews. Fully decouple thumbnail display from the monitoring capture loop.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ScreenAlert App                       │
│                                                         │
│  ┌──────────────────────┐   ┌────────────────────────┐  │
│  │  DWM Overlay Manager │   │   Monitoring Engine    │  │
│  │  (thumbnail display) │   │   (change detection)   │  │
│  │                      │   │                        │  │
│  │  - Win32 windows     │   │  - PrintWindow capture │  │
│  │  - DwmRegisterThumb  │   │  - SSIM / edge / pHash │  │
│  │  - OS-composited     │   │  - Region analysis     │  │
│  │  - Mouse interaction │   │  - Alert triggering    │  │
│  │  - Title on hover    │   │                        │  │
│  │  - Active border     │   │                        │  │
│  └──────────────────────┘   └────────────────────────┘  │
│           │                          │                   │
│           │ (independent)            │                   │
│           ▼                          ▼                   │
│    GPU Compositor              PrintWindow API           │
│    (smooth, ~0 CPU)            (1s intervals, CPU)       │
└─────────────────────────────────────────────────────────┘
```

**Key principle:** The DWM overlay handles *display only*. The monitoring engine handles *analysis only*. They share no image data and run independently.

---

## DWM Thumbnail API Usage

### Core Win32 API Calls (via ctypes)

| Function | Purpose |
|----------|---------|
| `DwmRegisterThumbnail(dest_hwnd, source_hwnd)` | Create live link between source window and overlay |
| `DwmUpdateThumbnailProperties(thumb_id, props)` | Set size, position, opacity, visible source region |
| `DwmUnregisterThumbnail(thumb_id)` | Destroy the link |
| `DwmQueryThumbnailSourceSize(thumb_id)` | Get source window dimensions for aspect ratio |

### DWM_THUMBNAIL_PROPERTIES Fields

```
- dwFlags: which fields are valid
- rcDestination: RECT in dest window where thumbnail renders
- rcSource: RECT of source window region to show (or full window)
- opacity: 0-255 (mapped from our 0.0-1.0 setting)
- fVisible: TRUE/FALSE
- fSourceClientAreaOnly: TRUE (show only client area, no title bar)
```

### Registration Lifecycle

```
Thumbnail Added/Window Found:
  1. Create Win32 overlay window (hidden)
  2. DwmRegisterThumbnail(overlay_hwnd, source_hwnd)
  3. DwmQueryThumbnailSourceSize → compute aspect-ratio-correct dest rect
  4. DwmUpdateThumbnailProperties (size, opacity, visible=True)
  5. ShowWindow(overlay_hwnd)

Source Window Lost/Closed:
  1. DwmUnregisterThumbnail(thumb_id)
  2. Show "Not Available" blue screen or hide overlay (per config)

Source Window Reconnected:
  1. DwmRegisterThumbnail with new hwnd
  2. Resume live display

Thumbnail Removed:
  1. DwmUnregisterThumbnail(thumb_id)
  2. DestroyWindow(overlay_hwnd)
```

---

## Overlay Window Specification

### Window Creation

Each overlay is a native Win32 window created via `CreateWindowEx`:

```
Extended Style: WS_EX_TOOLWINDOW    (no taskbar entry)
              | WS_EX_TOPMOST       (always on top)
              | WS_EX_LAYERED       (opacity support)
              | WS_EX_NOACTIVATE    (no focus steal)

Style:         WS_POPUP             (no decorations)
```

- Opacity via `SetLayeredWindowAttributes(hwnd, 0, alpha_byte, LWA_ALPHA)`
- No Tkinter Toplevel - pure Win32 window via ctypes/pywin32

### Rendering Layers

The overlay window has two visual layers:

1. **DWM Thumbnail** (bottom) - OS-composited live preview of source window
2. **Active Border** (drawn by app) - Optional colored frame indicating active window

The title bar and close button are drawn on mouse enter as a temporary overlay element.

### Frame Rate

- DWM thumbnails are composited by the OS at the display refresh rate (typically 60 Hz) regardless of any app setting
- The "frame rate" setting in the app controls the **DWM update interval** — how often we call `DwmUpdateThumbnailProperties` to sync size/position/opacity changes
- Default: 30 Hz (33ms timer)
- Range: 10-60 Hz
- This does NOT affect visual smoothness of the live preview — that is always at display refresh rate
- Setting name: `overlay_update_rate_hz` in app config

---

## Mouse Interactions (All Preserved)

### Left Click (activate source window)
- **Trigger:** `WM_LBUTTONUP` within 4px drag threshold
- **Action:** `SetForegroundWindow(source_hwnd)` — brings monitored window to front
- **Condition:** Only when source window is available (valid hwnd)

### Right Click + Drag (move overlay)
- **Trigger:** `WM_RBUTTONDOWN` → `WM_MOUSEMOVE` → `WM_RBUTTONUP`
- **Action:** Move overlay window position, emit `position_changed` on release
- **Drag threshold:** 4 pixels before entering move state

### Left + Right Click + Drag (resize overlay)
- **Trigger:** Both buttons pressed → `WM_MOUSEMOVE`
- **Action:** Resize overlay, maintaining aspect ratio of source window
- **Constraints:** Min 100x80, Max 1280x800
- **On release:** Emit `size_changed`, update DWM dest rect, save config

### Shift + Left + Right Click + Drag (synchronized resize)
- **Trigger:** Both buttons + Shift key → `WM_MOUSEMOVE`
- **Action:** Resize ALL overlay windows proportionally by same delta
- **On release:** Emit `bulk_geometry_changed`, save all configs

### Mouse Enter (show title)
- **Trigger:** `WM_MOUSEMOVE` when not previously inside (track via `TME_LEAVE`)
- **Action:** Show title bar overlay (25px height) with:
  - Window title text (left-aligned, white on dark gray #2e2e2e)
  - Close button "✕" (right side, hand cursor on hover)
- **Title source:** `window_title` from config (the user's stored label, not live `GetWindowText`)

### Mouse Leave (hide title)
- **Trigger:** `WM_MOUSELEAVE` (via `TrackMouseEvent`)
- **Action:** Hide title bar overlay
- **Edge case:** Verify pointer is actually outside window bounds before hiding

### Close Button Click
- **Trigger:** Left click on "✕" in title bar
- **Action:** Hide overlay (`ShowWindow(SW_HIDE)`), set `overview_visible = False`, save config
- **Monitoring continues** — the overlay is hidden but monitoring/alerts remain fully active
- Overlay can be re-shown from the main UI at any time
- Removing a thumbnail entirely (stopping monitoring) is only done from the main UI

---

## Active Window Border

### Detection
- Existing `EVENT_SYSTEM_FOREGROUND` hook (Win32 `SetWinEventHook`) detects when any monitored source window gains focus
- Runs in dedicated "foreground-event-hook" thread
- Checks window family (parent/child grouping)

### Visual
- **Active:** 3px border, orange (#FF9500), rendered around overlay window edge
- **Inactive:** No border (0px)
- Only one overlay has active border at any time
- Border always renders at full opacity regardless of overlay opacity setting (ensures visibility at low opacity)
- Border drawn via `WM_PAINT` or layered window composition — not a separate window

### Implementation
- Adjust `rcDestination` inward by 3px when border is active, draw border in remaining margin area via GDI
- When border deactivates, expand `rcDestination` back to full window area

---

## Source Window Availability & Error States

All error conditions use the same generic "Not Available" blue screen. There is no distinction in the overlay between a closed window, a minimized window, or a DWM registration error — the user sees the same visual state.

### Available State
- DWM thumbnail visible and live
- Left-click activates source window
- Normal opacity

### Unavailable State

Triggered by any of:
- Source window closed or destroyed
- Source window minimized (DWM can't thumbnail minimized windows)
- `DwmRegisterThumbnail` returns an error (e.g., protected window, UWP restrictions)
- `DwmUpdateThumbnailProperties` fails
- Source hwnd becomes invalid

**Behavior:**
- `DwmUnregisterThumbnail` if a registration exists (no stale frame)
- Two modes (per existing config):
  - **show_when_unavailable = True:** Show overlay with "Not Available" text (blue #0078D7 background, white text, centered)
  - **show_when_unavailable = False:** `ShowWindow(SW_HIDE)` — hide overlay entirely
- Left-click does nothing in unavailable state
- Title bar still shows on hover (so user can close the overlay)
- Active border does not apply

### Reconnection
- When source window becomes available again (e.g., un-minimized, reopened):
  - Re-register DWM thumbnail with new/same hwnd
  - Resume live display
- On DWM registration error during reconnect: remain in unavailable state, retry on next update cycle

---

## Multi-Monitor Support

### DPI Awareness
- Set `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` at app startup
- All coordinate math uses physical pixels

### Monitor Transitions
- When an overlay is dragged to a different monitor, handle `WM_DPICHANGED`:
  - Recalculate overlay size for new DPI
  - Update DWM `rcDestination` to maintain correct aspect ratio
  - Update config with new monitor index
- Position stored relative to monitor (existing `monitor` field in config)

### Source Window on Different Monitor
- DWM thumbnails work across monitors regardless of DPI differences — the OS handles scaling
- No special handling needed in the overlay

---

## Source Window Resize Tracking

If the monitored source window is resized, the DWM thumbnail aspect ratio changes. Without tracking, the overlay would show a stretched/distorted image.

### Detection
- On the DWM update timer (overlay_update_rate_hz), call `DwmQueryThumbnailSourceSize`
- Compare with last known source size
- If changed: recalculate `rcDestination` to maintain correct aspect ratio within the current overlay window size

### Behavior
- Overlay window size stays the same (user-configured)
- DWM dest rect adjusts within the overlay to preserve aspect ratio (letterbox/pillarbox as needed)
- Letterbox/pillarbox areas filled with black

---

## Z-Order Management

### Rules
- All overlays use `WS_EX_TOPMOST` — they stay above normal windows
- Among overlays, the **active overlay** (with border) is always topmost
- When an overlay is clicked (left-click to activate source), it is brought to front among overlays
- When a source window gains focus (foreground hook), its overlay is brought to front

### Implementation
- On active border change: `SetWindowPos(active_hwnd, HWND_TOPMOST, ...)` to ensure it's above other overlays
- On left-click activation: `SetWindowPos` to bring clicked overlay to front before activating source window

---

## Alert Behavior (Unchanged)

- Monitoring engine detects changes via PrintWindow captures (independent of DWM overlay)
- On alert: main app window brought to foreground (existing behavior)
- Alert sounds, TTS messages, region state machine — all unchanged
- No visual alert indicators on the DWM overlay itself

---

## Configuration

### New Settings

```json
{
  "app": {
    "overlay_update_rate_hz": 30
  }
}
```

### Preserved Settings (per thumbnail)

```json
{
  "position": {"x": 100, "y": 100, "monitor": 0},
  "size": {"width": 320, "height": 240},
  "opacity": 0.85,
  "show_border": true,
  "always_on_top": true,
  "overview_visible": true,
  "show_when_unavailable": true
}
```

### Settings UI
- Overlay Update Rate slider (10-60 Hz) in app settings panel
- Label: "Overlay Update Rate" with Hz value display
- Distinct from monitoring "Refresh Rate (ms)" — different label, different unit, different section
- Existing opacity, always-on-top, show-border controls remain

---

## What Gets Removed

- `_raw_image_queue`, `image_queue`, `_processed_queue` — no image pipeline needed for display
- `_image_worker` thread — no background resize thread needed
- `_process_image_queue` timer — no queue polling needed
- `ImageTk.PhotoImage` conversion — no PIL-to-Tk conversion
- Tkinter `Toplevel` windows for thumbnails — replaced by Win32 windows
- `PIL.Image` rendering path in `ThumbnailWindow`
- All thumbnail-related image capture in the engine loop (monitoring capture remains)

## What Gets Kept

- All monitoring logic (SSIM, regions, alerts, thresholds, state machine)
- PrintWindow capture for monitoring (unchanged)
- CacheManager for monitoring captures
- Configuration system (positions, sizes, regions, settings)
- Main UI window (Tkinter) for control panel
- Alert system (sound, TTS)
- Foreground hook thread (EVENT_SYSTEM_FOREGROUND)
- All interaction callbacks and config persistence
- Window family detection and grouping

---

## Threading Model

```
Main Thread (Tkinter):
  - Control panel UI
  - User configuration

Win32 Message Pump Thread (NEW):
  - Overlay window message processing
  - Mouse interactions (drag, click, resize)
  - Title bar show/hide
  - DwmUpdateThumbnailProperties calls
  - Active border painting
  - Source size polling

Foreground Hook Thread (existing):
  - EVENT_SYSTEM_FOREGROUND monitoring
  - Active border state updates
  - Z-order management (bring active overlay to front)

Monitoring Engine Thread (existing, simplified):
  - PrintWindow capture (for monitoring only)
  - Region analysis
  - Alert generation
  - NO thumbnail image updates
```

---

## Future Compatibility

### Abstraction Layer

All Win32/DWM calls are isolated behind a `ThumbnailBackend` interface:

```python
class ThumbnailBackend(ABC):
    """Abstract interface for thumbnail compositing backends."""

    @abstractmethod
    def register(self, dest_hwnd: int, source_hwnd: int) -> Any:
        """Create a live thumbnail link. Returns backend-specific handle."""

    @abstractmethod
    def unregister(self, handle: Any) -> None:
        """Destroy a thumbnail link."""

    @abstractmethod
    def update_properties(self, handle: Any, *,
                          dest_rect: tuple[int,int,int,int],
                          opacity: int = 255,
                          visible: bool = True,
                          source_client_only: bool = True) -> None:
        """Update thumbnail display properties."""

    @abstractmethod
    def query_source_size(self, handle: Any) -> tuple[int, int]:
        """Return (width, height) of source window."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is functional on the current system."""
```

The concrete implementation is `DwmThumbnailBackend`. All overlay window logic (interactions, borders, title bar) lives above this interface and is backend-agnostic.

### Why This Matters

| Scenario | Impact |
| -------- | ------ |
| **DWM API deprecated** (unlikely, stable since 2006) | Swap to new backend, zero overlay logic changes |
| **Windows.Graphics.Capture** becomes preferred | Implement `CaptureBackend` — would use frame-based rendering but same interface |
| **DirectComposition** integration | Implement `DirectCompBackend` for richer compositing |
| **ARM64 Windows** | Same ctypes declarations work; just needs testing |
| **New DPI/scaling modes** | Handled in overlay window layer, not backend |

### DPI Awareness

- Set `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` at app startup
- All coordinate math uses physical pixels
- Handle `WM_DPICHANGED` to recompute overlay positions on DPI changes
- This covers current and anticipated future Windows scaling behavior

### Win32 Window Abstraction

The overlay window class (`OverlayWindow`) is also separated from the backend:

```
OverlayWindow (Win32 message handling, mouse interactions, title bar, border)
    └── uses ThumbnailBackend (compositing — DWM today, swappable tomorrow)
```

This means interaction logic (drag, click, resize, hover) is written once and survives any backend change.

---

## Implementation Notes

### ctypes Declarations Needed

```python
dwmapi = ctypes.windll.dwmapi

# DwmRegisterThumbnail(HWND dest, HWND src, PHTHUMBNAIL phThumb) -> HRESULT
# DwmUnregisterThumbnail(HTHUMBNAIL hThumb) -> HRESULT
# DwmUpdateThumbnailProperties(HTHUMBNAIL hThumb, DWM_THUMBNAIL_PROPERTIES* ptp) -> HRESULT
# DwmQueryThumbnailSourceSize(HTHUMBNAIL hThumb, PSIZE pSize) -> HRESULT
```

### Key Structures

```python
class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", ctypes.c_ulong),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_byte),
        ("fVisible", ctypes.c_bool),
        ("fSourceClientAreaOnly", ctypes.c_bool),
    ]

# Flags
DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000002
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010
```

### DWM Limitations
- Source window must not be minimized (DWM can't thumbnail minimized windows)
  - On minimize: unregister thumbnail, show unavailable state
  - On restore: re-register thumbnail
- DWM must be enabled (always on in Windows 8+, guaranteed on Windows 10/11)
- No fallback mode — DWM is guaranteed on target platform

---

## Migration Checklist

1. [ ] Create `ThumbnailBackend` ABC and `DwmThumbnailBackend` implementation
2. [ ] Create Win32 overlay window class (ctypes CreateWindowEx + message pump)
3. [ ] Implement DWM thumbnail registration/update/unregistration via backend
4. [ ] Port all mouse interactions to Win32 message handlers
5. [ ] Implement title bar overlay (show on hover with config title, close button)
6. [ ] Implement active border drawing (full opacity regardless of window opacity)
7. [ ] Implement unified "Not Available" blue screen for all error/unavailable states
8. [ ] Implement source window resize tracking (aspect ratio preservation)
9. [ ] Implement multi-monitor DPI handling (WM_DPICHANGED, physical pixels)
10. [ ] Implement Z-order management (active overlay topmost)
11. [ ] Add overlay_update_rate_hz setting + UI control (distinct from monitoring refresh rate)
12. [ ] Decouple engine loop — remove thumbnail image updates, keep monitoring captures
13. [ ] Ensure close button hides overlay only — monitoring remains active
14. [ ] Remove old Tkinter thumbnail windows and image pipeline
15. [ ] Update config manager for new settings
16. [ ] Test all interactions match current behavior
17. [ ] Update ARCHITECTURE.md
