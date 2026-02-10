"""Thumbnail card widget for displaying thumbnail with status"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import logging
from typing import Optional, Callable

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
        self.status = 'ok'  # ok, warning, alert
        self.photo = None
        self.on_click: Optional[Callable[[str], None]] = None
        
        # Main frame with status border
        self.frame = tk.Frame(parent, bg='black', bd=3, highlightthickness=2)
        self.frame.config(highlightbackground=self.STATUS_COLORS['ok'])
        
        # Image label (120x80)
        self.image_label = tk.Label(self.frame, bg='black', width=15, height=5)
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
        
        # Region count
        self.region_label = tk.Label(
            info_frame, text=f"{region_count} regions",
            bg='#333333', fg='#aaaaaa', font=('Segoe UI', 8)
        )
        self.region_label.pack(fill=tk.X)
        
        # Status label
        self.status_label = tk.Label(
            info_frame, text="OK",
            bg='#2ecc71', fg='white', font=('Segoe UI', 8, 'bold')
        )
        self.status_label.pack(fill=tk.X, pady=(3, 0))
        
        # Bind click
        self.frame.bind("<Button-1>", self._on_click)
        self.image_label.bind("<Button-1>", self._on_click)
        self.title_label.bind("<Button-1>", self._on_click)
        self.region_label.bind("<Button-1>", self._on_click)
        self.status_label.bind("<Button-1>", self._on_click)
    
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
                # Resize to fit (120x80)
                img = pil_image.copy()
                img.thumbnail((120, 80), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.photo)
            except Exception as e:
                logger.error(f"Error setting image: {e}")
        else:
            self.image_label.config(image='')
            self.photo = None
    
    def set_status(self, status: str) -> None:
        """Set status indicator
        
        Args:
            status: 'ok', 'warning', or 'alert'
        """
        if status not in self.STATUS_COLORS:
            status = 'ok'
        
        self.status = status
        color = self.STATUS_COLORS[status]
        text = status.upper()
        
        self.status_label.config(bg=color, text=text)
        self.frame.config(highlightbackground=color)
    
    def set_region_count(self, count: int) -> None:
        """Update region count"""
        self.region_count = count
        self.region_label.config(text=f"{count} regions")
    
    def _on_click(self, event) -> None:
        """Handle click"""
        if self.on_click:
            self.on_click(self.thumbnail_id)
    
    def get_frame(self) -> tk.Frame:
        """Get the main frame"""
        return self.frame
