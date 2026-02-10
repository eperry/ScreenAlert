"""Main ScreenAlert engine - unified capture and processing loop"""

import logging
import threading
import time
from typing import Dict, Optional, List, Callable
from PIL import Image

from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.core.window_manager import WindowManager
from screenalert_core.core.cache_manager import CacheManager
from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.monitoring.region_monitor import MonitoringEngine
from screenalert_core.monitoring.alert_system import AlertSystem
from screenalert_core.rendering.thumbnail_renderer import ThumbnailRenderer
from screenalert_core.utils.constants import DEFAULT_REFRESH_RATE_MS

logger = logging.getLogger(__name__)


class ScreenAlertEngine:
    """Main engine coordinating all ScreenAlert components"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize ScreenAlert engine
        
        Args:
            config_path: Path to configuration file
        """
        # Initialize components
        self.config = ConfigManager(config_path)
        self.window_manager = WindowManager()
        self.cache_manager = CacheManager(lifetime_seconds=1.0)
        self.monitoring_engine = MonitoringEngine()
        self.alert_system = AlertSystem()
        self.renderer = ThumbnailRenderer(manager_callback=self._on_thumbnail_interaction)
        
        # State
        self.running = False
        self.paused = False
        self.loop_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Callbacks
        self.on_alert: Callable = lambda *args, **kwargs: None
        self.on_region_change: Callable = lambda *args, **kwargs: None
        self.on_window_lost: Callable = lambda *args, **kwargs: None
        
        # Initialize from config
        self._initialize_from_config()
        
        logger.info("ScreenAlert engine initialized")
    
    def _initialize_from_config(self) -> None:
        """Load thumbnails and regions from config"""
        for thumbnail_config in self.config.get_all_thumbnails():
            self._add_thumbnail_from_config(thumbnail_config)
            logger.debug(f"Initialized thumbnail from config: {thumbnail_config.get('id')}")
    
    def _add_thumbnail_from_config(self, config: Dict) -> bool:
        """Add thumbnail from config dict - mirrors add_thumbnail() flow"""
        thumbnail_id = config.get("id")
        if not thumbnail_id:
            return False
        
        try:
            # Check if already added
            if thumbnail_id in [t['id'] for t in self.config.get_all_thumbnails()]:
                # Already in config, just add to renderer
                if not self.renderer.add_thumbnail(thumbnail_id, config):
                    logger.warning(f"Failed to add renderer for {thumbnail_id}")
                    return False
            
            # Load regions  
            for region_config in config.get("monitored_regions", []):
                region_id = region_config.get("id")
                if region_id:
                    self.monitoring_engine.add_region(region_id, thumbnail_id, region_config)
            
            logger.info(f"Loaded thumbnail from config: {thumbnail_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading thumbnail from config: {e}", exc_info=True)
            return False
    
    def add_thumbnail(self, window_title: str, window_hwnd: int) -> Optional[str]:
        """Add new thumbnail for window
        
        Args:
            window_title: Window title
            window_hwnd: Window handle
        
        Returns:
            Thumbnail ID or None if failed
        """
        try:
            # Create config entry
            thumbnail_id = self.config.add_thumbnail(window_title, window_hwnd)
            
            # Get config
            config = self.config.get_thumbnail(thumbnail_id)
            
            # Add to renderer
            if not self.renderer.add_thumbnail(thumbnail_id, config):
                self.config.remove_thumbnail(thumbnail_id)
                return None
            
            self.config.save()
            logger.info(f"Added thumbnail: {thumbnail_id}")
            return thumbnail_id
        
        except Exception as e:
            logger.error(f"Error adding thumbnail: {e}")
            return None
    
    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        """Remove thumbnail"""
        try:
            # Remove from renderer
            if not self.renderer.remove_thumbnail(thumbnail_id):
                return False
            
            # Remove from monitoring
            monitors = self.monitoring_engine.get_thumbnail_monitors(thumbnail_id)
            for monitor in monitors:
                self.monitoring_engine.remove_region(monitor.region_id)
            
            # Remove from config
            self.config.remove_thumbnail(thumbnail_id)
            self.config.save()
            
            logger.info(f"Removed thumbnail: {thumbnail_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing thumbnail: {e}")
            return False
    
    def add_region(self, thumbnail_id: str, name: str, rect: tuple,
                  alert_threshold: float = 0.99) -> Optional[str]:
        """Add monitoring region to thumbnail
        
        Args:
            thumbnail_id: Parent thumbnail ID
            name: Region name
            rect: (x, y, width, height)
            alert_threshold: Change detection threshold
        
        Returns:
            Region ID or None if failed
        """
        try:
            region_config = {
                "name": name,
                "rect": rect,
                "alert_threshold": alert_threshold,
                "enabled": True,
                "sound_file": "",
                "tts_message": ""
            }
            
            region_id = self.config.add_region_to_thumbnail(thumbnail_id, region_config)
            if region_id:
                self.monitoring_engine.add_region(region_id, thumbnail_id, region_config)
                self.config.save()
                logger.info(f"Added region: {region_id}")
            
            return region_id
        
        except Exception as e:
            logger.error(f"Error adding region: {e}")
            return None
    
    def start(self) -> bool:
        """Start the engine"""
        if self.running:
            logger.warning("Engine already running")
            return False
        
        try:
            self.running = True
            self.renderer.start()
            
            # Start main loop thread
            self.loop_thread = threading.Thread(target=self._main_loop, daemon=True)
            self.loop_thread.start()
            
            logger.info("ScreenAlert engine started")
            return True
        
        except Exception as e:
            logger.error(f"Error starting engine: {e}")
            self.running = False
            return False
    
    def stop(self) -> None:
        """Stop the engine"""
        self.running = False
        self.renderer.stop()
        
        if self.loop_thread:
            self.loop_thread.join(timeout=5.0)
        
        self.config.save()
        self.alert_system.cleanup()
        
        logger.info("ScreenAlert engine stopped")
    
    def set_paused(self, paused: bool) -> None:
        """Pause/resume monitoring"""
        self.paused = paused
        logger.info(f"Monitoring paused: {paused}")
    
    def _main_loop(self) -> None:
        """Main unified capture and processing loop"""
        refresh_rate_ms = self.config.get_refresh_rate()
        highlight_time_sec = 5  # TODO: make configurable
        
        while self.running:
            try:
                start_time = time.time()
                
                # Get all thumbnails
                with self.lock:
                    thumbnails = self.config.get_all_thumbnails()
                
                # Process each thumbnail
                for thumbnail_config in thumbnails:
                    if not thumbnail_config.get("enabled", True):
                        continue
                    
                    thumbnail_id = thumbnail_config["id"]
                    window_hwnd = thumbnail_config["window_hwnd"]
                    
                    # Check if window is still valid
                    if not self.window_manager.is_window_valid(window_hwnd):
                        self.on_window_lost(thumbnail_id, thumbnail_config["window_title"])
                        continue
                    
                    # UNIFIED CAPTURE
                    cached_image = self.cache_manager.get(window_hwnd)
                    if cached_image is None:
                        window_image = self.window_manager.capture_window(window_hwnd)
                        if window_image:
                            self.cache_manager.set(window_hwnd, window_image)
                            logger.info(f"CAPTURED: {thumbnail_id} - size {window_image.size}")
                        else:
                            logger.error(f"CAPTURE FAILED: {thumbnail_id} hwnd={window_hwnd}")
                            continue
                    else:
                        window_image = cached_image
                    
                    # Update renderer with full window image
                    logger.info(f"RENDERER UPDATE: {thumbnail_id} - {window_image.size}")
                    result = self.renderer.update_thumbnail_image(thumbnail_id, window_image)
                    if not result:
                        logger.error(f"RENDERER REJECTED: {thumbnail_id}")
                    
                    # Process monitoring regions (uses same captured image)
                    if not self.paused:
                        region_results = self.monitoring_engine.update_regions(
                            thumbnail_id, window_image, highlight_time_sec
                        )
                        
                        for region_id, changed, should_alert in region_results:
                            if changed:
                                self.on_region_change(thumbnail_id, region_id)
                            
                            if should_alert:
                                # Play alert
                                region = self.monitoring_engine.get_monitor(region_id)
                                if region:
                                    config = region.config
                                    sound_file = config.get("sound_file", "")
                                    tts_message = config.get("tts_message", "")
                                    
                                    self.alert_system.play_alert(sound_file, tts_message)
                                    self.on_alert(thumbnail_id, region_id, config.get("name", ""))
                
                # Sleep to maintain refresh rate
                elapsed = (time.time() - start_time) * 1000  # Convert to ms
                sleep_time = max(1, refresh_rate_ms - elapsed) / 1000  # Convert to seconds
                time.sleep(sleep_time)
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(0.1)
    
    def _on_thumbnail_interaction(self, thumbnail_id: str, action: str) -> None:
        """Handle thumbnail user interactions"""
        logger.debug(f"Thumbnail {thumbnail_id} action: {action}")
        
        if action == "activated":
            # Bring corresponding window to front
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            if thumbnail:
                hwnd = thumbnail["window_hwnd"]
                self.window_manager.activate_window(hwnd)
        
        elif action == "position_changed":
            # Position will be updated via renderer
            pass
        
        elif action == "size_changed":
            # Size will be updated via renderer
            pass
    
    def is_running(self) -> bool:
        """Check if engine is running"""
        return self.running
