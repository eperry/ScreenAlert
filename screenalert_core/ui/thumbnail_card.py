"""Thumbnail card widget for displaying thumbnail with status"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import logging
from typing import Optional, Callable, List, Dict

logger = logging.getLogger(__name__)


class ThumbnailCard:
    """Card widget showing thumbnail preview with status"""
    
    # Status colors
    STATUS_COLORS = {
        'ok': '#2ecc71',      # Green
        'warning': '#f39c12',  # Orange/Yellow
        'alert': '#e74c3c',    # Red
    }
    
    def __init__(self, parent: tk.Widget, thumbnail_id: str, title: str, region_count: int = 0):
        """Initialize thumbnail card
        
        Args:
            parent: Parent widget
            thumbnail_id: ID of the thumbnail
            title: Window title
            region_count: Number of regions
        """
        self.thumbnail_id = thumbnail_id
        self.title = title
        self.region_count = region_count
        self.overall_status = 'ok'  # ok, warning, alert
        self.region_statuses: Dict[int, str] = {}  # region_index -> status
        self.photo = None
        self.on_click: Optional[Callable[[str], None]] = None
        
        # Main frame with status border
        self.frame = tk.Frame(parent, bg='black', bd=3, highlightthickness=2)
        self.frame.config(highlightbackground=self.STATUS_COLORS['ok'])
        
        # Image label (120x80) - use fixed size for consistency
        self.image_label = tk.Label(self.frame, bg='#1a1a1a', width=20, height=4, 
                                    relief=tk.SUNKEN, bd=1)
        self.image_label.pack(padx=5, pady=5)
        
        # Info frame (below image)
        info_frame = tk.Frame(self.frame, bg='#333333')
        info_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Title (word-wrapped, max 2 lines)
        self.title_label = tk.Label(
            info_frame, text=self._wrap_text(title, 18),
            bg='#333333', fg='white', font=('Segoe UI', 9),
            wraplength=120, justify=tk.CENTER
        )
        self.title_label.pack(fill=tk.X, pady=(3, 0))
        
        # Region count and info
        region_info = f"{region_count} region{'s' if region_count != 1 else ''}"
        self.region_label = tk.Label(
            info_frame, text=region_info,
            bg='#333333', fg='#aaaaaa', font=('Segoe UI', 8)
        )
        self.region_label.pack(fill=tk.X)
        
        # Region status indicators (colored dots for each region)
        self.region_indicators_frame = tk.Frame(info_frame, bg='#333333')
        self.region_indicators_frame.pack(fill=tk.X, pady=(2, 0))
        self.region_status_labels: List[tk.Label] = []
        self._create_region_indicators(region_count)
        
        # Overall status label (smaller)
        self.status_label = tk.Label(
            info_frame, text="OK",
            bg='#2ecc71', fg='white', font=('Segoe UI', 7, 'bold')
        )
        self.status_label.pack(fill=tk.X, pady=(3, 0))
        
        # Bind click
        self.frame.bind("<Button-1>", self._on_click)
        self.image_label.bind("<Button-1>", self._on_click)
        self.title_label.bind("<Button-1>", self._on_click)
        self.region_label.bind("<Button-1>", self._on_click)
        self.status_label.bind("<Button-1>", self._on_click)
    
    def _create_region_indicators(self, count: int) -> None:
        """Create status indicator dots for each region"""
        # Clear existing indicators
        for label in self.region_status_labels:
            label.destroy()
        self.region_status_labels.clear()
        self.region_statuses.clear()
        
        # Create a dot for each region
        for i in range(count):
            indicator = tk.Label(
                self.region_indicators_frame,
                text="●",
                fg=self.STATUS_COLORS['ok'],
                bg='#333333',
                font=('Segoe UI', 8)
            )
            indicator.pack(side=tk.LEFT, padx=2)
            self.region_status_labels.append(indicator)
            self.region_statuses[i] = 'ok'
    
    def _wrap_text(self, text: str, max_len: int) -> str:
        """Wrap text to fit in card"""
        if len(text) <= max_len:
            return text
        # Find a good break point
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_len:
                current += word + " "
            else:
                if current:
                    lines.append(current.strip())
                current = word + " "
        if current:
            lines.append(current.strip())
        return "\n".join(lines[:2])  # Max 2 lines
    
    def set_image(self, pil_image: Optional[Image.Image]) -> None:
        """Set the thumbnail image
        
        Args:
            pil_image: PIL Image object or None
        """
        if pil_image:
            try:
                # Resize to fit label size (keeps aspect ratio, pads with black)
                img = pil_image.copy()
                # Label is roughly 160x80 pixels at 96 DPI
                img.thumbnail((160, 80), Image.Resampling.LANCZOS)
                
                # Keep reference to prevent garbage collection
                self.photo = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.photo)
                logger.debug(f"Image set for card {self.thumbnail_id}")
            except Exception as e:
                logger.error(f"Error setting image for {self.thumbnail_id}: {e}", exc_info=True)
        else:
            self.image_label.config(image='')
            self.photo = None
    
    def set_status(self, status: str, region_index: int = -1) -> None:
        """Set status indicator
        
        Args:
            status: 'ok', 'warning', or 'alert'
            region_index: If >= 0, set status for specific region; else set overall status
        """
        if status not in self.STATUS_COLORS:
            status = 'ok'
        
        if region_index >= 0:
            # Set status for specific region
            if region_index < len(self.region_status_labels):
                self.region_statuses[region_index] = status
                color = self.STATUS_COLORS[status]
                self.region_status_labels[region_index].config(fg=color)
                logger.debug(f"Region {region_index} status set to {status}")
            
            # Update overall status based on worst region status
            self._update_overall_status()
        else:
            # Set overall status
            self.overall_status = status
            self._update_overall_status()
    
    def _update_overall_status(self) -> None:
        """Update overall status based on region statuses"""
        # Find worst status across all regions
        if self.region_statuses:
            statuses = list(self.region_statuses.values())
            if 'alert' in statuses:
                self.overall_status = 'alert'
            elif 'warning' in statuses:
                self.overall_status = 'warning'
            else:
                self.overall_status = 'ok'
        else:
            # No regions, use explicit overall status
            pass
        
        # Update UI
        color = self.STATUS_COLORS[self.overall_status]
        text = self.overall_status.upper()
        self.status_label.config(bg=color, text=text)
        self.frame.config(highlightbackground=color)
    
    def set_region_count(self, count: int) -> None:
        """Update region count"""
        self.region_count = count
        region_info = f"{count} region{'s' if count != 1 else ''}"
        self.region_label.config(text=region_info)
        self._create_region_indicators(count)
    
    
    def _on_click(self, event) -> None:
        """Handle click"""
        if self.on_click:
            self.on_click(self.thumbnail_id)
    
    def get_frame(self) -> tk.Frame:
        """Get the main frame"""
        return self.frame
