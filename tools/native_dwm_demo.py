#!/usr/bin/env python3
"""
Native Win32 layered window DWM thumbnail demo.
Usage: python tools/native_dwm_demo.py --title "Window title to capture"

This creates a borderless native window and registers a DWM thumbnail of the target
window inside it so you see a live composited overlay.
"""
import ctypes
from ctypes import wintypes
# LRESULT is a pointer-sized signed integer; wintypes may not define it on all Python versions.
if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT_T = ctypes.c_longlong
else:
    LRESULT_T = ctypes.c_long
# Pointer-sized WPARAM/LPARAM types
if ctypes.sizeof(ctypes.c_void_p) == 8:
    WPARAM_T = ctypes.c_uint64
    LPARAM_T = ctypes.c_int64
else:
    WPARAM_T = ctypes.c_uint32
    LPARAM_T = ctypes.c_int32
import sys
import argparse

user32 = ctypes.windll.user32
dwm = ctypes.windll.dwmapi

# Prefer pywin32 for window enumeration to avoid ctypes callback fragility
try:
    import win32gui
except Exception:
    win32gui = None

WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_T, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)

# Keep references to ctypes callbacks alive at module scope to prevent GC
_wndproc_ref = None
_enumproc_ref = None

# Set common user32 prototypes once
try:
    user32.DefWindowProcW.restype = LRESULT_T
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
except Exception:
    pass
try:
    user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, LPARAM_T), LPARAM_T]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
except Exception:
    pass

def make_window(title, width=800, height=600, x=100, y=100):
    hInstance = wintypes.HINSTANCE(ctypes.windll.kernel32.GetModuleHandleW(None))
    className = 'ScreenAlertNativeOverlay'

    # keep some state for mouse/close handling
    state = {
        'close_pressed': False,
        'close_rect': (width - 36, 6, width - 6, 36),
    }

    def point_in_rect(x, y, rect):
        l, t, r, b = rect
        return (x >= l and x <= r and y >= t and y <= b)

    def wndproc(hWnd, msg, wParam, lParam):
        # Windows message constants
        WM_DESTROY = 0x0002
        WM_PAINT = 0x000F
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_RBUTTONDOWN = 0x0204

        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        if msg == WM_PAINT:
            # Draw a simple close 'X' box in the top-right
            try:
                ps = wintypes.PAINTSTRUCT()
                hdc = user32.BeginPaint(hWnd, ctypes.byref(ps))
                # draw a filled rectangle for button
                left, top, right, bottom = state['close_rect']
                rect = ctypes.wintypes.RECT(left, top, right, bottom)
                # use FillRect via user32's GetSysColorBrush is complex; use DrawText to simulate
                # Draw an 'X' in the rect
                WHITE_BRUSH = 0
                # Set text color and background mode
                gdi32 = ctypes.windll.gdi32
                gdi32.SetTextColor(hdc, 0x00FFFFFF)
                gdi32.SetBkMode(hdc, 1)
                # draw X using DrawTextW
                DT_CENTER = 1
                DT_VCENTER = 4
                DT_SINGLELINE = 0x20
                user32.DrawTextW(hdc, 'X', -1, ctypes.byref(rect), DT_CENTER | DT_VCENTER | DT_SINGLELINE)
            except Exception:
                pass
            try:
                user32.EndPaint(hWnd, ctypes.byref(ps))
            except Exception:
                pass
            return 0

        if msg == WM_LBUTTONDOWN:
            x = wintypes.LOWORD(lParam)
            y = wintypes.HIWORD(lParam)
            if point_in_rect(x, y, state['close_rect']):
                state['close_pressed'] = True
                return 0
            # initiate window move (simulate titlebar drag)
            user32.ReleaseCapture()
            user32.SendMessageW(hWnd, 0x00A1, 2, 0)  # WM_NCLBUTTONDOWN, HTCAPTION=2
            return 0

        if msg == WM_LBUTTONUP:
            x = wintypes.LOWORD(lParam)
            y = wintypes.HIWORD(lParam)
            if state.get('close_pressed'):
                state['close_pressed'] = False
                if point_in_rect(x, y, state['close_rect']):
                    user32.PostQuitMessage(0)
                    return 0
            return 0

        if msg == WM_RBUTTONDOWN:
            # start bottom-right resize
            user32.ReleaseCapture()
            user32.SendMessageW(hWnd, 0x00A1, 17, 0)  # WM_NCLBUTTONDOWN, HTBOTTOMRIGHT=17
            return 0

        try:
            return user32.DefWindowProcW(wintypes.HWND(hWnd), wintypes.UINT(msg), WPARAM_T(wParam), LPARAM_T(lParam))
        except Exception:
            try:
                return user32.DefWindowProcW(hWnd, msg, wParam, lParam)
            except Exception:
                return 0

    wndproc_c = WNDPROCTYPE(wndproc)
    # keep reference global to avoid GC
    global _wndproc_ref
    _wndproc_ref = wndproc_c

    class WNDCLASS(ctypes.Structure):
        _fields_ = [('style', wintypes.UINT),
                    ('lpfnWndProc', WNDPROCTYPE),
                    ('cbClsExtra', ctypes.c_int),
                    ('cbWndExtra', ctypes.c_int),
                    ('hInstance', wintypes.HINSTANCE),
                    ('hIcon', ctypes.c_void_p),
                    ('hCursor', ctypes.c_void_p),
                    ('hbrBackground', ctypes.c_void_p),
                    ('lpszMenuName', wintypes.LPCWSTR),
                    ('lpszClassName', wintypes.LPCWSTR)]

    wndclass = WNDCLASS()
    wndclass.style = 0
    wndclass.lpfnWndProc = wndproc_c
    wndclass.cbClsExtra = wndclass.cbWndExtra = 0
    wndclass.hInstance = hInstance
    wndclass.hIcon = None
    wndclass.hCursor = None
    wndclass.hbrBackground = None
    wndclass.lpszMenuName = None
    wndclass.lpszClassName = className

    atom = user32.RegisterClassW(ctypes.byref(wndclass))
    if not atom:
        raise ctypes.WinError()

    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    x, y, w, h = x, y, width, height
    hwnd = user32.CreateWindowExW(0x00080000 | 0x00000080, className, 'DWM Thumbnail Demo', WS_POPUP | WS_VISIBLE,
                                  x, y, w, h, None, None, hInstance, None)
    if not hwnd:
        raise ctypes.WinError()

    # Make layered and topmost
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOPMOST = 0x00000008
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_LAYERED | WS_EX_TOPMOST
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

    return hwnd


def find_window_by_title(substr: str):
    """Find first visible top-level window whose title contains `substr`.

    Uses `win32gui.EnumWindows` from pywin32 (no ctypes EnumWindows fallback).
    If `pywin32` is not installed the function raises a RuntimeError.
    """
    if win32gui is None:
        raise RuntimeError('pywin32 (win32gui) is required for native_dwm_demo.py - please `pip install pywin32` in your venv')

    matches = []

    def _enum(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            text = win32gui.GetWindowText(hwnd) or ''
            if substr.lower() in text.lower():
                matches.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_enum, None)
    return matches[0] if matches else None


def register_dwm_thumbnail(dest_hwnd, src_hwnd, width, height, opacity=200):
    h_thumb = wintypes.HANDLE()
    res = dwm.DwmRegisterThumbnail(wintypes.HWND(dest_hwnd), wintypes.HWND(src_hwnd), ctypes.byref(h_thumb))
    if res != 0:
        raise ctypes.WinError(res)

    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

    class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
        _fields_ = [('dwFlags', ctypes.c_uint),
                    ('rcDestination', RECT),
                    ('rcSource', RECT),
                    ('opacity', ctypes.c_ubyte),
                    ('fVisible', wintypes.BOOL),
                    ('fSourceClientAreaOnly', wintypes.BOOL)]

    DWM_TNP_RECTDEST = 0x00000001
    DWM_TNP_OPACITY = 0x00000004
    DWM_TNP_VISIBLE = 0x00000008

    dest_rect = RECT(0, 0, int(width), int(height))
    src_rect = RECT(0, 0, 0, 0)
    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = DWM_TNP_RECTDEST | DWM_TNP_OPACITY | DWM_TNP_VISIBLE
    props.rcDestination = dest_rect
    props.rcSource = src_rect
    props.opacity = int(max(0, min(opacity, 255)))
    props.fVisible = True
    props.fSourceClientAreaOnly = False

    res2 = dwm.DwmUpdateThumbnailProperties(h_thumb, ctypes.byref(props))
    if res2 != 0:
        try:
            dwm.DwmUnregisterThumbnail(h_thumb)
        except Exception:
            pass
        raise ctypes.WinError(res2)

    return h_thumb


def message_loop():
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', required=True)
    parser.add_argument('--width', type=int, default=800)
    parser.add_argument('--height', type=int, default=600)
    args = parser.parse_args()

    print('Searching for target window with title:', repr(args.title))
    src = find_window_by_title(args.title)
    if not src:
        print('Target window not found')
        return 1
    print('Creating native window...')
    hwnd = make_window('ScreenAlert Native DWM Demo', width=args.width, height=args.height)

    print('Registering DWM thumbnail...')
    try:
        hthumb = register_dwm_thumbnail(hwnd, src, args.width, args.height, opacity=200)
        print('Thumbnail registered. Message loop running. Close window to exit.')
        message_loop()
        try:
            dwm.DwmUnregisterThumbnail(hthumb)
        except Exception:
            pass
    except Exception as e:
        print('DWM registration failed:', e)
        return 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
