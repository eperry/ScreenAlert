"""Region editor dialog for selecting monitoring regions"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import logging
from typing import Optional, Tuple, Dict, List

from screenalert_core.core.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class RegionEditorDialog:
    """Dialog for selecting regions in a window"""
    
    def __init__(self, parent: tk.Widget, window_image: Image.Image):
        """Initialize region editor
        
        Args:
            parent: Parent window
            window_image: PIL Image of the window
        """
        self.window_image = window_image
        self.regions: List[Tuple[int, int, int, int]] = []
        self.current_region: Optional[Tuple[int, int, int, int]] = None
        self.is_selecting = False
        self.start_x = 0
        self.start_y = 0
        self.min_region_size = 50

        # For drag-resize/move
        self.active_region_idx: Optional[int] = None
        self.drag_mode: Optional[str] = None  # 'move', 'resize', or None
        self.resize_handle: Optional[str] = None  # e.g. 'nw', 'n', 'ne', etc.
        self.drag_offset = (0, 0)
        
        # Create dialog (start with small size, will resize after loading image)
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Monitoring Regions")
        self.result = None
        self.dialog.geometry("400x300")  # Temporary size
        
        self._build_ui()
        self._load_image()
        self._resize_dialog_to_fit()
    
    def _build_ui(self) -> None:
        """Build dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instr_frame = ttk.LabelFrame(main_frame, text="Instructions", padding=5)
        instr_frame.pack(fill=tk.X, pady=(0, 10))
        
        instructions = """
• Click and drag on the image to select a region
• Multiple regions can be selected
• Regions will be used for monitoring changes
• Selected regions appear with green outline
"""
        ttk.Label(instr_frame, text=instructions, justify=tk.LEFT).pack()
        
        # Canvas for image
        canvas_frame = ttk.LabelFrame(main_frame, text="Window Preview", padding=5)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Dimension display label
        self.dimension_label = ttk.Label(canvas_frame, text="", font=("Courier", 10, "bold"),
                                        background="yellow", foreground="black")
        self.dimension_label.place_forget()  # Hidden initially
        
        # Create canvas with scrollbars
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        
        self.canvas = tk.Canvas(canvas_frame, bg="gray20", highlightthickness=0,
                               xscrollcommand=h_scrollbar.set,
                               yscrollcommand=v_scrollbar.set)
        
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)
        
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        
        # Regions list
        list_frame = ttk.LabelFrame(main_frame, text="Selected Regions", padding=5)
        list_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.regions_listbox = tk.Listbox(list_frame, height=6, font=("Courier", 9))
        self.regions_listbox.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, command=self.regions_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.regions_listbox.config(yscrollcommand=scrollbar.set)
        
        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Done", command=self._on_done).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear Last", command=self._on_clear_last).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _load_image(self) -> None:
        """Load window image onto canvas"""
        try:
            # Get available canvas space (dialog is 75% of screen)
            # Leave room for UI elements
            self.dialog.update_idletasks()
            available_width = int(self.dialog.winfo_width() * 0.95)
            available_height = int(self.dialog.winfo_height() * 0.65)  # Leave room for controls
            
            img = self.window_image
            
            # Resize to fit available space while maintaining aspect ratio
            if img.width > available_width or img.height > available_height:
                img = ImageProcessor.resize_image(img, available_width, available_height)
            
            # Convert to PhotoImage
            self.photo_image = ImageTk.PhotoImage(img)
            self.canvas_image_id = self.canvas.create_image(0, 0, image=self.photo_image, anchor="nw")
            
            # Configure canvas scroll region
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            
            # Store dimensions
            self.display_width = img.width
            self.display_height = img.height
            self.scale_x = self.window_image.width / img.width
            self.scale_y = self.window_image.height / img.height
            
            # Draw any existing regions
            self._draw_regions()
            
            logger.info(f"Loaded image: {img.width}x{img.height}, scale: {self.scale_x:.2f}x{self.scale_y:.2f}")
        
        except Exception as e:
            logger.error(f"Error loading image: {e}")
    
    def _on_canvas_press(self, event) -> None:
        """Handle mouse press on canvas (select, move, or resize region)"""
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        img_x = event.x + self.canvas.canvasx(0) - coords[0]
        img_y = event.y + self.canvas.canvasy(0) - coords[1]
        if img_x < 0 or img_y < 0 or img_x > self.display_width or img_y > self.display_height:
            return

        # Check if clicking on a region handle or body
        hit = self._hit_test_regions(img_x, img_y)
        if hit:
            idx, mode, handle = hit
            self.active_region_idx = idx
            self.drag_mode = mode
            self.resize_handle = handle
            rx, ry, rw, rh = self.regions[idx]
            if mode == 'move':
                self.drag_offset = (int(img_x * self.scale_x) - rx, int(img_y * self.scale_y) - ry)
            elif mode == 'resize':
                self.drag_offset = (int(img_x * self.scale_x), int(img_y * self.scale_y))
            return

        # Otherwise, start new region selection
        self.is_selecting = True
        self.start_x = int(img_x * self.scale_x)
        self.start_y = int(img_y * self.scale_y)
        self.active_region_idx = None
        self.drag_mode = None
        self.resize_handle = None
    
    def _on_canvas_drag(self, event) -> None:
        """Handle mouse drag on canvas (select, move, or resize region)"""
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        img_x = event.x + self.canvas.canvasx(0) - coords[0]
        img_y = event.y + self.canvas.canvasy(0) - coords[1]
        img_x = max(0, min(img_x, self.display_width))
        img_y = max(0, min(img_y, self.display_height))

        if self.is_selecting:
            # ...existing code for new region selection...
            end_x = int(img_x * self.scale_x)
            end_y = int(img_y * self.scale_y)
            x = min(self.start_x, end_x)
            y = min(self.start_y, end_y)
            width = abs(end_x - self.start_x)
            height = abs(end_y - self.start_y)
            if width > 0 and width < self.min_region_size:
                width = self.min_region_size
                if end_x < self.start_x:
                    end_x = self.start_x - width
                else:
                    end_x = self.start_x + width
            if height > 0 and height < self.min_region_size:
                height = self.min_region_size
                if end_y < self.start_y:
                    end_y = self.start_y - height
                else:
                    end_y = self.start_y + height
            start_display_x = int(self.start_x / self.scale_x)
            start_display_y = int(self.start_y / self.scale_y)
            end_display_x = int(end_x / self.scale_x)
            end_display_y = int(end_y / self.scale_y)
            x1 = min(start_display_x, end_display_x)
            y1 = min(start_display_y, end_display_y)
            x2 = max(start_display_x, end_display_x)
            y2 = max(start_display_y, end_display_y)
            self.canvas.delete("region_preview")
            self.canvas.create_rectangle(
                coords[0] + x1, coords[1] + y1,
                coords[0] + x2, coords[1] + y2,
                outline="lime", width=2, tags="region_preview"
            )
            dim_text = f"{width}x{height}px"
            self.dimension_label.config(text=dim_text)
            label_x = event.x + 15
            label_y = event.y - 25
            self.dimension_label.place(x=label_x, y=label_y)
        elif self.active_region_idx is not None and self.drag_mode:
            # Dragging existing region (move or resize)
            rx, ry, rw, rh = self.regions[self.active_region_idx]
            orig_rx, orig_ry, orig_rw, orig_rh = rx, ry, rw, rh
            if self.drag_mode == 'move':
                new_x = int(img_x * self.scale_x) - self.drag_offset[0]
                new_y = int(img_y * self.scale_y) - self.drag_offset[1]
                # Clamp to image bounds
                new_x = max(0, min(new_x, self.window_image.width - rw))
                new_y = max(0, min(new_y, self.window_image.height - rh))
                self.regions[self.active_region_idx] = (new_x, new_y, rw, rh)
            elif self.drag_mode == 'resize' and self.resize_handle:
                # Resize logic for each handle
                px = int(img_x * self.scale_x)
                py = int(img_y * self.scale_y)
                x, y, w, h = rx, ry, rw, rh
                min_size = self.min_region_size
                if 'n' in self.resize_handle:
                    new_h = h + (y - py)
                    if new_h >= min_size:
                        h = new_h
                        y = py
                if 's' in self.resize_handle:
                    h = max(min_size, py - y)
                if 'w' in self.resize_handle:
                    new_w = w + (x - px)
                    if new_w >= min_size:
                        w = new_w
                        x = px
                if 'e' in self.resize_handle:
                    w = max(min_size, px - x)
                # Clamp
                x = max(0, min(x, self.window_image.width - w))
                y = max(0, min(y, self.window_image.height - h))
                w = min(w, self.window_image.width - x)
                h = min(h, self.window_image.height - y)
                self.regions[self.active_region_idx] = (x, y, w, h)
            self._draw_regions(active_idx=self.active_region_idx, show_handles=True)
            # Show dimensions
            dim_text = f"{self.regions[self.active_region_idx][2]}x{self.regions[self.active_region_idx][3]}px"
            self.dimension_label.config(text=dim_text)
            label_x = event.x + 15
            label_y = event.y - 25
            self.dimension_label.place(x=label_x, y=label_y)
    
    def _on_canvas_release(self, event) -> None:
        """Handle mouse release on canvas (finish select, move, or resize)"""
        if self.is_selecting:
            self.is_selecting = False
            self.canvas.delete("region_preview")
            self.dimension_label.place_forget()  # Hide dimension label
            coords = self.canvas.coords(self.canvas_image_id)
            if not coords:
                return
            img_x = event.x + self.canvas.canvasx(0) - coords[0]
            img_y = event.y + self.canvas.canvasy(0) - coords[1]
            img_x = max(0, min(img_x, self.display_width))
            img_y = max(0, min(img_y, self.display_height))
            end_x = int(img_x * self.scale_x)
            end_y = int(img_y * self.scale_y)
            x = min(self.start_x, end_x)
            y = min(self.start_y, end_y)
            width = abs(end_x - self.start_x)
            height = abs(end_y - self.start_y)
            if width < self.min_region_size:
                width = self.min_region_size
            if height < self.min_region_size:
                height = self.min_region_size
            if x + width > self.window_image.width:
                x = self.window_image.width - width
            if y + height > self.window_image.height:
                y = self.window_image.height - height
            if width >= self.min_region_size and height >= self.min_region_size:
                region = (x, y, width, height)
                self.regions.append(region)
                self._update_regions_list()
                self._draw_regions()  # Redraw all regions
                logger.info(f"Added region: {region}")
        elif self.active_region_idx is not None and self.drag_mode:
            self.dimension_label.place_forget()
            self._draw_regions(active_idx=self.active_region_idx, show_handles=True)
            self.active_region_idx = None
            self.drag_mode = None
            self.resize_handle = None
        def _on_canvas_motion(self, event) -> None:
            """Show cursor feedback for handles and region bodies"""
            coords = self.canvas.coords(self.canvas_image_id)
            if not coords:
                return
            img_x = event.x + self.canvas.canvasx(0) - coords[0]
            img_y = event.y + self.canvas.canvasy(0) - coords[1]
            hit = self._hit_test_regions(img_x, img_y)
            if hit:
                _, mode, handle = hit
                if mode == 'move':
                    self.canvas.config(cursor='fleur')
                elif mode == 'resize' and handle:
                    cursor_map = {
                        'nw': 'top_left_corner', 'n': 'top_side', 'ne': 'top_right_corner',
                        'e': 'right_side', 'se': 'bottom_right_corner', 's': 'bottom_side',
                        'sw': 'bottom_left_corner', 'w': 'left_side'
                    }
                    self.canvas.config(cursor=cursor_map.get(handle, 'arrow'))
                else:
                    self.canvas.config(cursor='arrow')
            else:
                self.canvas.config(cursor='arrow')

        def _hit_test_regions(self, img_x, img_y):
            """Return (region_idx, mode, handle) if mouse is over a region or handle"""
            handle_size = 8
            for idx, (x, y, w, h) in enumerate(self.regions):
                # Convert to display coordinates
                x1 = x / self.scale_x
                y1 = y / self.scale_y
                x2 = (x + w) / self.scale_x
                y2 = (y + h) / self.scale_y
                # Handles: corners and sides
                handles = {
                    'nw': (x1, y1), 'n': ((x1 + x2) / 2, y1), 'ne': (x2, y1),
                    'e': (x2, (y1 + y2) / 2), 'se': (x2, y2), 's': ((x1 + x2) / 2, y2),
                    'sw': (x1, y2), 'w': (x1, (y1 + y2) / 2)
                }
                for handle, (hx, hy) in handles.items():
                    if abs(img_x - hx) <= handle_size and abs(img_y - hy) <= handle_size:
                        return (idx, 'resize', handle)
                # Body
                if x1 + handle_size < img_x < x2 - handle_size and y1 + handle_size < img_y < y2 - handle_size:
                    return (idx, 'move', None)
            return None
    
    def _update_regions_list(self) -> None:
        """Update regions listbox"""
        self.regions_listbox.delete(0, tk.END)
        for i, (x, y, w, h) in enumerate(self.regions, 1):
            text = f"Region {i}: ({x}, {y}) {w}x{h}"
            self.regions_listbox.insert(tk.END, text)
    
    def _draw_regions(self, active_idx=None, show_handles=False) -> None:
        """Draw all regions on canvas, with handles if needed"""
        self.canvas.delete("region_rect")
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        handle_size = 8
        for i, (x, y, w, h) in enumerate(self.regions, 1):
            x1 = int(x / self.scale_x)
            y1 = int(y / self.scale_y)
            x2 = int((x + w) / self.scale_x)
            y2 = int((y + h) / self.scale_y)
            color = "yellow" if active_idx == i - 1 else "lime"
            self.canvas.create_rectangle(
                coords[0] + x1, coords[1] + y1,
                coords[0] + x2, coords[1] + y2,
                outline=color, width=2, tags="region_rect"
            )
            self.canvas.create_text(
                coords[0] + x1 + 5, coords[1] + y1 + 5,
                text=f"{i}", fill=color, font=("Arial", 12, "bold"),
                anchor="nw", tags="region_rect"
            )
            # Draw handles if active
            if show_handles and active_idx == i - 1:
                handles = [
                    (x1, y1), ((x1 + x2) // 2, y1), (x2, y1),
                    (x2, (y1 + y2) // 2), (x2, y2), ((x1 + x2) // 2, y2),
                    (x1, y2), (x1, (y1 + y2) // 2)
                ]
                for hx, hy in handles:
                    self.canvas.create_rectangle(
                        coords[0] + hx - handle_size, coords[1] + hy - handle_size,
                        coords[0] + hx + handle_size, coords[1] + hy + handle_size,
                        outline="orange", fill="orange", tags="region_rect"
                    )
    
    def _on_clear_last(self) -> None:
        """Remove last selected region"""
        if self.regions:
            self.regions.pop()
            self._update_regions_list()
            self._draw_regions()  # Redraw remaining regions
    
    def _on_done(self) -> None:
        """Close dialog and return regions"""
        self.result = self.regions
        self.dialog.destroy()
    
    def _resize_dialog_to_fit(self) -> None:
        """Resize dialog to fit image, but cap at reasonable max"""
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Max dialog size is 75% of screen
        max_width = int(screen_width * 0.75)
        max_height = int(screen_height * 0.75)
        
        # Calculate size needed for image + UI
        # Image area size (with padding for scrollbars)
        img_width = min(self.display_width + 50, max_width)  # +50 for scrollbars
        img_height = min(self.display_height + 50, max_height)
        
        # Add space for all UI elements:
        # - Instructions: ~80px
        # - Canvas frame label: ~30px
        # - Window Preview label: ~30px
        # - Selected Regions label: ~30px
        # - Regions listbox (height=4, ~100px)
        # - Buttons frame: ~40px
        # - Padding: ~40px
        ui_height = 350
        
        # Final dialog dimensions
        dialog_width = min(img_width + 20, max_width)
        dialog_height = min(img_height + ui_height, max_height)
        
        # Center the dialog
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        logger.info(f"Dialog resized to {dialog_width}x{dialog_height} for image {self.display_width}x{self.display_height}")
    
    def show(self) -> List[Tuple[int, int, int, int]]:
        """Show dialog and return selected regions
        
        Returns:
            List of regions [(x, y, width, height), ...]
        """
        self.dialog.wait_window()
        return self.result or []
