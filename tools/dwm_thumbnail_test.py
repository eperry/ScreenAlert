"""
Simple DWM thumbnail demo script.
Usage: python tools/dwm_thumbnail_test.py --title "Target Window Title"

Creates a native Win32 window and registers a DWM thumbnail of the target window.
"""

import ctypes
from ctypes import wintypes
import sys
import argparse
import time

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

# --- Win32 constants ---
WS_OVERLAPPEDWINDOW = 0x00CF0000
CW_USEDEFAULT = -2147483648
WM_DESTROY = 0x0002

# DWM flags
DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008

# Basic RECT structure
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", ctypes.c_uint),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]

# WNDCLASS structure (minimal)
class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
    ]

# Platform-sized types for message parameters (safe on 32/64-bit)
HWND = ctypes.c_void_p
UINT = ctypes.c_uint
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t

# Window proc prototype using pointer-sized WPARAM/LPARAM to avoid overflow on 64-bit
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

# Ensure DefWindowProcW uses matching ctypes signatures
try:
    user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = LRESULT
except Exception:
    pass


@WNDPROC
def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def create_window():
    hInstance = kernel32.GetModuleHandleW(None)
    cls = WNDCLASS()
    cls.lpfnWndProc = ctypes.cast(wnd_proc, ctypes.c_void_p)
    cls.hInstance = hInstance
    cls.lpszClassName = "DwmThumbDemo"

    atom = user32.RegisterClassW(ctypes.byref(cls))
    if not atom:
        # Maybe class already registered, ignore
        pass

    hwnd = user32.CreateWindowExW(
        0,
        cls.lpszClassName,
        "DWM Thumbnail Demo",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        640, 480,
        None, None, hInstance, None
    )

    if not hwnd:
        raise RuntimeError("Failed to create window")

    user32.ShowWindow(hwnd, 1)
    user32.UpdateWindow(hwnd)
    return hwnd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', '-t', default='Calculator', help='Exact title of target window to thumbnail')
    args = parser.parse_args()

    print(f"Creating demo window...")
    hwnd = create_window()

    print(f"Searching for target window with title: {args.title!r}")
    target = user32.FindWindowW(None, args.title)
    if not target:
        print("Target window not found")
        print("Please open the target application with the exact window title, or run again with another title.")
        return

    # Prepare DWM function prototypes
    dwmapi.DwmRegisterThumbnail.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.POINTER(wintypes.HANDLE)]
    dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long
    dwmapi.DwmUpdateThumbnailProperties.argtypes = [wintypes.HANDLE, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
    dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long

    thumb = wintypes.HANDLE()
    hr = dwmapi.DwmRegisterThumbnail(hwnd, target, ctypes.byref(thumb))
    if hr != 0:
        print("DwmRegisterThumbnail failed:", hr)
        return

    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_OPACITY | DWM_TNP_VISIBLE
    # destination rectangle inside our window: leave a margin
    props.rcDestination = RECT(10, 10, 630, 470)
    props.opacity = 200  # 0-255
    props.fVisible = True
    props.fSourceClientAreaOnly = False

    hr = dwmapi.DwmUpdateThumbnailProperties(thumb, ctypes.byref(props))
    if hr != 0:
        print("DwmUpdateThumbnailProperties failed:", hr)
        return

    print("Thumbnail registered. Message loop running. Close window to exit.")

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == '__main__':
    main()
