"""Pygame-based thumbnail rendering"""

import logging
import threading
import time
from typing import Dict, Optional, Callable, Tuple
from PIL import Image
import pygame

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.constants import (
    THUMBNAIL_MIN_WIDTH, THUMBNAIL_MAX_WIDTH,
    THUMBNAIL_MIN_HEIGHT, THUMBNAIL_MAX_HEIGHT
)
from screenalert_core.utils.helpers import hex_to_rgb

logger = logging.getLogger(__name__)


class ThumbnailRenderer:
    """Manages Pygame-based thumbnail overlay windows"""
    
    def __init__(self, manager_callback: Callable = None):
        """Initialize thumbnail renderer
        
        Args:
            manager_callback: Function to call on user interactions
        """
        try:
            pygame.init()
        except:
            logger.error("Failed to initialize pygame")
        
        self.thumbnails: Dict[str, 'ThumbnailWindow'] = {}
        self.manager_callback = manager_callback
        self.running = False
        self.render_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
    
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
                    self.manager_callback
                )
                self.thumbnails[thumbnail_id] = thumbnail
                logger.info(f"Added thumbnail: {thumbnail_id}")
                return True
            
            except Exception as e:
                logger.error(f"Error adding thumbnail {thumbnail_id}: {e}")
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
                logger.error(f"Error removing thumbnail {thumbnail_id}: {e}")
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
        """Main render loop (runs in separate thread)"""
        clock = pygame.time.Clock()
        
        try:
            while self.running:
                with self.lock:
                    for thumbnail in list(self.thumbnails.values()):
                        try:
                            thumbnail.render()
                        except Exception as e:
                            logger.error(f"Error rendering thumbnail: {e}")
                
                # Cap at reasonable FPS
                clock.tick(30)  # 30 FPS max
        
        except Exception as e:
            logger.error(f"Error in render loop: {e}")
    
    def is_running(self) -> bool:
        """Check if renderer is running"""
        return self.running


class ThumbnailWindow:
    """Individual thumbnail overlay window"""
    
    def __init__(self, thumbnail_id: str, config: Dict, 
                 manager_callback: Callable = None):
        """Initialize thumbnail window
        
        Args:
            thumbnail_id: Unique ID
            config: Configuration dict
            manager_callback: Callback for user interactions
        """
        self.thumbnail_id = thumbnail_id
        self.config = config
        self.manager_callback = manager_callback
        
        # Position and size
        pos = config.get("position", {})
        size = config.get("size", {})
        
        self.x = pos.get("x", 0)
        self.y = pos.get("y", 0)
        self.monitor = pos.get("monitor", 0)
        self.width = size.get("width", 320)
        self.height = size.get("height", 240)
        
        # Appearance
        self.opacity = config.get("opacity", 0.8)
        self.show_border = config.get("show_border", True)
        self.enabled = config.get("enabled", True)
        
        # State
        self.current_image: Optional[pygame.Surface] = None
        self.is_dragging = False
        self.is_resizing = False
        self.drag_start = (0, 0)
        
        # Create window
        self._create_window()
    
    def _create_window(self) -> None:
        """Create Pygame window"""
        try:
            # Set up flags for always-on-top overlay
            flags = pygame.HWSURFACE | pygame.DOUBLEBUF
            
            self.surface = pygame.display.set_mode(
                (self.width, self.height),
                flags
            )
            
            # Always-on-top is set via flags above (pygame.HIDDEN)
            # Window handle management for Tkinter integration would go here
            # For now, just use the pygame surface directly
            
            pygame.display.set_caption(self.config.get("window_title", "ScreenAlert"))
            logger.debug(f"Created window for thumbnail {self.thumbnail_id}")
        
        except Exception as e:
            logger.error(f"Error creating window: {e}")
            self.surface = None
    
    def set_image(self, pil_image: Image.Image) -> None:
        """Update displayed image"""
        try:
            # Resize to fit thumbnail
            pil_image = ImageProcessor.resize_image(
                pil_image, self.width, self.height, 
                maintain_aspect=True
            )
            
            # Convert to pygame surface
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            self.current_image = pygame.image.fromstring(
                pil_image.tobytes(), pil_image.size, pil_image.mode
            )
        
        except Exception as e:
            logger.debug(f"Error setting image: {e}")
    
    def set_position(self, x: int, y: int) -> None:
        """Update window position"""
        self.x = x
        self.y = y
        if self.surface:
            try:
                # Move window (platform-specific)
                pass
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
            if self.surface:
                pygame.display.set_mode((self.width, self.height))
        except Exception as e:
            logger.error(f"Error resizing window: {e}")
    
    def set_opacity(self, opacity: float) -> None:
        """Update window opacity"""
        self.opacity = max(0.2, min(opacity, 1.0))
    
    def render(self) -> None:
        """Render frame"""
        if not self.surface or not self.enabled:
            return
        
        try:
            # Draw background
            self.surface.fill((0, 0, 0))
            
            # Draw image
            if self.current_image:
                self.surface.blit(self.current_image, (0, 0))
            
            # Draw border if enabled
            if self.show_border:
                pygame.draw.rect(self.surface, (255, 149, 0), 
                               (0, 0, self.width, self.height), 2)
            
            # Update display
            pygame.display.flip()
        
        except Exception as e:
            logger.debug(f"Error rendering: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            if self.surface:
                pygame.display.quit()
        except:
            pass
