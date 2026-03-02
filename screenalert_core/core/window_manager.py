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
    
    def find_window_by_title(self, title: str, exact=False,
                            expected_size=None, size_tolerance=20,
                            expected_monitor_id=None,
                            expected_class_name=None) -> Optional[Dict]:
        """Find window by title with optional metadata filtering
        
        Args:
            title: Window title to search for
            exact: If True, only exact matches; if False, allow partial matches
            expected_size: Optional (width, height) to validate window size
            size_tolerance: Pixels of tolerance for size matching
            expected_monitor_id: Optional monitor index the window should be on
            expected_class_name: Optional window class name to match
        
        Returns:
            Best matching window or None
        """
        windows = self.get_window_list(use_cache=False)
        
        # Pre-filter by monitor/class metadata when available
        if expected_monitor_id is not None or expected_class_name:
            monitors = self.get_monitor_info()  # Fetch once for all windows
            metadata_matched = []
            for window in windows:
                class_ok = (not expected_class_name or
                            window.get('class') == expected_class_name)
                monitor_ok = True
                if expected_monitor_id is not None:
                    window_monitor_id = self.get_monitor_id_for_rect(
                        window.get('rect'), monitors=monitors)
                    monitor_ok = window_monitor_id == expected_monitor_id
                if class_ok and monitor_ok:
                    metadata_matched.append(window)
            if metadata_matched:
                windows = metadata_matched
        
        def _size_matches(window_size, exp_size, tolerance):
            if not exp_size:
                return True
            return (abs(window_size[0] - exp_size[0]) <= tolerance and
                    abs(window_size[1] - exp_size[1]) <= tolerance)
        
        # Exact title + size match
        for window in windows:
            if window['title'] == title:
                if _size_matches(window['size'], expected_size, size_tolerance):
                    return window
        
        # Exact title, largest by area (when no expected_size)
        if expected_size is None:
            exact_matches = [w for w in windows if w['title'] == title]
            if exact_matches:
                return max(exact_matches,
                           key=lambda w: w['size'][0] * w['size'][1])
        
        # Exact title without size validation (window may have resized)
        if not exact:
            for window in windows:
                if window['title'] == title:
                    return window
        
        # Partial / fuzzy matching (only when not exact)
        if not exact:
            title_lower = title.lower()
            for window in windows:
                if title_lower in window['title'].lower():
                    if _size_matches(window['size'], expected_size,
                                     size_tolerance):
                        return window
            for window in windows:
                if window['title'].lower() in title_lower:
                    if _size_matches(window['size'], expected_size,
                                     size_tolerance):
                        return window
            title_words = set(title_lower.split())
            for window in windows:
                window_words = set(window['title'].lower().split())
                if title_words and window_words:
                    common = title_words & window_words
                    ratio = len(common) / max(len(title_words),
                                              len(window_words))
                    if ratio >= 0.5 and len(common) >= 2:
                        if _size_matches(window['size'], expected_size,
                                         size_tolerance):
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
    
    def find_largest_window_by_title(self, title: str,
                                     expected_monitor_id=None,
                                     expected_class_name=None) -> Optional[Dict]:
        """Find the largest window matching title, optionally filtered by metadata
        
        Args:
            title: Window title to search for
            expected_monitor_id: Optional monitor index filter
            expected_class_name: Optional window class filter
        
        Returns:
            Largest matching window or None
        """
        windows = self.get_window_list(use_cache=False)
        
        # Apply metadata filter
        if expected_monitor_id is not None or expected_class_name:
            monitors = self.get_monitor_info()  # Fetch once for all windows
            filtered = []
            for window in windows:
                class_ok = (not expected_class_name or
                            window.get('class') == expected_class_name)
                monitor_ok = True
                if expected_monitor_id is not None:
                    monitor_ok = (self.get_monitor_id_for_rect(
                        window.get('rect'), monitors=monitors)
                        == expected_monitor_id)
                if class_ok and monitor_ok:
                    filtered.append(window)
            if filtered:
                windows = filtered
        
        # Exact matches
        matching = [w for w in windows if w['title'] == title]
        
        # Partial matches as fallback
        if not matching:
            title_lower = title.lower()
            matching = [w for w in windows
                        if title_lower in w['title'].lower()]
        
        if matching:
            return max(matching, key=lambda w: w['size'][0] * w['size'][1])
        return None
    
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
        """Get information about all monitors (DPI/scaling robust)"""
        monitors = []
        try:
            import win32api
            import win32gui
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()

            monitor_items = win32api.EnumDisplayMonitors(None, None)
            for hmonitor, _hdc, rect in monitor_items:
                if isinstance(rect, (tuple, list)) and len(rect) == 4:
                    left, top, right, bottom = rect
                else:
                    monitor_info = win32gui.GetMonitorInfo(hmonitor)
                    left, top, right, bottom = monitor_info.get('Monitor', (0, 0, 0, 0))

                monitors.append({
                    'handle': hmonitor,
                    'left': left,
                    'top': top,
                    'right': right,
                    'bottom': bottom,
                    'width': right - left,
                    'height': bottom - top
                })
        except Exception as e:
            logger.warning(f"Error getting monitor info: {e}, using primary monitor")
            # Fallback to primary monitor
            monitors = [{
                'handle': 0,
                'left': 0,
                'top': 0,
                'right': 1920,
                'bottom': 1080,
                'width': 1920,
                'height': 1080
            }]
        return monitors
    
    def get_monitor_id_for_rect(self, rect, monitors=None) -> int:
        """Determine which monitor a window rect belongs to using center point.
        
        Args:
            rect: (left, top, right, bottom) tuple
            monitors: Optional pre-fetched monitor list (avoids repeated EnumDisplayMonitors)
        
        Returns:
            Monitor index (0-based), 0 as fallback
        """
        if not rect:
            return 0
        
        if monitors is None:
            monitors = self.get_monitor_info()
        if not monitors:
            return 0
        
        center_x = (rect[0] + rect[2]) // 2
        center_y = (rect[1] + rect[3]) // 2
        
        for i, monitor in enumerate(monitors):
            left = monitor.get('left', 0)
            top = monitor.get('top', 0)
            right = monitor.get('right', left)
            bottom = monitor.get('bottom', top)
            if (left <= center_x < right and
                    top <= center_y < bottom):
                return i
        
        return 0
    
    def get_window_metadata(self, hwnd: int) -> Optional[Dict]:
        """Get current metadata for a live window handle.
        
        Returns dict with title, class, rect, size, monitor_id
        or None if the window is unavailable.
        """
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return None
            
            cls = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            if width <= 0 or height <= 0:
                return None
            
            return {
                'hwnd': hwnd,
                'title': title,
                'class': cls,
                'rect': rect,
                'size': (width, height),
                'monitor_id': self.get_monitor_id_for_rect(rect)
            }
        except Exception:
            return None
    
    @staticmethod
    def is_window_size_significantly_different(current_size, expected_size) -> bool:
        """Detect large size mismatches that usually indicate wrong window binding.
        
        Allows normal resize/fullscreen fluctuations but rejects major shifts
        (e.g. HWND reused by a completely different window).
        """
        if not current_size or not expected_size:
            return False
        
        expected_w = max(1, expected_size[0])
        expected_h = max(1, expected_size[1])
        current_w = max(1, current_size[0])
        current_h = max(1, current_size[1])
        
        width_ratio = current_w / expected_w
        height_ratio = current_h / expected_h
        
        return (width_ratio < 0.60 or width_ratio > 1.60 or
                height_ratio < 0.60 or height_ratio > 1.60)
    
    def validate_window_identity(self, hwnd: int,
                                  expected_title: str = None,
                                  expected_class: str = None,
                                  expected_monitor_id: int = None,
                                  expected_size=None) -> bool:
        """Validate that a window handle still corresponds to the expected window.
        
        Returns True if the window is valid and its identity matches expectations.
        Returns False if the window is gone or its metadata doesn't match
        (indicating HWND reuse or monitor migration).
        
        Title matching uses substring containment rather than strict equality
        because many apps change their title dynamically (e.g. adding page names
        or unsaved indicators).
        """
        metadata = self.get_window_metadata(hwnd)
        if metadata is None:
            return False
        
        # Use loose title matching: either must be a substring of the other,
        # so we catch dynamic title changes while still detecting HWND reuse.
        if expected_title:
            live_title = metadata['title'].lower()
            saved_title = expected_title.lower()
            if saved_title not in live_title and live_title not in saved_title:
                logger.debug(f"Window {hwnd} title mismatch: "
                             f"'{metadata['title']}' vs '{expected_title}'")
                return False
        
        if expected_class and metadata['class'] != expected_class:
            logger.debug(f"Window {hwnd} class mismatch: "
                         f"'{metadata['class']}' != '{expected_class}'")
            return False
        
        if expected_monitor_id is not None and metadata['monitor_id'] != expected_monitor_id:
            logger.debug(f"Window {hwnd} monitor mismatch: "
                         f"{metadata['monitor_id']} != {expected_monitor_id}")
            return False
        
        if self.is_window_size_significantly_different(
                metadata['size'], expected_size):
            logger.debug(f"Window {hwnd} size mismatch: "
                         f"{metadata['size']} vs expected {expected_size}")
            return False
        
        return True

    def is_foreground_fullscreen(self) -> bool:
        """Return True if the foreground window appears fullscreen on its monitor."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            rect = win32gui.GetWindowRect(hwnd)
            if not rect:
                return False
            monitors = self.get_monitor_info()
            monitor_id = self.get_monitor_id_for_rect(rect, monitors=monitors)
            if monitor_id < 0 or monitor_id >= len(monitors):
                return False
            mon = monitors[monitor_id]
            window_w = rect[2] - rect[0]
            window_h = rect[3] - rect[1]
            mon_w = mon.get('width', 0)
            mon_h = mon.get('height', 0)
            if mon_w <= 0 or mon_h <= 0:
                return False
            return window_w >= int(mon_w * 0.98) and window_h >= int(mon_h * 0.98)
        except Exception:
            return False
    
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
            
            width = bmpinfo['bmWidth']
            height = bmpinfo['bmHeight']
            bits_per_pixel = bmpinfo.get('bmBitsPixel', 32)
            
            logger.debug(f"Bitmap info: {width}x{height}, {bits_per_pixel} bpp")
            
            # Handle based on bits per pixel
            if bits_per_pixel == 32:
                # 32-bit bitmap (BGRA or BGRX)
                img = Image.frombuffer('RGB', (width, height), bmpstr, 
                                      'raw', 'BGRX', 0, 1)
            else:
                # 24-bit bitmap with padding
                stride = ((width * 3 + 3) // 4) * 4
                img = Image.frombytes('RGB', (width, height), bmpstr, 
                                     'raw', 'BGR', stride, -1)
            
            # Cleanup
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            return img
        
        except Exception as e:
            logger.debug(f"Error capturing window {hwnd}: {e}")
            return None
