"""Region selection overlay for selecting monitoring regions on actual window"""

import tkinter as tk
from typing import Tuple, List, Callable, Optional
import logging

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
        
        # Create full-screen overlay
        self.overlay = tk.Toplevel(parent_root)
        self.overlay.attributes('-alpha', 0.3)  # Semi-transparent
        self.overlay.attributes('-topmost', True)
        self.overlay.overrideredirect(True)
        
        # Make it full screen
        self.overlay.geometry(f"{self.overlay.winfo_screenwidth()}x{self.overlay.winfo_screenheight()}+0+0")
        
        # Dark canvas
        self.canvas = tk.Canvas(self.overlay, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", self._on_cancel)
        
        # Instructions text
        instruction_text = "Draw regions on the window. Press ESC when done."
        self.canvas.create_text(
            self.overlay.winfo_screenwidth() // 2,
            30,
            text=instruction_text,
            fill='yellow',
            font=('Arial', 14, 'bold')
        )
        
        logger.info("Region selection overlay created - draw regions with mouse, press ESC when done")
    
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
        
        self.canvas.create_rectangle(
            x, y,
            x + width, y + height,
            outline='lime', width=3, tags="preview_rect"
        )
        
        # Show dimensions
        dim_text = f"{width}x{height}px"
        self.canvas.delete("dimension_text")
        self.canvas.create_text(
            event.x_root + 10, event.y_root - 10,
            text=dim_text,
            fill='yellow',
            font=('Courier', 10, 'bold'),
            tags="dimension_text"
        )
    
    def _on_release(self, event: tk.Event) -> None:
        """Handle mouse release - save region"""
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
            
            # Draw saved region (fades slowly)
            self.canvas.delete("saved_regions")
            for i, (rx, ry, rw, rh) in enumerate(self.regions, 1):
                self.canvas.create_rectangle(
                    rx, ry, rx + rw, ry + rh,
                    outline='lime', width=2, tags="saved_regions"
                )
                self.canvas.create_text(
                    rx + 5, ry + 5,
                    text=f"{i}",
                    fill='lime',
                    font=('Arial', 12, 'bold'),
                    anchor='nw',
                    tags="saved_regions"
                )
            
            logger.info(f"Added region: {region}")
    
    def _on_cancel(self, event: tk.Event) -> None:
        """Handle ESC key - finish selection"""
        self.overlay.destroy()
        if self.on_complete:
            self.on_complete(self.regions)
    
    def show(self) -> List[Tuple[int, int, int, int]]:
        """Show overlay and wait for selection
        
        Returns:
            List of regions [(x, y, width, height), ...]
        """
        self.overlay.wait_window()
        return self.regions
