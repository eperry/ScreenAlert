"""Region selection overlay for selecting monitoring regions on actual window"""

import tkinter as tk
from typing import Tuple, List, Callable, Optional
import logging
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

        # Track the target window client rectangle in screen coordinates.
        self.window_x, self.window_y, self.window_width, self.window_height = self._get_client_rect_screen()

        logger.info(
            "Region overlay target window: (%s, %s), size: %sx%s",
            self.window_x,
            self.window_y,
            self.window_width,
            self.window_height,
        )
        
        # Create full-screen overlay on the same monitor as the window
        self.overlay = tk.Toplevel(parent_root)
        self.overlay.attributes('-alpha', 0.28)
        self.overlay.attributes('-topmost', True)
        self.overlay.overrideredirect(True)
        
        # Position overlay exactly on top of the target app window.
        self.overlay.geometry(
            f"{self.window_width}x{self.window_height}+{self.window_x}+{self.window_y}"
        )
        
        # Dark canvas (semi-transparent so target app remains visible)
        self.canvas = tk.Canvas(self.overlay, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Draw a border around the selectable area (the app window itself).
        self.canvas.create_rectangle(
            1,
            1,
            self.window_width - 1,
            self.window_height - 1,
            outline='#00d4ff',
            width=2,
            tags='target_window'
        )
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", self._on_cancel)
        
        # Instructions text
        instruction_text = "Draw a region on the highlighted window. Selection auto-completes on mouse release."
        self.canvas.create_text(
            self.window_width // 2,
            30,
            text="Draw a region inside this app window. Selection auto-completes on mouse release.",
            fill='#ffff00',
            font=('Arial', 14, 'bold')
        )
        
        # ESC hint text at bottom
        esc_text = "Press ESC to cancel without saving"
        self.canvas.create_text(
            self.window_width // 2,
            self.window_height - 30,
            text=esc_text,
            fill='#ffaa00',
            font=('Arial', 12)
        )
        
        logger.info("Region selection overlay created - draw region with mouse, auto-completes on release")

    def _get_client_rect_screen(self) -> Tuple[int, int, int, int]:
        """Return target window client-area rect as (x, y, width, height) in screen coords."""
        try:
            client = win32gui.GetClientRect(self.window_hwnd)
            if not client:
                raise RuntimeError("GetClientRect returned empty")

            top_left = win32gui.ClientToScreen(self.window_hwnd, (0, 0))
            bottom_right = win32gui.ClientToScreen(self.window_hwnd, (client[2], client[3]))

            x = int(top_left[0])
            y = int(top_left[1])
            width = max(1, int(bottom_right[0] - top_left[0]))
            height = max(1, int(bottom_right[1] - top_left[1]))
            return x, y, width, height
        except Exception as error:
            logger.warning("Falling back to window rect for region overlay: %s", error)
            rect = win32gui.GetWindowRect(self.window_hwnd)
            x = int(rect[0])
            y = int(rect[1])
            width = max(1, int(rect[2] - rect[0]))
            height = max(1, int(rect[3] - rect[1]))
            return x, y, width, height
    
    def _on_press(self, event: tk.Event) -> None:
        """Handle mouse press"""
        self.is_selecting = True
        self.start_x = event.x
        self.start_y = event.y
    
    def _on_drag(self, event: tk.Event) -> None:
        """Handle mouse drag - draw preview rectangle"""
        if not self.is_selecting:
            return
        
        self.canvas.delete("preview_rect")

        x = min(self.start_x, event.x)
        y = min(self.start_y, event.y)
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        
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
                event.x + 10, event.y - 10,
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
        
        x = min(self.start_x, event.x)
        y = min(self.start_y, event.y)
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        
        # Only save if meets minimum size
        if width >= self.min_region_size and height >= self.min_region_size:
            # Convert overlay-local coordinates back to screen coordinates.
            region = (self.window_x + x, self.window_y + y, width, height)
            self.regions.append(region)
            logger.info(f"Added region: {region}, auto-completing selection")
            
            # Auto-complete after first region
            self.overlay.destroy()
        else:
            # Region too small, show message and continue
            self.canvas.delete("too_small_text")
            self.canvas.create_text(
                event.x,
                event.y - 30,
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

