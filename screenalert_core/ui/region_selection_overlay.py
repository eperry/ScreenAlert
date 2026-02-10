"""Region selection overlay for selecting monitoring regions on actual window"""

import tkinter as tk
from typing import Tuple, List, Callable, Optional
import logging
import win32api
import win32gui

logger = logging.getLogger(__name__)


class RegionSelectionOverlay:
    """Transparent overlay for selecting regions by drawing on the screen"""
    
    def __init__(self, window_hwnd: int, parent_root: tk.Tk):
        """Initialize region selection overlay
        
        Args:
            window_hwnd: Handle of the window being monitored
            parent_root: Parent tkinter root
        """
        self.window_hwnd = window_hwnd
        self.parent_root = parent_root
        self.regions: List[Tuple[int, int, int, int]] = []
        self.is_selecting = False
        self.start_x = 0
        self.start_y = 0
        self.min_region_size = 50
        self.on_complete: Optional[Callable[[List[Tuple[int, int, int, int]]], None]] = None
        
        # Get the window's monitor
        monitor_info = self._get_window_monitor()
        monitor_x = monitor_info['left']
        monitor_y = monitor_info['top']
        monitor_width = monitor_info['right'] - monitor_info['left']
        monitor_height = monitor_info['bottom'] - monitor_info['top']
        
        logger.info(f"Window on monitor: ({monitor_x}, {monitor_y}), size: {monitor_width}x{monitor_height}")
        
        # Create full-screen overlay on the same monitor as the window
        self.overlay = tk.Toplevel(parent_root)
        self.overlay.attributes('-alpha', 1.0)  # Fully opaque to gray out other apps
        self.overlay.attributes('-topmost', True)
        self.overlay.overrideredirect(True)
        
        # Position overlay on the target monitor
        self.overlay.geometry(f"{monitor_width}x{monitor_height}+{monitor_x}+{monitor_y}")
        
        # Dark canvas (fully opaque to gray out other windows)
        self.canvas = tk.Canvas(self.overlay, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", self._on_cancel)
        
        # Instructions text
        instruction_text = "Draw a region by clicking and dragging. Selection auto-completes when finished."
        self.canvas.create_text(
            monitor_width // 2,
            30,
            text=instruction_text,
            fill='#ffff00',
            font=('Arial', 14, 'bold')
        )
        
        # ESC hint text at bottom
        esc_text = "Press ESC to cancel without saving"
        self.canvas.create_text(
            monitor_width // 2,
            monitor_height - 30,
            text=esc_text,
            fill='#ffaa00',
            font=('Arial', 12)
        )
        
        logger.info("Region selection overlay created - draw region with mouse, auto-completes on release")
    
    def _get_window_monitor(self) -> dict:
        """Get monitor info for the window
        
        Returns:
            Dict with 'left', 'top', 'right', 'bottom' keys
        """
        try:
            # Get window rect
            rect = win32gui.GetWindowRect(self.window_hwnd)
            window_center_x = (rect[0] + rect[2]) // 2
            window_center_y = (rect[1] + rect[3]) // 2
            
            # Get monitor handle at that point
            monitor_handle = win32api.MonitorFromPoint((window_center_x, window_center_y))
            
            # Get monitor info
            monitor_info = win32api.GetMonitorInfo(monitor_handle)
            work_area = monitor_info['Work']
            
            return {
                'left': work_area[0],
                'top': work_area[1],
                'right': work_area[2],
                'bottom': work_area[3]
            }
        except Exception as e:
            logger.warning(f"Error getting monitor info, using primary: {e}")
            # Fallback to screen dimensions
            return {
                'left': 0,
                'top': 0,
                'right': tk.Tk().winfo_screenwidth(),
                'bottom': tk.Tk().winfo_screenheight()
            }
    
    def _on_press(self, event: tk.Event) -> None:
        """Handle mouse press"""
        self.is_selecting = True
        self.start_x = event.x_root
        self.start_y = event.y_root
    
    def _on_drag(self, event: tk.Event) -> None:
        """Handle mouse drag - draw preview rectangle"""
        if not self.is_selecting:
            return
        
        self.canvas.delete("preview_rect")
        
        x = min(self.start_x, event.x_root)
        y = min(self.start_y, event.y_root)
        width = abs(event.x_root - self.start_x)
        height = abs(event.y_root - self.start_y)
        
        if width > 0 and height > 0:
            self.canvas.create_rectangle(
                x, y,
                x + width, y + height,
                outline='#00ff00', width=3, tags="preview_rect"
            )
            
            # Show dimensions
            dim_text = f"{width}x{height}px"
            self.canvas.delete("dimension_text")
            self.canvas.create_text(
                event.x_root + 10, event.y_root - 10,
                text=dim_text,
                fill='#ffff00',
                font=('Courier', 10, 'bold'),
                tags="dimension_text"
            )
    
    def _on_release(self, event: tk.Event) -> None:
        """Handle mouse release - save region and auto-complete"""
        if not self.is_selecting:
            return
        
        self.is_selecting = False
        self.canvas.delete("preview_rect", "dimension_text")
        
        x = min(self.start_x, event.x_root)
        y = min(self.start_y, event.y_root)
        width = abs(event.x_root - self.start_x)
        height = abs(event.y_root - self.start_y)
        
        # Only save if meets minimum size
        if width >= self.min_region_size and height >= self.min_region_size:
            region = (x, y, width, height)
            self.regions.append(region)
            logger.info(f"Added region: {region}, auto-completing selection")
            
            # Auto-complete after first region
            self.overlay.destroy()
        else:
            # Region too small, show message and continue
            self.canvas.delete("too_small_text")
            self.canvas.create_text(
                event.x_root, event.y_root - 30,
                text=f"Too small ({width}x{height}). Min: {self.min_region_size}x{self.min_region_size}",
                fill='#ff4444',
                font=('Arial', 11, 'bold'),
                tags="too_small_text"
            )
            # Clear message after 2 seconds
            self.overlay.after(2000, lambda: self.canvas.delete("too_small_text"))
    
    def _on_cancel(self, event: tk.Event) -> None:
        """Handle ESC key - cancel selection"""
        logger.info("Region selection cancelled by user")
        self.regions = []  # Clear any regions
        self.overlay.destroy()
    
    def show(self) -> List[Tuple[int, int, int, int]]:
        """Show overlay and wait for selection
        
        Returns:
            List of regions [(x, y, width, height), ...]
        """
        self.overlay.wait_window()
        return self.regions

