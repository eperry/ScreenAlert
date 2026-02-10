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
        
        # Calculate region in original coordinates
        end_x = int(img_x * self.scale_x)
        end_y = int(img_y * self.scale_y)
        
        x = min(self.start_x, end_x)
        y = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        
        # Snap to minimum size if we're close
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
        
        # Convert back to display coordinates
        start_display_x = int(self.start_x / self.scale_x)
        start_display_y = int(self.start_y / self.scale_y)
        end_display_x = int(end_x / self.scale_x)
        end_display_y = int(end_y / self.scale_y)
        
        x1 = min(start_display_x, end_display_x)
        y1 = min(start_display_y, end_display_y)
        x2 = max(start_display_x, end_display_x)
        y2 = max(start_display_y, end_display_y)
        
        # Draw preview rectangle
        self.canvas.delete("region_preview")
        self.canvas.create_rectangle(
            coords[0] + x1, coords[1] + y1,
            coords[0] + x2, coords[1] + y2,
            outline="lime", width=2, tags="region_preview"
        )
        
        # Show dimensions near cursor
        dim_text = f"{width}x{height}px"
        self.dimension_label.config(text=dim_text)
        
        # Position label near cursor (offset so it's visible)
        label_x = event.x + 15
        label_y = event.y - 25
        self.dimension_label.place(x=label_x, y=label_y)
    
    def _on_canvas_release(self, event) -> None:
        """Handle mouse release on canvas"""
        if not self.is_selecting:
            return
        
        self.is_selecting = False
        self.canvas.delete("region_preview")
        self.dimension_label.place_forget()  # Hide dimension label
        
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
        
        # Enforce minimum size with snapping
        if width < self.min_region_size:
            width = self.min_region_size
        if height < self.min_region_size:
            height = self.min_region_size
        
        # Ensure region doesn't exceed image bounds
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
    
    def _update_regions_list(self) -> None:
        """Update regions listbox"""
        self.regions_listbox.delete(0, tk.END)
        for i, (x, y, w, h) in enumerate(self.regions, 1):
            text = f"Region {i}: ({x}, {y}) {w}x{h}"
            self.regions_listbox.insert(tk.END, text)
    
    def _draw_regions(self) -> None:
        """Draw all regions on canvas"""
        # Remove old region drawings
        self.canvas.delete("region_rect")
        
        coords = self.canvas.coords(self.canvas_image_id)
        if not coords:
            return
        
        # Draw each region
        for i, (x, y, w, h) in enumerate(self.regions, 1):
            # Convert to display coordinates
            x1 = int(x / self.scale_x)
            y1 = int(y / self.scale_y)
            x2 = int((x + w) / self.scale_x)
            y2 = int((y + h) / self.scale_y)
            
            self.canvas.create_rectangle(
                coords[0] + x1, coords[1] + y1,
                coords[0] + x2, coords[1] + y2,
                outline="lime", width=2, tags="region_rect"
            )
            
            # Add region number label
            self.canvas.create_text(
                coords[0] + x1 + 5, coords[1] + y1 + 5,
                text=f"{i}", fill="lime", font=("Arial", 12, "bold"),
                anchor="nw", tags="region_rect"
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
