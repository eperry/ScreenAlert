"""Window management and capture"""

import logging
from typing import List, Dict, Optional, Tuple
import platform
import time

if platform.system() == "Windows":
    import win32gui
    import win32ui
    from ctypes import windll

logger = logging.getLogger(__name__)


class WindowManager:
    """Handles window detection and capture"""
    
    def __init__(self):
        """Initialize window manager"""
        self.window_cache = {}
        self.cache_time = 0
        self.cache_lifetime = 2.0  # seconds
    
    def get_window_list(self, use_cache=True) -> List[Dict]:
        """Get list of all visible windows
        
        Returns:
            List of window dicts: {
                'hwnd': handle,
                'title': window_title,
                'class': window_class,
                'rect': (left, top, right, bottom),
                'size': (width, height)
            }
        """
        now = time.time()
        if use_cache and self.window_cache and (now - self.cache_time) < self.cache_lifetime:
            return self.window_cache
        
        windows = []
        
        def enum_window_callback(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                title = win32gui.GetWindowText(hwnd)
                if not title or len(title.strip()) == 0:
                    return True
                
                try:
                    cls = win32gui.GetClassName(hwnd)
                except:
                    cls = "Unknown"
                
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # Skip very small windows (taskbar, system windows)
                if width < 50 or height < 50:
                    return True
                
                windows.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': cls,
                    'rect': rect,
                    'size': (width, height)
                })
                return True
            except Exception as e:
                logger.debug(f"Error enumerating window {hwnd}: {e}")
                return True
        
        try:
            win32gui.EnumWindows(enum_window_callback, None)
        except Exception as e:
            logger.error(f"Error getting window list: {e}")
        
        # Cache and return
        self.window_cache = windows
        self.cache_time = now
        return windows
    
    def find_window_by_hwnd(self, hwnd: int) -> Optional[Dict]:
        """Find window by handle"""
        try:
            if not win32gui.IsWindow(hwnd):
                return None
            
            if not win32gui.IsWindowVisible(hwnd):
                return None
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return None
            
            cls = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            return {
                'hwnd': hwnd,
                'title': title,
                'class': cls,
                'rect': rect,
                'size': (width, height)
            }
        except Exception as e:
            logger.debug(f"Error finding window {hwnd}: {e}")
            return None
    
    def find_window_by_title(self, title: str, exact=False) -> Optional[Dict]:
        """Find window by title
        
        Args:
            title: Window title to search for
            exact: If True, only exact matches; if False, allow partial matches
        
        Returns:
            First matching window or None
        """
        windows = self.get_window_list(use_cache=False)
        
        # Try exact match first
        for window in windows:
            if window['title'] == title:
                return window
        
        # Try partial match if not exact
        if not exact:
            title_lower = title.lower()
            for window in windows:
                if title_lower in window['title'].lower():
                    return window
        
        return None
    
    def find_windows_by_title(self, title: str, exact=False) -> List[Dict]:
        """Find all windows matching title"""
        windows = self.get_window_list(use_cache=False)
        results = []
        
        # Try exact match first
        for window in windows:
            if window['title'] == title:
                results.append(window)
        
        if results:
            return results
        
        # Try partial match if not exact
        if not exact:
            title_lower = title.lower()
            for window in windows:
                if title_lower in window['title'].lower():
                    results.append(window)
        
        return results
    
    def is_window_valid(self, hwnd: int) -> bool:
        """Check if window handle is valid and visible"""
        try:
            return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        except:
            return False
    
    def is_window_minimized(self, hwnd: int) -> bool:
        """Check if window is minimized"""
        try:
            return win32gui.IsIconic(hwnd)
        except:
            return False
    
    def get_window_rect(self, hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """Get window rectangle (left, top, right, bottom)"""
        try:
            if not self.is_window_valid(hwnd):
                return None
            return win32gui.GetWindowRect(hwnd)
        except:
            return None
    
    def get_window_size(self, hwnd: int) -> Optional[Tuple[int, int]]:
        """Get window size (width, height)"""
        rect = self.get_window_rect(hwnd)
        if not rect:
            return None
        return (rect[2] - rect[0], rect[3] - rect[1])
    
    def activate_window(self, hwnd: int) -> bool:
        """Bring window to front and activate it"""
        try:
            if not self.is_window_valid(hwnd):
                return False
            
            if self.is_window_minimized(hwnd):
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.error(f"Error activating window {hwnd}: {e}")
            return False
    
    def get_monitor_info(self) -> List[Dict]:
        """Get information about all monitors"""
        monitors = []
        
        try:
            import win32api
            
            def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                monitors.append({
                    'handle': hMonitor,
                    'rect': lprcMonitor,
                    'width': lprcMonitor[2] - lprcMonitor[0],
                    'height': lprcMonitor[3] - lprcMonitor[1],
                })
                return True
            
            win32api.EnumDisplayMonitors(None, None, monitor_enum_proc, 0)
        except Exception as e:
            logger.warning(f"Error getting monitor info: {e}, using primary monitor")
            # Fallback to primary monitor
            monitors = [{
                'handle': 0,
                'rect': (0, 0, 1920, 1080),
                'width': 1920,
                'height': 1080,
            }]
        
        return monitors
    
    def capture_window(self, hwnd: int) -> Optional['Image']:
        """Capture window screenshot
        
        Returns:
            PIL Image or None if capture failed
        """
        try:
            from PIL import Image
            
            # Validate window
            if not self.is_window_valid(hwnd):
                logger.debug(f"Window {hwnd} is not valid")
                return None
            
            # Get window rect
            rect = self.get_window_rect(hwnd)
            if not rect:
                logger.debug(f"Could not get rect for window {hwnd}")
                return None
            
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            if width <= 0 or height <= 0:
                logger.debug(f"Invalid window size: {width}x{height}")
                return None
            
            # Get device contexts
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # Capture using PrintWindow
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
            
            if not result:
                logger.debug(f"PrintWindow failed for {hwnd}")
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                return None
            
            # Convert to PIL Image
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = Image.frombytes('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), 
                                 bmpstr, 'raw', 'BGR', bmpinfo['bmWidth'] * 3, -1)
            
            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            return img
        
        except Exception as e:
            logger.debug(f"Error capturing window {hwnd}: {e}")
            return None
