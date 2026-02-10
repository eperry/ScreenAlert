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
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Monitoring Regions")
        self.result = None
        
        self._build_ui()
        self._load_image()
    
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
        
        # Regions list
        list_frame = ttk.LabelFrame(main_frame, text="Selected Regions", padding=5)
        list_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.regions_listbox = tk.Listbox(list_frame, height=4, font=("Courier", 9))
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
            # Resize if too large
            max_width = 1000
            max_height = 700
            img = self.window_image
            
            if img.width > max_width or img.height > max_height:
                img = ImageProcessor.resize_image(img, max_width, max_height)
            
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
            
            logger.info(f"Loaded image: {img.width}x{img.height}")
        
        except Exception as e:
            logger.error(f"Error loading image: {e}")
    
    def _on_canvas_press(self, event) -> None:
        """Handle mouse press on canvas"""
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        
        img_x = event.x + self.canvas.canvasx(0) - coords[0]
        img_y = event.y + self.canvas.canvasy(0) - coords[1]
        
        if img_x < 0 or img_y < 0 or img_x > self.display_width or img_y > self.display_height:
            return
        
        self.is_selecting = True
        self.start_x = int(img_x * self.scale_x)
        self.start_y = int(img_y * self.scale_y)
    
    def _on_canvas_drag(self, event) -> None:
        """Handle mouse drag on canvas"""
        if not self.is_selecting:
            return
        
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        
        img_x = event.x + self.canvas.canvasx(0) - coords[0]
        img_y = event.y + self.canvas.canvasy(0) - coords[1]
        
        # Clamp to image bounds
        img_x = max(0, min(img_x, self.display_width))
        img_y = max(0, min(img_y, self.display_height))
        
        # Draw preview rectangle
        self.canvas.delete("region_preview")
        
        start_display_x = int(self.start_x / self.scale_x)
        start_display_y = int(self.start_y / self.scale_y)
        
        x1 = min(start_display_x, int(img_x))
        y1 = min(start_display_y, int(img_y))
        x2 = max(start_display_x, int(img_x))
        y2 = max(start_display_y, int(img_y))
        
        coords = self.canvas.coords(self.canvas_image_id)
        self.canvas.create_rectangle(
            coords[0] + x1, coords[1] + y1,
            coords[0] + x2, coords[1] + y2,
            outline="lime", width=2, tags="region_preview"
        )
    
    def _on_canvas_release(self, event) -> None:
        """Handle mouse release on canvas"""
        if not self.is_selecting:
            return
        
        self.is_selecting = False
        self.canvas.delete("region_preview")
        
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        
        img_x = event.x + self.canvas.canvasx(0) - coords[0]
        img_y = event.y + self.canvas.canvasy(0) - coords[1]
        
        # Clamp to image bounds
        img_x = max(0, min(img_x, self.display_width))
        img_y = max(0, min(img_y, self.display_height))
        
        # Convert to original image coordinates
        end_x = int(img_x * self.scale_x)
        end_y = int(img_y * self.scale_y)
        
        # Create region (x, y, width, height)
        x = min(self.start_x, end_x)
        y = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        
        if width > 50 and height > 50:  # Minimum region size
            region = (x, y, width, height)
            self.regions.append(region)
            self._update_regions_list()
            logger.info(f"Added region: {region}")
        else:
            logger.warning("Region too small (minimum 50x50)")
    
    def _update_regions_list(self) -> None:
        """Update regions listbox"""
        self.regions_listbox.delete(0, tk.END)
        for i, (x, y, w, h) in enumerate(self.regions, 1):
            text = f"Region {i}: ({x}, {y}) {w}x{h}"
            self.regions_listbox.insert(tk.END, text)
    
    def _on_clear_last(self) -> None:
        """Remove last selected region"""
        if self.regions:
            self.regions.pop()
            self._update_regions_list()
    
    def _on_done(self) -> None:
        """Close dialog and return regions"""
        self.result = self.regions
        self.dialog.destroy()
    
    def show(self) -> List[Tuple[int, int, int, int]]:
        """Show dialog and return selected regions
        
        Returns:
            List of regions [(x, y, width, height), ...]
        """
        self.dialog.wait_window()
        return self.result or []
