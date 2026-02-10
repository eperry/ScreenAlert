"""Tkinter-based thumbnail rendering for multiple overlay windows"""

import logging
import threading
import time
import queue
from typing import Dict, Optional, Callable, Tuple
from PIL import Image, ImageTk
import tkinter as tk

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.constants import (
    THUMBNAIL_MIN_WIDTH, THUMBNAIL_MAX_WIDTH,
    THUMBNAIL_MIN_HEIGHT, THUMBNAIL_MAX_HEIGHT
)
from screenalert_core.utils.helpers import hex_to_rgb

logger = logging.getLogger(__name__)


class ThumbnailRenderer:
    """Manages tkinter-based thumbnail overlay windows"""
    
    def __init__(self, manager_callback: Callable = None, parent_root: Optional[tk.Tk] = None):
        """Initialize thumbnail renderer
        
        Args:
            manager_callback: Function to call on user interactions
            parent_root: Parent tkinter root (optional, for integration)
        """
        self.thumbnails: Dict[str, 'ThumbnailWindow'] = {}
        self.manager_callback = manager_callback
        self.parent_root = parent_root
        self.running = False
        self.render_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        logger.info("Thumbnail renderer initialized")
    
    def add_thumbnail(self, thumbnail_id: str, config: Dict) -> bool:
        """Add a new thumbnail window
        
        Args:
            thumbnail_id: Unique thumbnail ID
            config: Thumbnail configuration dict
        
        Returns:
            True if successful
        """
        with self.lock:
            if thumbnail_id in self.thumbnails:
                logger.warning(f"Thumbnail {thumbnail_id} already exists")
                return False
            
            try:
                thumbnail = ThumbnailWindow(
                    thumbnail_id, 
                    config,
                    self.manager_callback,
                    parent_root=self.parent_root
                )
                self.thumbnails[thumbnail_id] = thumbnail
                logger.info(f"Added thumbnail: {thumbnail_id}")
                return True
            
            except Exception as e:
                logger.error(f"Error adding thumbnail {thumbnail_id}: {e}", exc_info=True)
                return False
    
    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        """Remove a thumbnail window"""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            
            try:
                self.thumbnails[thumbnail_id].cleanup()
                del self.thumbnails[thumbnail_id]
                logger.info(f"Removed thumbnail: {thumbnail_id}")
                return True
            except Exception as e:
                logger.error(f"Error removing thumbnail {thumbnail_id}: {e}", exc_info=True)
                return False
    
    def update_thumbnail_image(self, thumbnail_id: str, image: Image.Image) -> bool:
        """Update thumbnail display image"""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            
            self.thumbnails[thumbnail_id].set_image(image)
            return True
    
    def update_thumbnail_position(self, thumbnail_id: str, x: int, y: int) -> bool:
        """Update thumbnail position"""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            
            self.thumbnails[thumbnail_id].set_position(x, y)
    
    def update_thumbnail_size(self, thumbnail_id: str, width: int, height: int) -> bool:
        """Update thumbnail size"""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            
            self.thumbnails[thumbnail_id].set_size(width, height)
            return True
    
    def update_thumbnail_opacity(self, thumbnail_id: str, opacity: float) -> bool:
        """Update thumbnail opacity"""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            
            self.thumbnails[thumbnail_id].set_opacity(opacity)
            return True
    
    def get_thumbnail(self, thumbnail_id: str) -> Optional['ThumbnailWindow']:
        """Get thumbnail window object"""
        return self.thumbnails.get(thumbnail_id)
    
    def start(self) -> None:
        """Start render loop"""
        if self.running:
            return
        
        self.running = True
        self.render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self.render_thread.start()
        logger.info("Thumbnail renderer started")
    
    def stop(self) -> None:
        """Stop render loop"""
        self.running = False
        if self.render_thread:
            self.render_thread.join(timeout=2.0)
        
        # Cleanup all thumbnails
        with self.lock:
            for thumbnail in self.thumbnails.values():
                try:
                    thumbnail.cleanup()
                except:
                    pass
            self.thumbnails.clear()
        
        logger.info("Thumbnail renderer stopped")
    
    def _render_loop(self) -> None:
        """Main render loop (runs in separate thread) - can be simplified"""
        try:
            while self.running:
                # Image queue processing now happens on main thread via window.after()
                # This loop just keeps the renderer thread alive
                time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Error in render loop: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Check if renderer is running"""
        return self.running


class ThumbnailWindow:
    """Individual thumbnail overlay window using tkinter Toplevel"""
    
    def __init__(self, thumbnail_id: str, config: Dict, 
                 manager_callback: Callable = None,
                 parent_root: Optional[tk.Tk] = None):
        """Initialize thumbnail window
        
        Args:
            thumbnail_id: Unique ID
            config: Configuration dict
            manager_callback: Callback for user interactions
            parent_root: Parent tkinter root (optional)
        """
        self.thumbnail_id = thumbnail_id
        self.config = config
        self.manager_callback = manager_callback
        self.parent_root = parent_root
        
        # Position and size
        pos = config.get("position", {})
        size = config.get("size", {})
        
        self.x = pos.get("x", 100)
        self.y = pos.get("y", 100)
        self.monitor = pos.get("monitor", 0)
        self.width = size.get("width", 320)
        self.height = size.get("height", 240)
        
        # Appearance
        self.opacity = config.get("opacity", 0.8)
        self.show_border = config.get("show_border", True)
        self.enabled = config.get("enabled", True)
        
        # State
        self.current_image: Optional[Image.Image] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None
        self.is_dragging = False
        self.is_resizing = False
        self.drag_start = (0, 0)
        
        # Thread-safe queue for image updates from worker threads
        self.image_queue: queue.Queue = queue.Queue(maxsize=1)
        
        # Create tkinter window
        self._create_window()
    
    def _create_window(self) -> None:
        """Create tkinter Toplevel window"""
        try:
            # Create toplevel window (overlay) - use parent_root if available
            if self.parent_root:
                self.window = tk.Toplevel(self.parent_root)
            else:
                self.window = tk.Toplevel()
            
            # Remove window decorations (no title bar)
            self.window.overrideredirect(True)
            
            self.window.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
            self.window.attributes('-topmost', True)  # Always on top
            self.window.attributes('-alpha', self.opacity)  # Set opacity
            
            # Main container
            container = tk.Frame(self.window, bg='#FF9500' if self.show_border else 'black')
            container.pack(fill=tk.BOTH, expand=True)
            
            # Custom title bar (hidden by default)
            self.title_bar = tk.Frame(container, bg='#2e2e2e', height=25)
            self.title_label = tk.Label(self.title_bar, 
                                       text=self.config.get("window_title", "ScreenAlert")[:30],
                                       bg='#2e2e2e', fg='white', 
                                       font=('Segoe UI', 9))
            self.title_label.pack(side=tk.LEFT, padx=5)
            
            # Close button on title bar
            close_btn = tk.Label(self.title_bar, text="✕", bg='#2e2e2e', fg='white',
                                font=('Segoe UI', 10, 'bold'), cursor='hand2')
            close_btn.pack(side=tk.RIGHT, padx=5)
            close_btn.bind('<Button-1>', lambda e: self.cleanup())
            
            # Don't pack title bar initially (starts hidden)
            # Will be shown on mouse hover
            
            # Border frame
            border_frame = tk.Frame(container, bg='black', relief=tk.RAISED, 
                                   bd=2 if self.show_border else 0)
            border_frame.pack(fill=tk.BOTH, expand=True, 
                            padx=(2 if self.show_border else 0), 
                            pady=(2 if self.show_border else 0))
            
            # Image label
            self.label = tk.Label(border_frame, bg='black', image=None)
            self.label.pack(fill=tk.BOTH, expand=True)
            
            # Bind hover events to show/hide title bar
            self.window.bind('<Enter>', self._on_mouse_enter)
            self.window.bind('<Leave>', self._on_mouse_leave)
            self.label.bind('<Enter>', self._on_mouse_enter)
            self.label.bind('<Leave>', self._on_mouse_leave)
            
            # Bind drag events to title bar
            self.title_bar.bind('<Button-1>', self._on_press)
            self.title_bar.bind('<B1-Motion>', self._on_drag)
            self.title_bar.bind('<ButtonRelease-1>', self._on_release)
            self.title_label.bind('<Button-1>', self._on_press)
            self.title_label.bind('<B1-Motion>', self._on_drag)
            self.title_label.bind('<ButtonRelease-1>', self._on_release)
            
            # Bind drag events to label too (when title bar hidden)
            self.label.bind('<Button-1>', self._on_press)
            self.label.bind('<B1-Motion>', self._on_drag)
            self.label.bind('<ButtonRelease-1>', self._on_release)
            
            # Schedule periodic queue processing
            self._process_image_queue()
            
            logger.debug(f"Created window for thumbnail {self.thumbnail_id}")
        
        except Exception as e:
            logger.error(f"Error creating window: {e}", exc_info=True)
            self.window = None
    
    def _process_image_queue(self) -> None:
        """Process image updates from queue (runs on main thread)"""
        if not self.window or not self.enabled:
            if self.window:
                try:
                    self.window.after(50, self._process_image_queue)
                except:
                    pass
            return
        
        try:
            # Non-blocking check for new images
            try:
                pil_image = self.image_queue.get_nowait()
                logger.info(f"[{self.thumbnail_id}] DEQUEUE: image size {pil_image.size}")
                
                # Convert and display on main thread
                photo = ImageTk.PhotoImage(pil_image)
                logger.info(f"[{self.thumbnail_id}] PHOTOIMAGE: created {photo}")
                
                if hasattr(self, 'label') and self.label:
                    self.label.config(image=photo)
                    self.label.image = photo
                    self.photo_image = photo
                    logger.info(f"[{self.thumbnail_id}] DISPLAY_UPDATE: ✓ image displayed (label={self.label})")
                else:
                    logger.error(f"[{self.thumbnail_id}] DISPLAY_ERROR: No label to update (hasattr={hasattr(self, 'label')})")
            except queue.Empty:
                # No images in queue - this is normal
                pass
            except Exception as e:
                logger.error(f"[{self.thumbnail_id}] QUEUE_PROCESS_ERROR: {e}", exc_info=True)
            
            # Schedule next check
            if self.window:
                try:
                    self.window.after(50, self._process_image_queue)
                except:
                    # Window might be destroyed, stop processing
                    logger.debug(f"[{self.thumbnail_id}] Window closed, stopping queue processing")
        
        except Exception as e:
            logger.error(f"[{self.thumbnail_id}] PROCESS_QUEUE_ERROR: {e}", exc_info=True)
    
    def set_image(self, pil_image: Image.Image) -> None:
        """Update displayed image (thread-safe)"""
        try:
            logger.info(f"[{self.thumbnail_id}] SET_IMAGE: received image size {pil_image.size}")
            
            # Resize to fit thumbnail
            resized = ImageProcessor.resize_image(
                pil_image, self.width, self.height, 
                maintain_aspect=True
            )
            logger.info(f"[{self.thumbnail_id}] SET_IMAGE: resized to {resized.size}")
            
            # Put in queue for main thread to process
            # Drop old image if queue is full (non-blocking)
            try:
                self.image_queue.put_nowait(resized)
                qsize = self.image_queue.qsize()
                logger.info(f"[{self.thumbnail_id}] QUEUED: queue size now {qsize}")
            except queue.Full:
                # Queue full, try to remove old one and add new
                logger.debug(f"[{self.thumbnail_id}] Queue full, dropping old image")
                try:
                    self.image_queue.get_nowait()
                    self.image_queue.put_nowait(resized)
                except queue.Empty:
                    self.image_queue.put_nowait(resized)
        
        except Exception as e:
            logger.error(f"[{self.thumbnail_id}] SET_IMAGE ERROR: {e}", exc_info=True)
    
    def update_display(self) -> None:
        """Placeholder - image updates now done via queue processing"""
        pass
    
    def set_position(self, x: int, y: int) -> None:
        """Update window position"""
        self.x = x
        self.y = y
        if self.window:
            try:
                self.window.geometry(f"+{x}+{y}")
            except:
                pass
    
    def set_size(self, width: int, height: int) -> None:
        """Update window size"""
        width = max(THUMBNAIL_MIN_WIDTH, min(width, THUMBNAIL_MAX_WIDTH))
        height = max(THUMBNAIL_MIN_HEIGHT, min(height, THUMBNAIL_MAX_HEIGHT))
        
        if width == self.width and height == self.height:
            return
        
        self.width = width
        self.height = height
        
        try:
            if self.window:
                self.window.geometry(f"{width}x{height}")
                # Force resize of current image
                if self.current_image:
                    self.set_image(self.current_image)
        except Exception as e:
            logger.error(f"Error resizing window: {e}", exc_info=True)
    
    def set_opacity(self, opacity: float) -> None:
        """Update window opacity"""
        self.opacity = max(0.2, min(opacity, 1.0))
        if self.window:
            try:
                self.window.attributes('-alpha', self.opacity)
            except:
                pass
    
    def _on_mouse_enter(self, event) -> None:
        """Show title bar when mouse enters"""
        if hasattr(self, 'title_bar') and self.title_bar:
            try:
                self.title_bar.pack(side=tk.TOP, fill=tk.X, before=self.label.master)
            except:
                pass
    
    def _on_mouse_leave(self, event) -> None:
        """Hide title bar when mouse leaves"""
        # Check if mouse really left the window (not just moved between child widgets)
        if hasattr(self, 'title_bar') and self.title_bar and self.window:
            try:
                x, y = self.window.winfo_pointerxy()
                widget = self.window.winfo_containing(x, y)
                # If pointer is not over any part of this window, hide title bar
                if widget is None or widget.winfo_toplevel() != self.window:
                    self.title_bar.pack_forget()
            except:
                pass
    
    def _on_press(self, event) -> None:
        """Start drag operation"""
        self.is_dragging = True
        self.drag_start = (event.x_root, event.y_root)
    
    def _on_drag(self, event) -> None:
        """Handle dragging"""
        if not self.is_dragging or not self.window:
            return
        
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        
        new_x = self.x + dx
        new_y = self.y + dy
        
        self.set_position(new_x, new_y)
        self.drag_start = (event.x_root, event.y_root)
    
    def _on_release(self, event) -> None:
        """End drag operation"""
        self.is_dragging = False
    
    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.window:
                self.window.destroy()
        except:
            pass
