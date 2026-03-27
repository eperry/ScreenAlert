"""Win32 overlay window with DWM thumbnail compositing.

Each OverlayWindow is a native Win32 popup that hosts a DWM thumbnail link.
All mouse interactions (move, resize, activate, title bar) are handled via
the Win32 message loop.  No Tkinter dependency.
"""

import ctypes
import ctypes.wintypes
import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple, TYPE_CHECKING

from screenalert_core.rendering.dwm_backend import ThumbnailBackend
from screenalert_core.utils.constants import (
    THUMBNAIL_MIN_WIDTH, THUMBNAIL_MAX_WIDTH,
    THUMBNAIL_MIN_HEIGHT, THUMBNAIL_MAX_HEIGHT,
)

if TYPE_CHECKING:
    from screenalert_core.rendering.overlay_manager import OverlayManager

logger = logging.getLogger(__name__)

# ── Win32 constants ──────────────────────────────────────────────────────

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_CLOSE = 0x0010
WM_ERASEBKGND = 0x0014
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_MOUSELEAVE = 0x02A3
WM_DPICHANGED = 0x02E0
WM_USER = 0x0400

LWA_ALPHA = 0x00000002

SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

TME_LEAVE = 0x00000002

MK_SHIFT = 0x0004
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

# GDI
PS_SOLID = 0
NULL_BRUSH = 5

TIMER_ID_UPDATE = 1
TITLE_BAR_HEIGHT = 25
BORDER_WIDTH = 3
DRAG_THRESHOLD_PX = 4

# Colors
COLOR_BORDER_ACTIVE = 0x0095FF  # BGR for #FF9500
COLOR_TITLE_BG = 0x2E2E2E  # BGR for #2e2e2e
COLOR_UNAVAILABLE_BG = 0xD77800  # BGR for #0078D7
COLOR_BLACK = 0x000000

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Set proper argtypes for 64-bit Windows
user32.DefWindowProcW.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong


# ── Win32 helpers ────────────────────────────────────────────────────────

class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("hwndTrack", ctypes.wintypes.HWND),
        ("dwHoverTime", ctypes.c_ulong),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", ctypes.wintypes.HDC),
        ("fErase", ctypes.wintypes.BOOL),
        ("rcPaint", ctypes.wintypes.RECT),
        ("fRestore", ctypes.wintypes.BOOL),
        ("fIncUpdate", ctypes.wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
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
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("hIcon", ctypes.wintypes.HICON),
        ("hCursor", ctypes.wintypes.HICON),
        ("hbrBackground", ctypes.wintypes.HBRUSH),
        ("lpszMenuName", ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
        ("hIconSm", ctypes.wintypes.HICON),
    ]


# Global window class registration (once per process)
_wndclass_registered = False
_wndclass_name = "ScreenAlertOverlay"
_window_map: Dict[int, "OverlayWindow"] = {}  # hwnd -> OverlayWindow


def _wndproc(hwnd, msg, wparam, lparam):
    """Global WndProc that dispatches to the OverlayWindow instance."""
    try:
        overlay = _window_map.get(hwnd)
        if overlay:
            result = overlay._handle_message(msg, wparam, lparam)
            if result is not None:
                return result
    except Exception as e:
        logger.warning("WndProc error for hwnd=%s msg=0x%04X: %s", hwnd, msg, e)
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_wndproc_ref = WNDPROC(_wndproc)  # prevent GC


def _ensure_wndclass():
    """Register the Win32 window class (once per process)."""
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
    logger.debug("Overlay window class registered")


# ── OverlayWindow ────────────────────────────────────────────────────────

class OverlayWindow:
    """A single DWM-backed overlay window with mouse interactions."""

    def __init__(
        self,
        thumbnail_id: str,
        config: Dict,
        backend: ThumbnailBackend,
        manager_callback: Optional[Callable] = None,
        owner_manager: Optional["OverlayManager"] = None,
    ):
        self.thumbnail_id = thumbnail_id
        self.config = config
        self.backend = backend
        self.manager_callback = manager_callback
        self.owner_manager = owner_manager

        # Position and size
        pos = config.get("position", {})
        size = config.get("size", {})
        self.x = pos.get("x", 100)
        self.y = pos.get("y", 100)
        self.monitor = pos.get("monitor", 0)
        self.width = size.get("width", 320)
        self.height = size.get("height", 240)

        # Appearance
        self.opacity = config.get("opacity", 0.8)
        self.always_on_top = bool(config.get("always_on_top", True))
        self.show_border = config.get("show_border", True)
        self._scaling_mode = "fit"  # "fit", "stretch", or "letterbox"
        self._is_active_window = False

        # State
        self._is_available = True
        self._show_when_unavailable = False
        self._is_user_hidden = False
        self._source_hwnd: Optional[int] = None
        self._dwm_handle: Optional[Any] = None
        self._source_size: Tuple[int, int] = (0, 0)
        self._poll_fail_count = 0
        self._props_fail_count = 0

        # Interaction state machine
        self.interaction_state = "idle"
        self.left_pressed = False
        self.right_pressed = False
        self.pointer_start = (0, 0)
        self.start_geometry = {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
        self._sync_start_sizes: Dict[str, Tuple[int, int]] = {}
        self._did_move_or_resize = False
        self._mouse_inside = False

        # Win32 window
        self.hwnd: Optional[int] = None
        self._create_window()
        logger.debug("[%s] OverlayWindow initialized at (%s,%s) %sx%s",
                     thumbnail_id, self.x, self.y, self.width, self.height)

    # ── Window creation ─────────────────────────────────────────────────

    def _create_window(self) -> None:
        """Create the native Win32 overlay window."""
        try:
            _ensure_wndclass()

            ex_style = WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE
            if self.always_on_top:
                ex_style |= WS_EX_TOPMOST

            self.hwnd = user32.CreateWindowExW(
                ex_style,
                _wndclass_name,
                f"ScreenAlert Overlay - {self.thumbnail_id}",
                WS_POPUP,
                self.x, self.y, self.width, self.height,
                None, None, kernel32.GetModuleHandleW(None), None,
            )
            if not self.hwnd:
                err = ctypes.GetLastError()
                raise OSError(f"CreateWindowExW failed: error={err}")

            _window_map[self.hwnd] = self

            # Set opacity
            alpha_byte = max(1, min(255, int(self.opacity * 255)))
            user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha_byte, LWA_ALPHA)

            # Show window without activating
            if not self._is_user_hidden:
                user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)

            logger.debug("[%s] Overlay window created: hwnd=%s", self.thumbnail_id, self.hwnd)

        except Exception as e:
            logger.error("[%s] Failed to create overlay window: %s", self.thumbnail_id, e, exc_info=True)
            raise

    # ── DWM thumbnail management ────────────────────────────────────────

    def set_source_hwnd(self, source_hwnd: int) -> None:
        """Set or change the source window for DWM thumbnail."""
        # Skip if hwnd unchanged and we already have a valid DWM handle
        if source_hwnd == self._source_hwnd and self._dwm_handle is not None:
            return

        logger.debug("[%s] set_source_hwnd: src=%s (prev=%s)",
                     self.thumbnail_id, source_hwnd, self._source_hwnd)

        if self._dwm_handle is not None:
            try:
                self.backend.unregister(self._dwm_handle)
            except Exception as e:
                logger.warning("[%s] Failed to unregister previous DWM thumb: %s",
                               self.thumbnail_id, e)
            self._dwm_handle = None

        self._source_hwnd = source_hwnd
        if source_hwnd and self.hwnd:
            try:
                self._dwm_handle = self.backend.register(self.hwnd, source_hwnd)
                self._query_and_update_source_size()
                self._update_dwm_properties()
                # Don't set _is_available here — let set_availability() handle
                # visibility so the early-return guard works correctly.
                logger.debug("[%s] DWM thumbnail linked: src=%s -> overlay=%s",
                             self.thumbnail_id, source_hwnd, self.hwnd)
            except Exception as e:
                logger.warning("[%s] DWM register failed for src=%s: %s",
                               self.thumbnail_id, source_hwnd, e)
                self._dwm_handle = None

    def _query_and_update_source_size(self) -> None:
        """Query source window size and update cached value."""
        if not self._dwm_handle:
            return
        try:
            self._source_size = self.backend.query_source_size(self._dwm_handle)
            logger.debug("[%s] Source size queried: %s", self.thumbnail_id, self._source_size)
        except Exception as e:
            logger.warning("[%s] query_source_size failed: %s", self.thumbnail_id, e)

    def _compute_dest_rect(self) -> Tuple[int, int, int, int]:
        """Compute DWM dest rect within overlay bounds.

        Returns (left, top, right, bottom) in overlay client coordinates.
        Accounts for active border inset and scaling mode.

        Modes:
          fit       – overlay shape is already aspect-locked, so fill entirely.
          stretch   – fill entire area regardless of aspect ratio (may distort).
          letterbox – preserve aspect ratio inside, black bars for the gap.
        """
        border = BORDER_WIDTH if (self._is_active_window and self.show_border) else 0
        avail_w = self.width - 2 * border
        avail_h = self.height - 2 * border

        if avail_w <= 0 or avail_h <= 0:
            return (border, border, self.width - border, self.height - border)

        src_w, src_h = self._source_size

        if self._scaling_mode == "letterbox" and src_w > 0 and src_h > 0:
            # Preserve aspect ratio inside the overlay, add bars for the gap
            scale = min(avail_w / src_w, avail_h / src_h)
            thumb_w = int(src_w * scale)
            thumb_h = int(src_h * scale)
            offset_x = border + (avail_w - thumb_w) // 2
            offset_y = border + (avail_h - thumb_h) // 2
            return (offset_x, offset_y, offset_x + thumb_w, offset_y + thumb_h)

        # fit and stretch both fill the entire available area.
        # fit relies on the overlay window itself being aspect-locked via resize.
        # stretch just fills regardless of proportions.
        return (border, border, border + avail_w, border + avail_h)

    def _update_dwm_properties(self) -> None:
        """Sync DWM thumbnail properties (dest rect, opacity, visibility)."""
        if not self._dwm_handle:
            return
        try:
            dest_rect = self._compute_dest_rect()
            # DWM thumbnail opacity is separate from window opacity; use 255 (full)
            # so the window-level layered opacity controls overall transparency.
            self.backend.update_properties(
                self._dwm_handle,
                dest_rect=dest_rect,
                opacity=255,
                visible=True,
                source_client_only=True,
            )
            self._props_fail_count = 0
        except Exception as e:
            # Tolerate transient failures; only mark unavailable after repeated errors
            self._props_fail_count = getattr(self, '_props_fail_count', 0) + 1
            if self._props_fail_count >= 5:
                logger.warning("[%s] DWM update_properties failed %d times, marking unavailable: %s",
                               self.thumbnail_id, self._props_fail_count, e)
                self._unregister_dwm()
                self._is_available = False
                self._invalidate()
            else:
                logger.debug("[%s] DWM update_properties transient failure (%d): %s",
                             self.thumbnail_id, self._props_fail_count, e)

    def _unregister_dwm(self) -> None:
        """Safely unregister current DWM thumbnail."""
        if self._dwm_handle is not None:
            try:
                self.backend.unregister(self._dwm_handle)
                logger.debug("[%s] DWM thumbnail unregistered", self.thumbnail_id)
            except Exception as e:
                logger.warning("[%s] DWM unregister error: %s", self.thumbnail_id, e)
            self._dwm_handle = None

    def poll_source_size(self) -> None:
        """Check if source window size changed and update dest rect if needed."""
        if not self._dwm_handle:
            return
        try:
            new_size = self.backend.query_source_size(self._dwm_handle)
            self._poll_fail_count = 0
            if new_size != self._source_size:
                logger.debug("[%s] Source size changed: %s -> %s",
                             self.thumbnail_id, self._source_size, new_size)
                self._source_size = new_size
                self._update_dwm_properties()
        except Exception as e:
            # Tolerate transient failures; only mark unavailable after repeated errors
            self._poll_fail_count = getattr(self, '_poll_fail_count', 0) + 1
            if self._poll_fail_count >= 10:
                logger.warning("[%s] poll_source_size failed %d times, marking unavailable: %s",
                               self.thumbnail_id, self._poll_fail_count, e)
                self._unregister_dwm()
                self._is_available = False
                self._invalidate()
            else:
                logger.debug("[%s] poll_source_size transient failure (%d): %s",
                             self.thumbnail_id, self._poll_fail_count, e)

    # ── Win32 message handling ──────────────────────────────────────────

    def _handle_message(self, msg, wparam, lparam) -> Optional[int]:
        """Handle Win32 messages. Return int to skip DefWindowProc, or None."""
        try:
            if msg == WM_PAINT:
                self._on_paint()
                return 0
            elif msg == WM_ERASEBKGND:
                return 1  # we handle background in WM_PAINT
            elif msg == WM_LBUTTONDOWN:
                self._on_left_press(lparam, wparam)
                return 0
            elif msg == WM_LBUTTONUP:
                self._on_left_release(lparam, wparam)
                return 0
            elif msg == WM_RBUTTONDOWN:
                self._on_right_press(lparam, wparam)
                return 0
            elif msg == WM_RBUTTONUP:
                self._on_right_release(lparam, wparam)
                return 0
            elif msg == WM_MOUSEMOVE:
                self._on_mouse_move(lparam, wparam)
                return 0
            elif msg == WM_MOUSELEAVE:
                self._on_mouse_leave()
                return 0
            elif msg == WM_TIMER:
                if wparam == TIMER_ID_UPDATE:
                    self._on_update_timer()
                return 0
            elif msg == WM_DPICHANGED:
                self._on_dpi_changed(lparam)
                return 0
            elif msg == WM_DESTROY:
                logger.debug("[%s] WM_DESTROY received", self.thumbnail_id)
                _window_map.pop(self.hwnd, None)
                return None
        except Exception as e:
            logger.error("[%s] Error handling message 0x%04X: %s",
                         self.thumbnail_id, msg, e, exc_info=True)
        return None

    # ── Painting ────────────────────────────────────────────────────────

    def _on_paint(self) -> None:
        """Handle WM_PAINT: draw border, unavailable state, and title bar."""
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(self.hwnd, ctypes.byref(ps))
        if not hdc:
            logger.warning("[%s] BeginPaint returned null HDC", self.thumbnail_id)
            return

        try:
            # Fill background black (visible in letterbox/pillarbox areas)
            rc = ctypes.wintypes.RECT(0, 0, self.width, self.height)
            brush_black = gdi32.CreateSolidBrush(COLOR_BLACK)
            if brush_black:
                user32.FillRect(hdc, ctypes.byref(rc), brush_black)
                gdi32.DeleteObject(brush_black)

            # Active border
            if self._is_active_window and self.show_border:
                self._paint_border(hdc)

            # Unavailable state
            if not self._is_available:
                self._paint_unavailable(hdc)

            # Title bar overlay (when mouse inside)
            if self._mouse_inside:
                self._paint_title_bar(hdc)

        except Exception as e:
            logger.warning("[%s] Paint error: %s", self.thumbnail_id, e)
        finally:
            user32.EndPaint(self.hwnd, ctypes.byref(ps))

    def _paint_border(self, hdc) -> None:
        """Draw orange active border."""
        try:
            pen = gdi32.CreatePen(PS_SOLID, BORDER_WIDTH, COLOR_BORDER_ACTIVE)
            if not pen:
                return
            old_pen = gdi32.SelectObject(hdc, pen)
            old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))

            # Draw rectangle inset by half the pen width
            half = BORDER_WIDTH // 2
            gdi32.Rectangle(hdc, half, half, self.width - half, self.height - half)

            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(pen)
        except Exception as e:
            logger.warning("[%s] Paint border error: %s", self.thumbnail_id, e)

    def _paint_unavailable(self, hdc) -> None:
        """Draw 'Not Available' blue screen."""
        try:
            rc = ctypes.wintypes.RECT(0, 0, self.width, self.height)
            brush = gdi32.CreateSolidBrush(COLOR_UNAVAILABLE_BG)
            if brush:
                user32.FillRect(hdc, ctypes.byref(rc), brush)
                gdi32.DeleteObject(brush)

            # Draw centered text
            gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
            gdi32.SetTextColor(hdc, 0x00FFFFFF)  # white

            font = gdi32.CreateFontW(
                16, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Segoe UI"
            )
            if font:
                old_font = gdi32.SelectObject(hdc, font)
                text = "Not Available"
                user32.DrawTextW(hdc, text, len(text), ctypes.byref(rc), 0x25)  # DT_CENTER | DT_VCENTER | DT_SINGLELINE
                gdi32.SelectObject(hdc, old_font)
                gdi32.DeleteObject(font)
        except Exception as e:
            logger.warning("[%s] Paint unavailable error: %s", self.thumbnail_id, e)

    def _paint_title_bar(self, hdc) -> None:
        """Draw title bar overlay at top of window."""
        try:
            rc = ctypes.wintypes.RECT(0, 0, self.width, TITLE_BAR_HEIGHT)
            brush = gdi32.CreateSolidBrush(COLOR_TITLE_BG)
            if brush:
                user32.FillRect(hdc, ctypes.byref(rc), brush)
                gdi32.DeleteObject(brush)

            # Title text
            gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
            gdi32.SetTextColor(hdc, 0x00FFFFFF)  # white
            font = gdi32.CreateFontW(
                14, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Segoe UI"
            )
            if not font:
                return
            old_font = gdi32.SelectObject(hdc, font)

            title = self._build_overlay_title()
            text_rc = ctypes.wintypes.RECT(8, 0, self.width - 30, TITLE_BAR_HEIGHT)
            user32.DrawTextW(hdc, title, len(title), ctypes.byref(text_rc), 0x24)  # DT_SINGLELINE | DT_VCENTER

            # Close button "X"
            close_rc = ctypes.wintypes.RECT(self.width - 25, 0, self.width, TITLE_BAR_HEIGHT)
            close_text = "X"
            user32.DrawTextW(hdc, close_text, len(close_text), ctypes.byref(close_rc), 0x25)  # DT_CENTER | DT_VCENTER | DT_SINGLELINE

            gdi32.SelectObject(hdc, old_font)
            gdi32.DeleteObject(font)
        except Exception as e:
            logger.warning("[%s] Paint title bar error: %s", self.thumbnail_id, e)

    def _invalidate(self) -> None:
        """Force a repaint."""
        if self.hwnd:
            try:
                user32.InvalidateRect(self.hwnd, None, True)
            except Exception as e:
                logger.debug("[%s] InvalidateRect failed: %s", self.thumbnail_id, e)

    # ── Title helpers ───────────────────────────────────────────────────

    def _build_overlay_title(self) -> str:
        """Build title bar text including slot number when assigned."""
        title = str(self.config.get("window_title", "ScreenAlert") or "ScreenAlert").strip()
        slot_value = self.config.get("window_slot")
        try:
            slot_num = int(slot_value)
        except (TypeError, ValueError):
            slot_num = None
        prefix = f"[{slot_num}] " if slot_num is not None and 1 <= slot_num <= 10 else ""
        return f"{prefix}{title}"[:48]

    def refresh_title(self) -> None:
        """Refresh title bar by repainting."""
        if self._mouse_inside:
            self._invalidate()

    # ── Mouse interactions ──────────────────────────────────────────────

    def _get_screen_pos(self, lparam) -> Tuple[int, int]:
        """Extract screen coordinates from mouse message lparam."""
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        pt = ctypes.wintypes.POINT(x, y)
        user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        return (pt.x, pt.y)

    def _get_client_pos(self, lparam) -> Tuple[int, int]:
        """Extract client coordinates from mouse message lparam."""
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        return (x, y)

    @staticmethod
    def _is_shift_pressed(wparam) -> bool:
        return bool(wparam & MK_SHIFT)

    def _is_within_threshold(self, screen_x: int, screen_y: int) -> bool:
        dx = abs(screen_x - self.pointer_start[0])
        dy = abs(screen_y - self.pointer_start[1])
        return dx <= DRAG_THRESHOLD_PX and dy <= DRAG_THRESHOLD_PX

    def _track_mouse_leave(self) -> None:
        """Request WM_MOUSELEAVE notification."""
        try:
            tme = TRACKMOUSEEVENT()
            tme.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
            tme.dwFlags = TME_LEAVE
            tme.hwndTrack = self.hwnd
            tme.dwHoverTime = 0
            user32.TrackMouseEvent(ctypes.byref(tme))
        except Exception as e:
            logger.debug("[%s] TrackMouseEvent failed: %s", self.thumbnail_id, e)

    def _on_mouse_move(self, lparam, wparam) -> None:
        screen_x, screen_y = self._get_screen_pos(lparam)

        if not self._mouse_inside:
            self._mouse_inside = True
            self._track_mouse_leave()
            self._invalidate()  # show title bar

        # Handle drag/resize
        if self.left_pressed and self.right_pressed and self.interaction_state not in ("resizing", "sync_resizing"):
            self._begin_resize(screen_x, screen_y, sync=self._is_shift_pressed(wparam))

        if self.interaction_state == "pending_focus" and not self._is_within_threshold(screen_x, screen_y):
            self._did_move_or_resize = True

        if self.interaction_state == "moving":
            self._apply_move(screen_x, screen_y)
        elif self.interaction_state in ("resizing", "sync_resizing"):
            self._apply_resize(screen_x, screen_y)

    def _on_mouse_leave(self) -> None:
        self._mouse_inside = False
        self._invalidate()  # hide title bar

    def _on_left_press(self, lparam, wparam) -> None:
        user32.SetCapture(self.hwnd)
        screen_x, screen_y = self._get_screen_pos(lparam)
        self.left_pressed = True

        # Check close button hit
        client_x, client_y = self._get_client_pos(lparam)
        if self._is_close_button_hit(client_x, client_y):
            logger.debug("[%s] Close button clicked", self.thumbnail_id)
            self._on_close_button()
            return

        if self.right_pressed:
            self._begin_resize(screen_x, screen_y, sync=self._is_shift_pressed(wparam))
        else:
            self._begin_interaction(screen_x, screen_y)
            self.interaction_state = "pending_focus"
            self._did_move_or_resize = False

    def _on_left_release(self, lparam, wparam) -> None:
        self.left_pressed = False
        screen_x, screen_y = self._get_screen_pos(lparam)
        self._finalize_interaction(screen_x, screen_y, released_button='left')
        if not self.left_pressed and not self.right_pressed:
            user32.ReleaseCapture()

    def _on_right_press(self, lparam, wparam) -> None:
        user32.SetCapture(self.hwnd)
        screen_x, screen_y = self._get_screen_pos(lparam)
        self.right_pressed = True
        if self.left_pressed:
            self._begin_resize(screen_x, screen_y, sync=self._is_shift_pressed(wparam))
        else:
            self._begin_move(screen_x, screen_y)

    def _on_right_release(self, lparam, wparam) -> None:
        self.right_pressed = False
        screen_x, screen_y = self._get_screen_pos(lparam)
        self._finalize_interaction(screen_x, screen_y, released_button='right')
        if not self.left_pressed and not self.right_pressed:
            user32.ReleaseCapture()

    def _is_close_button_hit(self, client_x: int, client_y: int) -> bool:
        """Check if click is on close button area."""
        if not self._mouse_inside:
            return False
        return (client_y < TITLE_BAR_HEIGHT and client_x >= self.width - 25)

    def _on_close_button(self) -> None:
        """Handle overlay close click."""
        try:
            self._emit_interaction("overlay_closed", {})
        except Exception as e:
            logger.warning("[%s] Close button callback error: %s", self.thumbnail_id, e)
        self.set_user_visibility(False)

    # ── Interaction state machine ───────────────────────────────────────

    def _begin_interaction(self, screen_x: int, screen_y: int) -> None:
        self.pointer_start = (screen_x, screen_y)
        self.start_geometry = {
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
        }

    def _begin_move(self, screen_x: int, screen_y: int) -> None:
        self.interaction_state = "moving"
        self._did_move_or_resize = False
        self._begin_interaction(screen_x, screen_y)
        logger.debug("[%s] Begin move from (%s,%s)", self.thumbnail_id, screen_x, screen_y)

    def _begin_resize(self, screen_x: int, screen_y: int, sync: bool) -> None:
        self.interaction_state = "sync_resizing" if sync else "resizing"
        self._did_move_or_resize = False
        self._begin_interaction(screen_x, screen_y)
        self._sync_start_sizes = {}
        logger.debug("[%s] Begin %s from (%s,%s)",
                     self.thumbnail_id, self.interaction_state, screen_x, screen_y)
        if sync and self.owner_manager:
            try:
                source_width = self.start_geometry["width"]
                source_height = self.start_geometry["height"]
                geometries = self.owner_manager.get_all_thumbnail_geometries()
                self._sync_start_sizes = {
                    tid: (source_width, source_height)
                    for tid in geometries
                }
                for overlay in self.owner_manager._overlays.values():
                    overlay.set_size(source_width, source_height)
            except Exception as e:
                logger.warning("[%s] Sync resize init error: %s", self.thumbnail_id, e)

    def _apply_move(self, screen_x: int, screen_y: int) -> None:
        if self.interaction_state != "moving":
            return
        dx = screen_x - self.pointer_start[0]
        dy = screen_y - self.pointer_start[1]
        new_x = self.start_geometry["x"] + dx
        new_y = self.start_geometry["y"] + dy
        self.set_position(new_x, new_y)
        self._did_move_or_resize = True

    def _constrain_size_for_mode(self, target_w: int, target_h: int,
                                 start_w: int, start_h: int,
                                 dx: int, dy: int) -> Tuple[int, int]:
        """Apply scaling mode constraints to a resize target."""
        if self._scaling_mode == "fit":
            src_w, src_h = self._source_size
            if src_w > 0 and src_h > 0:
                aspect = src_h / src_w
                # Use whichever axis moved more as the driver
                if abs(dx) >= abs(dy):
                    target_h = int(target_w * aspect)
                else:
                    target_w = int(target_h / aspect)
        target_w = max(THUMBNAIL_MIN_WIDTH, min(target_w, THUMBNAIL_MAX_WIDTH))
        target_h = max(THUMBNAIL_MIN_HEIGHT, min(target_h, THUMBNAIL_MAX_HEIGHT))
        return target_w, target_h

    def _apply_resize(self, screen_x: int, screen_y: int) -> None:
        if self.interaction_state not in ("resizing", "sync_resizing"):
            return

        dx = screen_x - self.pointer_start[0]
        dy = screen_y - self.pointer_start[1]
        self._did_move_or_resize = True

        if self.interaction_state == "sync_resizing" and self.owner_manager:
            try:
                for tid, overlay in self.owner_manager._overlays.items():
                    start_size = self._sync_start_sizes.get(tid, (overlay.width, overlay.height))
                    start_w, start_h = start_size
                    raw_w = start_w + dx
                    raw_h = start_h + dy
                    target_w, target_h = overlay._constrain_size_for_mode(
                        raw_w, raw_h, start_w, start_h, dx, dy)
                    overlay.set_size(target_w, target_h)
            except Exception as e:
                logger.warning("[%s] Sync resize apply error: %s", self.thumbnail_id, e)
            return

        start_w = self.start_geometry["width"]
        start_h = self.start_geometry["height"]
        raw_w = start_w + dx
        raw_h = start_h + dy
        target_w, target_h = self._constrain_size_for_mode(
            raw_w, raw_h, start_w, start_h, dx, dy)
        self.set_size(target_w, target_h)

    def _finalize_interaction(self, screen_x: int, screen_y: int, released_button: str) -> None:
        state = self.interaction_state

        if state == "pending_focus":
            if released_button == 'left' and not self.right_pressed and not self._did_move_or_resize:
                if self._is_available:
                    logger.debug("[%s] Activated via left-click", self.thumbnail_id)
                    self._emit_interaction("activated", {})
            self.interaction_state = "idle"
            return

        if state == "moving" and released_button == 'right':
            logger.debug("[%s] Move completed to (%s,%s)", self.thumbnail_id, self.x, self.y)
            self._emit_interaction(
                "position_changed",
                {"x": self.x, "y": self.y, "width": self.width, "height": self.height},
            )
            self.interaction_state = "idle"
            return

        if state == "resizing":
            if not self.left_pressed and not self.right_pressed:
                logger.debug("[%s] Resize completed to %sx%s",
                             self.thumbnail_id, self.width, self.height)
                self._emit_interaction(
                    "size_changed",
                    {"x": self.x, "y": self.y, "width": self.width, "height": self.height},
                )
                self.interaction_state = "idle"
            return

        if state == "sync_resizing":
            if not self.left_pressed and not self.right_pressed:
                geometries = {}
                if self.owner_manager:
                    geometries = self.owner_manager.get_all_thumbnail_geometries()
                logger.debug("[%s] Sync resize completed (%d overlays)",
                             self.thumbnail_id, len(geometries))
                self._emit_interaction("bulk_geometry_changed", {"geometries": geometries})
                self.interaction_state = "idle"
            return

    def _emit_interaction(self, action: str, payload: Optional[Dict] = None) -> None:
        if not self.manager_callback:
            return
        try:
            self.manager_callback(self.thumbnail_id, action, payload or {})
        except TypeError:
            try:
                self.manager_callback(self.thumbnail_id, action)
            except Exception as error:
                logger.warning("[%s] Interaction callback failed (fallback): %s",
                               self.thumbnail_id, error)
        except Exception as error:
            logger.warning("[%s] Interaction callback failed for '%s': %s",
                           self.thumbnail_id, action, error)

    # ── Timer ───────────────────────────────────────────────────────────

    def start_update_timer(self, interval_ms: int) -> None:
        """Start the periodic DWM property update timer."""
        if self.hwnd:
            try:
                user32.SetTimer(self.hwnd, TIMER_ID_UPDATE, interval_ms, None)
                logger.debug("[%s] Update timer started: %dms", self.thumbnail_id, interval_ms)
            except Exception as e:
                logger.warning("[%s] SetTimer failed: %s", self.thumbnail_id, e)

    def stop_update_timer(self) -> None:
        """Stop the periodic update timer."""
        if self.hwnd:
            try:
                user32.KillTimer(self.hwnd, TIMER_ID_UPDATE)
            except Exception as e:
                logger.debug("[%s] KillTimer failed: %s", self.thumbnail_id, e)

    def _on_update_timer(self) -> None:
        """Periodic DWM update: poll source size, refresh properties."""
        try:
            if self._dwm_handle and self._is_available:
                self.poll_source_size()
        except Exception as e:
            logger.warning("[%s] Update timer error: %s", self.thumbnail_id, e)

    # ── DPI ─────────────────────────────────────────────────────────────

    def _on_dpi_changed(self, lparam) -> None:
        """Handle WM_DPICHANGED: reposition/resize for new DPI."""
        try:
            suggested_rect = ctypes.cast(lparam, ctypes.POINTER(ctypes.wintypes.RECT)).contents
            new_x = suggested_rect.left
            new_y = suggested_rect.top
            new_w = suggested_rect.right - suggested_rect.left
            new_h = suggested_rect.bottom - suggested_rect.top
            logger.debug("[%s] DPI changed: new geometry (%s,%s) %sx%s",
                         self.thumbnail_id, new_x, new_y, new_w, new_h)
            user32.SetWindowPos(
                self.hwnd, None,
                new_x, new_y, new_w, new_h,
                SWP_NOZORDER | SWP_NOACTIVATE,
            )
            self.x = new_x
            self.y = new_y
            self.width = new_w
            self.height = new_h
            self._update_dwm_properties()
        except Exception as e:
            logger.warning("[%s] DPI change handling failed: %s", self.thumbnail_id, e)

    # ── Public API (called from message pump thread) ────────────────────

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        if self.hwnd:
            try:
                user32.SetWindowPos(
                    self.hwnd, None, x, y, 0, 0,
                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
                )
            except Exception as e:
                logger.warning("[%s] SetWindowPos (move) failed: %s", self.thumbnail_id, e)

    def set_size(self, width: int, height: int) -> None:
        width = max(THUMBNAIL_MIN_WIDTH, min(width, THUMBNAIL_MAX_WIDTH))
        height = max(THUMBNAIL_MIN_HEIGHT, min(height, THUMBNAIL_MAX_HEIGHT))
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        if self.hwnd:
            try:
                user32.SetWindowPos(
                    self.hwnd, None, 0, 0, width, height,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
                )
                self._update_dwm_properties()
                self._invalidate()
            except Exception as e:
                logger.warning("[%s] SetWindowPos (resize) failed: %s", self.thumbnail_id, e)

    def set_opacity(self, opacity: float) -> None:
        self.opacity = max(0.2, min(opacity, 1.0))
        if self.hwnd:
            try:
                alpha_byte = max(1, min(255, int(self.opacity * 255)))
                user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha_byte, LWA_ALPHA)
                logger.debug("[%s] Opacity set to %.2f", self.thumbnail_id, self.opacity)
            except Exception as e:
                logger.warning("[%s] SetLayeredWindowAttributes failed: %s", self.thumbnail_id, e)

    def set_topmost(self, on_top: bool) -> None:
        self.always_on_top = bool(on_top)
        if self.hwnd:
            try:
                insert_after = HWND_TOPMOST if on_top else HWND_NOTOPMOST
                user32.SetWindowPos(
                    self.hwnd, insert_after, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
                logger.debug("[%s] Topmost set to %s", self.thumbnail_id, on_top)
            except Exception as e:
                logger.warning("[%s] SetWindowPos (topmost) failed: %s", self.thumbnail_id, e)

    def set_show_border(self, enabled: bool) -> None:
        self.show_border = bool(enabled)
        self._update_dwm_properties()
        self._invalidate()

    def set_scaling_mode(self, mode: str) -> None:
        """Set overlay scaling mode: 'fit', 'stretch', or 'letterbox'."""
        if mode not in ("fit", "stretch", "letterbox"):
            mode = "fit"
        if self._scaling_mode == mode:
            return
        self._scaling_mode = mode
        logger.debug("[%s] Scaling mode: %s", self.thumbnail_id, mode)

        # Ensure we have current source dimensions before snapping
        self._query_and_update_source_size()

        # When switching to fit, snap overlay to source aspect ratio
        if mode == "fit":
            self._snap_to_aspect_ratio()

        self._update_dwm_properties()
        self._invalidate()  # repaint background for letterbox bars

    def _snap_to_aspect_ratio(self) -> None:
        """Resize overlay to match source window aspect ratio, keeping width."""
        src_w, src_h = self._source_size
        if src_w <= 0 or src_h <= 0:
            return
        aspect = src_h / src_w
        new_h = int(self.width * aspect)
        new_h = max(THUMBNAIL_MIN_HEIGHT, min(new_h, THUMBNAIL_MAX_HEIGHT))
        if new_h != self.height:
            logger.debug("[%s] Snap to aspect ratio: %dx%d -> %dx%d",
                         self.thumbnail_id, self.width, self.height, self.width, new_h)
            self.set_size(self.width, new_h)
            self._emit_interaction(
                "size_changed",
                {"width": self.width, "height": self.height},
            )

    def set_active_border(self, is_active: bool) -> None:
        if self._is_active_window == bool(is_active):
            return
        self._is_active_window = bool(is_active)
        logger.debug("[%s] Active border: %s", self.thumbnail_id, is_active)
        self._update_dwm_properties()
        self._invalidate()

        # Z-order: active overlay goes topmost among overlays
        if is_active and self.hwnd and self.always_on_top:
            try:
                user32.SetWindowPos(
                    self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
            except Exception as e:
                logger.warning("[%s] Z-order update failed: %s", self.thumbnail_id, e)

    def set_availability(self, available: bool, show_when_unavailable: bool = False) -> None:
        """Set availability state and update overlay presentation."""
        was_available = self._is_available
        was_show_unavail = self._show_when_unavailable

        # Skip if nothing changed
        if was_available == bool(available) and was_show_unavail == bool(show_when_unavailable):
            return

        self._is_available = bool(available)
        self._show_when_unavailable = bool(show_when_unavailable)

        logger.debug("[%s] Availability changed: %s -> %s (show_when_unavail=%s)",
                     self.thumbnail_id, was_available, available, show_when_unavailable)

        if not available and was_available:
            self._unregister_dwm()

        if not self.hwnd:
            return

        self._apply_visibility()

    def set_user_visibility(self, visible: bool) -> None:
        """Show/hide window per user action."""
        self._is_user_hidden = not bool(visible)
        logger.debug("[%s] User visibility: %s", self.thumbnail_id, visible)
        if not self.hwnd:
            return
        if self._is_user_hidden:
            user32.ShowWindow(self.hwnd, SW_HIDE)
        else:
            self._apply_visibility()

    def _apply_visibility(self) -> None:
        """Apply current visibility state."""
        if self._is_user_hidden:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            return
        if self._is_available:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self._invalidate()
        elif self._show_when_unavailable:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self._invalidate()
        else:
            user32.ShowWindow(self.hwnd, SW_HIDE)

    def is_visible(self) -> bool:
        if self._is_user_hidden:
            return False
        if not self.hwnd:
            return False
        try:
            return bool(user32.IsWindowVisible(self.hwnd))
        except Exception:
            return False

    def lift(self) -> None:
        """Bring overlay to front."""
        if self.hwnd:
            try:
                insert_after = HWND_TOPMOST if self.always_on_top else HWND_NOTOPMOST
                user32.SetWindowPos(
                    self.hwnd, insert_after, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )
            except Exception as e:
                logger.warning("[%s] Lift (SetWindowPos) failed: %s", self.thumbnail_id, e)

    # ── Cleanup ─────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Unregister DWM and destroy window."""
        logger.debug("[%s] Cleanup started", self.thumbnail_id)
        try:
            self.stop_update_timer()
        except Exception as e:
            logger.warning("[%s] Stop timer error during cleanup: %s", self.thumbnail_id, e)

        self._unregister_dwm()

        if self.hwnd:
            _window_map.pop(self.hwnd, None)
            try:
                user32.DestroyWindow(self.hwnd)
                logger.debug("[%s] Window destroyed: hwnd=%s", self.thumbnail_id, self.hwnd)
            except Exception as e:
                logger.warning("[%s] DestroyWindow failed: %s", self.thumbnail_id, e)
            self.hwnd = None
