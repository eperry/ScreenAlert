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
        self._active_thumbnail_id: Optional[str] = None
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
                    owner_renderer=self,
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
                if self._active_thumbnail_id == thumbnail_id:
                    self._active_thumbnail_id = None
                    if self.thumbnails:
                        self._active_thumbnail_id = next(iter(self.thumbnails.keys()))
                logger.info(f"Removed thumbnail: {thumbnail_id}")
                return True
            except Exception as e:
                logger.error(f"Error removing thumbnail {thumbnail_id}: {e}", exc_info=True)
                return False

    def set_active_thumbnail(self, thumbnail_id: str, bring_to_front: bool = True) -> None:
        """Mark one overlay as active/top and update border visibility for all overlays."""
        thumbnails_snapshot = {}
        active_thumbnail = None
        previous_active_id: Optional[str] = None
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return

            previous_active_id = self._active_thumbnail_id
            if previous_active_id == thumbnail_id and not bring_to_front:
                return

            self._active_thumbnail_id = thumbnail_id
            active_thumbnail = self.thumbnails.get(thumbnail_id)
            thumbnails_snapshot = dict(self.thumbnails)

        if bring_to_front and active_thumbnail:
            active_thumbnail.lift_threadsafe()

        if previous_active_id == thumbnail_id:
            return

        for current_id, thumbnail in thumbnails_snapshot.items():
            thumbnail.set_active_border_threadsafe(current_id == thumbnail_id)

    def clear_active_thumbnail(self) -> None:
        """Clear active overlay border state for all overlays."""
        thumbnails_snapshot = {}
        with self.lock:
            if self._active_thumbnail_id is None:
                return
            self._active_thumbnail_id = None
            thumbnails_snapshot = dict(self.thumbnails)

        for thumbnail in thumbnails_snapshot.values():
            thumbnail.set_active_border_threadsafe(False)

    def refresh_thumbnail_titles(self) -> None:
        """Refresh title-bar labels for all active thumbnails."""
        with self.lock:
            thumbnails_snapshot = list(self.thumbnails.values())
        for thumbnail in thumbnails_snapshot:
            thumbnail.refresh_title_threadsafe()
    
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
            return True
    
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

    def set_all_thumbnail_opacity(self, opacity: float) -> None:
        """Apply opacity to all active thumbnail windows."""
        with self.lock:
            for thumbnail in self.thumbnails.values():
                thumbnail.set_opacity(opacity)

    def set_all_thumbnail_topmost(self, on_top: bool) -> None:
        """Apply topmost flag to all active thumbnail windows."""
        with self.lock:
            for thumbnail in self.thumbnails.values():
                thumbnail.set_topmost(on_top)

    def set_all_thumbnail_borders(self, show_borders: bool) -> None:
        """Apply border visibility to all active thumbnail windows."""
        with self.lock:
            for thumbnail in self.thumbnails.values():
                thumbnail.set_show_border(show_borders)

    def refresh_unavailable_thumbnails(self, show_when_unavailable: bool) -> None:
        """Refresh visibility for currently unavailable thumbnails."""
        with self.lock:
            for thumbnail in self.thumbnails.values():
                if not thumbnail._is_available:
                    thumbnail.set_availability(False, show_when_unavailable)
    
    def get_thumbnail(self, thumbnail_id: str) -> Optional['ThumbnailWindow']:
        """Get thumbnail window object"""
        return self.thumbnails.get(thumbnail_id)

    def get_all_thumbnail_geometries(self) -> Dict[str, Dict[str, int]]:
        """Get current geometry snapshot for all thumbnails."""
        with self.lock:
            return {
                thumbnail_id: {
                    "x": thumbnail.x,
                    "y": thumbnail.y,
                    "width": thumbnail.width,
                    "height": thumbnail.height,
                }
                for thumbnail_id, thumbnail in self.thumbnails.items()
            }

    def set_thumbnail_availability(self, thumbnail_id: str, available: bool,
                                   show_when_unavailable: bool = False) -> bool:
        """Set thumbnail availability state for unavailable-window handling."""
        with self.lock:
            if thumbnail_id not in self.thumbnails:
                return False
            self.thumbnails[thumbnail_id].set_availability(
                available=available,
                show_when_unavailable=show_when_unavailable,
            )
            return True
    
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
                 owner_renderer: Optional[ThumbnailRenderer] = None,
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
        self.owner_renderer = owner_renderer
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
        self.always_on_top = bool(config.get("always_on_top", True))
        self.show_border = config.get("show_border", True)
        self.enabled = config.get("enabled", True)
        self._is_active_window = False
        
        # State
        self.current_image: Optional[Image.Image] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None
        self._is_available = True
        self._show_when_unavailable = False
        self.interaction_state = "idle"
        self.left_pressed = False
        self.right_pressed = False
        self.pointer_start = (0, 0)
        self.start_geometry = {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
        self._sync_start_sizes: Dict[str, Tuple[int, int]] = {}
        self._drag_threshold_px = 4
        self._did_move_or_resize = False
        
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
            self.window.attributes('-topmost', self.always_on_top)
            self.window.attributes('-alpha', self.opacity)  # Set opacity
            
            # Main container
            self.container = tk.Frame(self.window, bg='black')
            self.container.pack(fill=tk.BOTH, expand=True)
            
            # Custom title bar (hidden by default); placed as overlay so it never affects geometry
            self.title_bar = tk.Frame(self.container, bg='#2e2e2e', height=25)
            self.title_label = tk.Label(self.title_bar, 
                                       text=self._build_overlay_title(),
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
            self.border_frame = tk.Frame(self.container, bg='black', relief=tk.FLAT, bd=0)
            self.border_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
            # Image label
            self.label = tk.Label(self.border_frame, bg='black', image=None)
            self.label.pack(fill=tk.BOTH, expand=True)

            # Border appears only when this overlay window is active
            self._set_active_border(False)
            
            # Bind hover events to show/hide title bar
            self.window.bind('<Enter>', self._on_mouse_enter)
            self.window.bind('<Leave>', self._on_mouse_leave)
            self.window.bind('<FocusIn>', self._on_focus_in)
            self.label.bind('<Enter>', self._on_mouse_enter)
            self.label.bind('<Leave>', self._on_mouse_leave)
            
            # Bind drag events to title bar
            self.title_bar.bind('<ButtonPress-1>', self._on_left_press)
            self.title_bar.bind('<ButtonRelease-1>', self._on_left_release)
            self.title_bar.bind('<ButtonPress-3>', self._on_right_press)
            self.title_bar.bind('<ButtonRelease-3>', self._on_right_release)
            self.title_bar.bind('<B1-Motion>', self._on_motion)
            self.title_bar.bind('<B3-Motion>', self._on_motion)
            self.title_label.bind('<ButtonPress-1>', self._on_left_press)
            self.title_label.bind('<ButtonRelease-1>', self._on_left_release)
            self.title_label.bind('<ButtonPress-3>', self._on_right_press)
            self.title_label.bind('<ButtonRelease-3>', self._on_right_release)
            self.title_label.bind('<B1-Motion>', self._on_motion)
            self.title_label.bind('<B3-Motion>', self._on_motion)
            
            # Bind drag events to label too (when title bar hidden)
            self.label.bind('<ButtonPress-1>', self._on_left_press)
            self.label.bind('<ButtonRelease-1>', self._on_left_release)
            self.label.bind('<ButtonPress-3>', self._on_right_press)
            self.label.bind('<ButtonRelease-3>', self._on_right_release)
            self.label.bind('<B1-Motion>', self._on_motion)
            self.label.bind('<B3-Motion>', self._on_motion)

            # Window-level fallback bindings to keep gestures reliable across child boundaries
            self.window.bind('<ButtonPress-1>', self._on_left_press)
            self.window.bind('<ButtonRelease-1>', self._on_left_release)
            self.window.bind('<ButtonPress-3>', self._on_right_press)
            self.window.bind('<ButtonRelease-3>', self._on_right_release)
            self.window.bind('<B1-Motion>', self._on_motion)
            self.window.bind('<B3-Motion>', self._on_motion)
            
            # Schedule periodic queue processing (use after to ensure window is fully initialized)
            self.window.after(50, self._process_image_queue)
            
            logger.debug(f"Created window for thumbnail {self.thumbnail_id}")
        
        except Exception as e:
            logger.error(f"Error creating window: {e}", exc_info=True)
            self.window = None

    def _build_overlay_title(self) -> str:
        """Build title bar text including slot number when assigned."""
        title = str(self.config.get("window_title", "ScreenAlert") or "ScreenAlert").strip()
        slot_value = self.config.get("window_slot")
        try:
            slot_num = int(slot_value)
        except (TypeError, ValueError):
            slot_num = None

        prefix = f"[{slot_num}] " if slot_num is not None and 1 <= slot_num <= 10 else ""
        return f"{prefix}{title}"[:48]

    def refresh_title_threadsafe(self) -> None:
        """Refresh title-bar text on Tk thread."""
        if not self.window:
            return

        def _apply() -> None:
            if hasattr(self, 'title_label') and self.title_label:
                self.title_label.config(text=self._build_overlay_title())

        try:
            self.window.after(0, _apply)
        except Exception:
            pass

    def _set_active_border(self, is_active: bool) -> None:
        """Show border only while this overlay window is active."""
        self._is_active_window = bool(is_active)
        if not self.show_border:
            return
        if not hasattr(self, 'container') or not hasattr(self, 'border_frame'):
            return
        try:
            border_px = 2 if self._is_active_window else 0
            self.container.configure(bg='#FF9500' if self._is_active_window else 'black')
            self.border_frame.configure(
                relief=tk.RAISED if self._is_active_window else tk.FLAT,
                bd=border_px,
            )
            self.border_frame.pack_configure(padx=border_px, pady=border_px)
        except Exception:
            pass

    def set_active_border_threadsafe(self, is_active: bool) -> None:
        """Set active border state on Tk thread regardless of caller thread."""
        if self._is_active_window == bool(is_active):
            return
        if not self.window:
            return
        try:
            self.window.after(0, lambda: self._set_active_border(is_active))
        except Exception:
            pass

    def lift_threadsafe(self) -> None:
        """Lift overlay on Tk thread regardless of caller thread."""
        if not self.window:
            return
        try:
            self.window.after(0, self.window.lift)
        except Exception:
            pass

    def _on_focus_in(self, _event) -> None:
        pass
    
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
                    logger.info(f"[{self.thumbnail_id}] DISPLAY_UPDATE: image displayed (label={self.label})")
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
            self.current_image = pil_image
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

    def set_availability(self, available: bool, show_when_unavailable: bool = False) -> None:
        """Set availability state and update overlay presentation."""
        self._is_available = bool(available)
        self._show_when_unavailable = bool(show_when_unavailable)
        self._apply_availability_state()

    def _clear_image_queue(self) -> None:
        """Clear pending image queue to prevent stale frames."""
        while True:
            try:
                self.image_queue.get_nowait()
            except queue.Empty:
                break

    def _apply_availability_state(self) -> None:
        """Apply unavailable/available visual state to overlay window."""
        if not self.window or not hasattr(self, 'label') or not self.label:
            return
        try:
            window_state = ""
            try:
                window_state = self.window.state()
            except Exception:
                window_state = ""

            if self._is_available:
                if window_state == 'withdrawn':
                    self.window.deiconify()
                self.label.config(bg='black', fg='white', text='')
                if self.photo_image is not None:
                    self.label.config(image=self.photo_image)
                    self.label.image = self.photo_image
            else:
                self._clear_image_queue()
                if self._show_when_unavailable:
                    if window_state == 'withdrawn':
                        self.window.deiconify()
                    self.photo_image = None
                    self.label.image = None
                    self.label.config(
                        image='',
                        text='Not Available',
                        fg='white',
                        bg='#0078D7',
                        compound='center',
                    )
                else:
                    self.window.withdraw()
        except Exception as error:
            logger.debug(f"[{self.thumbnail_id}] availability state apply failed: {error}")
    
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

    def set_topmost(self, on_top: bool) -> None:
        """Update always-on-top flag for this thumbnail window."""
        self.always_on_top = bool(on_top)
        if self.window:
            try:
                self.window.attributes('-topmost', self.always_on_top)
            except:
                pass

    def set_show_border(self, enabled: bool) -> None:
        """Update border visibility for this thumbnail window."""
        self.show_border = bool(enabled)
        if not self.window:
            return

        def _apply() -> None:
            if not self.show_border:
                try:
                    if hasattr(self, 'container'):
                        self.container.configure(bg='black')
                    if hasattr(self, 'border_frame'):
                        self.border_frame.configure(relief=tk.FLAT, bd=0)
                        self.border_frame.pack_configure(padx=0, pady=0)
                except Exception:
                    pass
                return
            self._set_active_border(self._is_active_window)

        try:
            self.window.after(0, _apply)
        except Exception:
            pass
    
    def _on_mouse_enter(self, event) -> None:
        """Show title bar when mouse enters"""
        if hasattr(self, 'title_bar') and self.title_bar:
            try:
                self.title_bar.place(x=0, y=0, relwidth=1.0, height=25)
                self.title_bar.lift()
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
                    self.title_bar.place_forget()
            except:
                pass
    
    @staticmethod
    def _is_shift_pressed(event) -> bool:
        return bool(getattr(event, 'state', 0) & 0x0001)

    def _is_within_threshold(self, event) -> bool:
        dx = abs(event.x_root - self.pointer_start[0])
        dy = abs(event.y_root - self.pointer_start[1])
        return dx <= self._drag_threshold_px and dy <= self._drag_threshold_px

    def _begin_interaction(self, event) -> None:
        self.pointer_start = (event.x_root, event.y_root)
        self.start_geometry = {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    def _begin_move(self, event) -> None:
        self.interaction_state = "moving"
        self._did_move_or_resize = False
        self._begin_interaction(event)

    def _begin_resize(self, event, sync: bool) -> None:
        self.interaction_state = "sync_resizing" if sync else "resizing"
        self._did_move_or_resize = False
        self._begin_interaction(event)
        self._sync_start_sizes = {}
        if sync and self.owner_renderer:
            source_width = self.start_geometry["width"]
            source_height = self.start_geometry["height"]
            geometries = self.owner_renderer.get_all_thumbnail_geometries()
            self._sync_start_sizes = {
                thumbnail_id: (source_width, source_height)
                for thumbnail_id, geometry in geometries.items()
            }
            for thumbnail in self.owner_renderer.thumbnails.values():
                thumbnail.set_size(source_width, source_height)

    def _apply_move(self, event) -> None:
        if self.interaction_state != "moving":
            return
        dx = event.x_root - self.pointer_start[0]
        dy = event.y_root - self.pointer_start[1]
        new_x = self.start_geometry["x"] + dx
        new_y = self.start_geometry["y"] + dy
        self.set_position(new_x, new_y)
        self._did_move_or_resize = True

    def _apply_resize(self, event) -> None:
        if self.interaction_state not in ("resizing", "sync_resizing"):
            return

        dx = event.x_root - self.pointer_start[0]
        dy = event.y_root - self.pointer_start[1]
        self._did_move_or_resize = True

        if self.interaction_state == "sync_resizing" and self.owner_renderer:
            for thumbnail_id, thumbnail in self.owner_renderer.thumbnails.items():
                start_size = self._sync_start_sizes.get(thumbnail_id, (thumbnail.width, thumbnail.height))
                start_width, start_height = start_size
                target_width = max(THUMBNAIL_MIN_WIDTH, min(start_width + dx, THUMBNAIL_MAX_WIDTH))
                target_height = max(THUMBNAIL_MIN_HEIGHT, min(start_height + dy, THUMBNAIL_MAX_HEIGHT))
                thumbnail.set_size(target_width, target_height)
            return

        target_width = max(THUMBNAIL_MIN_WIDTH, min(self.start_geometry["width"] + dx, THUMBNAIL_MAX_WIDTH))
        target_height = max(THUMBNAIL_MIN_HEIGHT, min(self.start_geometry["height"] + dy, THUMBNAIL_MAX_HEIGHT))
        self.set_size(target_width, target_height)

    def _emit_interaction(self, action: str, payload: Optional[Dict] = None) -> None:
        if not self.manager_callback:
            return
        try:
            self.manager_callback(self.thumbnail_id, action, payload or {})
        except TypeError:
            self.manager_callback(self.thumbnail_id, action)
        except Exception as error:
            logger.debug(f"[{self.thumbnail_id}] interaction callback failed: {error}")

    def _on_left_press(self, event) -> None:
        self.left_pressed = True
        if self.right_pressed:
            self._begin_resize(event, sync=self._is_shift_pressed(event))
        else:
            self._begin_interaction(event)
            self.interaction_state = "pending_focus"
            self._did_move_or_resize = False

    def _on_right_press(self, event) -> None:
        self.right_pressed = True
        if self.left_pressed:
            self._begin_resize(event, sync=self._is_shift_pressed(event))
        else:
            self._begin_move(event)

    def _on_motion(self, event) -> None:
        if self.left_pressed and self.right_pressed and self.interaction_state not in ("resizing", "sync_resizing"):
            self._begin_resize(event, sync=self._is_shift_pressed(event))

        if self.interaction_state == "pending_focus" and not self._is_within_threshold(event):
            self._did_move_or_resize = True

        if self.interaction_state == "moving":
            self._apply_move(event)
        elif self.interaction_state in ("resizing", "sync_resizing"):
            self._apply_resize(event)

    def _on_left_release(self, event) -> None:
        self.left_pressed = False
        self._finalize_interaction(event, released_button='left')

    def _on_right_release(self, event) -> None:
        self.right_pressed = False
        self._finalize_interaction(event, released_button='right')

    def _finalize_interaction(self, event, released_button: str) -> None:
        state = self.interaction_state

        if state == "pending_focus":
            if released_button == 'left' and not self.right_pressed and not self._did_move_or_resize:
                if self._is_available:
                    self._emit_interaction("activated", {})
            self.interaction_state = "idle"
            return

        if state == "moving" and released_button == 'right':
            self._emit_interaction(
                "position_changed",
                {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
            )
            self.interaction_state = "idle"
            return

        if state == "resizing":
            if not self.left_pressed and not self.right_pressed:
                self._emit_interaction(
                    "size_changed",
                    {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
                )
                self.interaction_state = "idle"
            return

        if state == "sync_resizing":
            if not self.left_pressed and not self.right_pressed:
                geometries = {}
                if self.owner_renderer:
                    geometries = self.owner_renderer.get_all_thumbnail_geometries()
                self._emit_interaction("bulk_geometry_changed", {"geometries": geometries})
                self.interaction_state = "idle"
            return
    
    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.window:
                self.window.destroy()
        except:
            pass
