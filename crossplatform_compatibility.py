"""
Cross-Platform Compatibility Layer for ScreenAlert
Add this to the top of screenalert.py to make it work on Linux with ACT
"""

import platform
import subprocess
import sys

# Detect platform
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"

# Import platform-specific modules
if IS_WINDOWS:
    try:
        import win32gui
        import win32ui
        import win32con
        import win32api
        WINDOWS_MODULES_AVAILABLE = True
    except ImportError:
        print("Warning: pywin32 not available. Some Windows features may not work.")
        WINDOWS_MODULES_AVAILABLE = False
else:
    # On non-Windows platforms, create mock modules to prevent import errors
    class MockWin32Module:
        def __getattr__(self, name):
            def mock_function(*args, **kwargs):
                raise NotImplementedError(f"win32 function {name} not available on {platform.system()}")
            return mock_function
    
    win32gui = MockWin32Module()
    win32ui = MockWin32Module()  
    win32con = MockWin32Module()
    win32api = MockWin32Module()
    WINDOWS_MODULES_AVAILABLE = False

def get_all_windows_crossplatform():
    """Cross-platform window enumeration"""
    if IS_WINDOWS and WINDOWS_MODULES_AVAILABLE:
        # Use your existing Windows implementation
        windows = []
        def enum_window_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title:
                    class_name = win32gui.GetClassName(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    windows.append({
                        'hwnd': hwnd,
                        'title': window_title,
                        'class': class_name, 
                        'rect': rect
                    })
        win32gui.EnumWindows(enum_window_callback, windows)
        return windows
    
    elif IS_LINUX:
        # Linux implementation using wmctrl and xwininfo
        windows = []
        try:
            result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        window_id = parts[0]
                        title = parts[3]
                        rect = get_window_geometry_linux(window_id)
                        windows.append({
                            'hwnd': window_id,
                            'title': title,
                            'class': 'unknown',
                            'rect': rect
                        })
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("wmctrl not found. Install with: sudo apt install wmctrl")
            # Fallback to empty list - app will work but without window selection
        return windows
    
    else:
        # macOS or other - return empty for now
        print(f"Window enumeration not implemented for {platform.system()}")
        return []

def get_window_geometry_linux(window_id):
    """Get window geometry on Linux using xwininfo"""
    try:
        result = subprocess.run(['xwininfo', '-id', window_id], capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        
        x = y = width = height = 0
        for line in lines:
            if 'Absolute upper-left X:' in line:
                x = int(line.split(':')[1].strip())
            elif 'Absolute upper-left Y:' in line:
                y = int(line.split(':')[1].strip())  
            elif 'Width:' in line:
                width = int(line.split(':')[1].strip())
            elif 'Height:' in line:
                height = int(line.split(':')[1].strip())
                
        return (x, y, x + width, y + height)  # left, top, right, bottom
    except:
        return (0, 0, 100, 100)  # Default rectangle

def capture_window_crossplatform(window_info):
    """Cross-platform window capture"""
    if IS_WINDOWS and WINDOWS_MODULES_AVAILABLE:
        # Use your existing Windows capture code
        return capture_window_windows(window_info['hwnd'])
    else:
        # Use pyautogui for other platforms  
        import pyautogui
        rect = window_info['rect']
        if rect != (0, 0, 100, 100):  # Not default
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            return pyautogui.screenshot(region=(left, top, width, height))
    return None

def is_window_valid_crossplatform(hwnd):
    """Cross-platform window validation"""
    if IS_WINDOWS and WINDOWS_MODULES_AVAILABLE:
        return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
    elif IS_LINUX:
        # For Linux, assume window_id from wmctrl is valid
        # Could add more validation here if needed
        return True
    return False

def get_monitor_info_crossplatform():
    """Cross-platform monitor information"""
    if IS_WINDOWS and WINDOWS_MODULES_AVAILABLE:
        # Use your existing Windows implementation
        monitors = []
        def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            monitor_info = {
                'left': lprcMonitor[0],
                'top': lprcMonitor[1], 
                'right': lprcMonitor[2],
                'bottom': lprcMonitor[3]
            }
            monitors.append(monitor_info)
            return True
        win32api.EnumDisplayMonitors(None, None, monitor_enum_proc, 0)
        return monitors
    else:
        # Fallback to primary monitor using pyautogui
        import pyautogui
        width, height = pyautogui.size()
        return [{'left': 0, 'top': 0, 'right': width, 'bottom': height}]

# Usage instructions:
# Replace your existing function calls with these cross-platform versions:
# get_all_windows() -> get_all_windows_crossplatform()
# capture_window() -> capture_window_crossplatform()  
# is_window_valid() -> is_window_valid_crossplatform()
# get_monitor_info() -> get_monitor_info_crossplatform()
