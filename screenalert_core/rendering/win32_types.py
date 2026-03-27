"""Win32 constants, DLL handles, and ctypes structures for overlay windows.

Centralising these here keeps overlay_window.py focused on behaviour and
makes the raw Win32 bindings reusable by any future rendering module.
"""

import ctypes
import ctypes.wintypes
import logging
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from screenalert_core.rendering.overlay_window import OverlayWindow

logger = logging.getLogger(__name__)

# ── DLL handles ─────────────────────────────────────────────────────────

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Correct argtypes for 64-bit Windows — prevents OverflowError on large lparams
user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.c_uint,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_longlong

# ── Window style constants ───────────────────────────────────────────────

WS_POPUP     = 0x80000000
WS_VISIBLE   = 0x10000000

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST    = 0x00000008
WS_EX_LAYERED    = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

# ── Window messages ──────────────────────────────────────────────────────

WM_CREATE    = 0x0001
WM_DESTROY   = 0x0002
WM_PAINT     = 0x000F
WM_CLOSE     = 0x0010
WM_ERASEBKGND = 0x0014
WM_TIMER     = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP   = 0x0205
WM_MOUSEMOVE   = 0x0200
WM_MOUSELEAVE  = 0x02A3
WM_DPICHANGED  = 0x02E0
WM_USER        = 0x0400

# ── Layered window / SetWindowPos ────────────────────────────────────────

LWA_ALPHA = 0x00000002

SWP_NOACTIVATE = 0x0010
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001
SWP_NOZORDER   = 0x0004
SWP_SHOWWINDOW = 0x0040

HWND_TOPMOST   = -1
HWND_NOTOPMOST = -2

SW_HIDE          = 0
SW_SHOWNOACTIVATE = 4

# ── Mouse tracking ───────────────────────────────────────────────────────

TME_LEAVE  = 0x00000002
MK_SHIFT   = 0x0004
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

# ── GDI ──────────────────────────────────────────────────────────────────

PS_SOLID   = 0
NULL_BRUSH = 5

# ── Overlay-specific metrics ─────────────────────────────────────────────

TIMER_ID_UPDATE  = 1
TITLE_BAR_HEIGHT = 25
BORDER_WIDTH     = 3
DRAG_THRESHOLD_PX = 4

# ── Colours (Win32 GDI uses BGR) ─────────────────────────────────────────

COLOR_BORDER_ACTIVE  = 0x0095FF  # BGR for #FF9500 (orange)
COLOR_TITLE_BG       = 0x2E2E2E  # BGR for #2e2e2e (dark grey)
COLOR_UNAVAILABLE_BG = 0xD77800  # BGR for #0078D7 (Windows blue)
COLOR_BLACK          = 0x000000

# ── ctypes structures ────────────────────────────────────────────────────

class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize",     ctypes.c_ulong),
        ("dwFlags",    ctypes.c_ulong),
        ("hwndTrack",  ctypes.wintypes.HWND),
        ("dwHoverTime", ctypes.c_ulong),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc",          ctypes.wintypes.HDC),
        ("fErase",       ctypes.wintypes.BOOL),
        ("rcPaint",      ctypes.wintypes.RECT),
        ("fRestore",     ctypes.wintypes.BOOL),
        ("fIncUpdate",   ctypes.wintypes.BOOL),
        ("rgbReserved",  ctypes.c_byte * 32),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    ctypes.wintypes.HWND,
    ctypes.c_uint,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        ctypes.c_uint),
        ("style",         ctypes.c_uint),
        ("lpfnWndProc",   WNDPROC),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     ctypes.wintypes.HINSTANCE),
        ("hIcon",         ctypes.wintypes.HICON),
        ("hCursor",       ctypes.wintypes.HICON),
        ("hbrBackground", ctypes.wintypes.HBRUSH),
        ("lpszMenuName",  ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
        ("hIconSm",       ctypes.wintypes.HICON),
    ]


# ── Window class registration (once per process) ─────────────────────────

_wndclass_registered = False
_wndclass_name = "ScreenAlertOverlay"
_window_map: Dict[int, "OverlayWindow"] = {}  # hwnd -> OverlayWindow


def _wndproc_dispatch(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    """Global WndProc — dispatches to the correct OverlayWindow instance."""
    try:
        overlay = _window_map.get(hwnd)
        if overlay:
            result = overlay._handle_message(msg, wparam, lparam)
            if result is not None:
                return result
    except Exception as exc:
        logger.warning("WndProc error hwnd=%s msg=0x%04X: %s", hwnd, msg, exc)
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_wndproc_ref = WNDPROC(_wndproc_dispatch)  # keep reference to prevent GC


def ensure_wndclass() -> None:
    """Register the overlay window class with Win32 (idempotent)."""
    global _wndclass_registered
    if _wndclass_registered:
        return
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = _wndproc_ref
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hIcon = None
    wc.hCursor = user32.LoadCursorW(None, 32512)  # IDC_ARROW
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = _wndclass_name
    wc.hIconSm = None
    atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not atom:
        err = ctypes.GetLastError()
        raise OSError(f"RegisterClassExW failed: error={err}")
    _wndclass_registered = True
    logger.debug("Overlay window class '%s' registered", _wndclass_name)
