"""Main ScreenAlert engine - unified capture and processing loop"""

import logging
import threading
import time
import os
import re
import string
import tkinter as tk
from datetime import datetime
from typing import Dict, Optional, List, Callable
from PIL import Image

from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.core.window_manager import WindowManager
from screenalert_core.core.cache_manager import CacheManager
from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.monitoring.region_monitor import MonitoringEngine
from screenalert_core.monitoring.alert_system import AlertSystem
from screenalert_core.rendering.thumbnail_renderer import ThumbnailRenderer
from screenalert_core.utils.plugin_hooks import PluginHooks
from screenalert_core.utils.constants import DEFAULT_REFRESH_RATE_MS, TEMP_DIR

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
        self.plugin_hooks = PluginHooks()
        self.tkinter_root: Optional[tk.Tk] = None  # Will be set by main_window
        self.renderer = ThumbnailRenderer(manager_callback=self._on_thumbnail_interaction, parent_root=None)
        
        # State
        self.running = False
        self.paused = False
        self.loop_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Callbacks
        self.on_alert: Callable = lambda *args, **kwargs: None
        self.on_region_change: Callable = lambda *args, **kwargs: None
        self.on_window_lost: Callable = lambda *args, **kwargs: None
        
        # Config will be initialized after tkinter root is set
        self._config_initialized = False
        self.last_pause_reminder_ts = 0
        self._diag_last_report_ts = time.time()
        self._diag_loop_count = 0
        self._diag_capture_ms = 0.0
        self._diag_render_ms = 0.0
        self._diag_monitor_ms = 0.0
        self._diag_alert_count = 0
        self._diag_change_count = 0
        self._reconnect_attempted_once: set[str] = set()
        self._window_lost_notified: set[str] = set()
        logger.info("ScreenAlert engine initialized")
        logger.debug(f"Config path: {config_path}")
        logger.debug("WindowManager, CacheManager, MonitoringEngine, AlertSystem, ThumbnailRenderer initialized")

    def register_plugin_hook(self, event_name: str, callback: Callable[..., None]) -> None:
        """Register callback for plugin extension events."""
        self.plugin_hooks.register(event_name, callback)

    def unregister_plugin_hook(self, event_name: str, callback: Callable[..., None]) -> bool:
        """Unregister callback for plugin extension events."""
        return self.plugin_hooks.unregister(event_name, callback)

    def list_plugin_events(self) -> List[str]:
        """Return currently registered plugin event names."""
        return self.plugin_hooks.list_events()
    
    def set_tkinter_root(self, root: 'tk.Tk') -> None:
        """Set the main tkinter root for overlay windows
        
        Args:
            root: The main tkinter Tk instance
        """
        self.tkinter_root = root
        self.renderer.parent_root = root
        logger.debug("Set tkinter root for renderer")
        # Now that we have a tkinter root, initialize from config
        if not self._config_initialized:
            self._initialize_from_config()
            self._config_initialized = True
            logger.debug("Initialized thumbnails from config")
        logger.info("tkinter root set, config initialized")
    
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
                
                # Immediately capture and display (same as add_thumbnail)
                window_hwnd = config.get("window_hwnd")
                if window_hwnd:
                    expected_title = config.get("window_title")
                    expected_class = config.get("window_class") or None
                    expected_size = tuple(config.get("window_size")) if config.get("window_size") else None
                    expected_monitor = config.get("monitor_id")
                    if self.window_manager.validate_window_identity(
                        window_hwnd,
                        expected_title=expected_title,
                        expected_class=expected_class,
                        expected_monitor_id=expected_monitor,
                        expected_size=expected_size,
                    ):
                        window_image = self.window_manager.capture_window(window_hwnd)
                        if window_image:
                            logger.info(f"[{thumbnail_id}] Initial capture from config: {window_image.size}")
                            self.renderer.update_thumbnail_image(thumbnail_id, window_image)
                            self.renderer.set_thumbnail_availability(thumbnail_id, True)
                        else:
                            self.renderer.set_thumbnail_availability(
                                thumbnail_id,
                                False,
                                self.config.get_show_overlay_when_unavailable(),
                            )
                    else:
                        self.renderer.set_thumbnail_availability(
                            thumbnail_id,
                            False,
                            self.config.get_show_overlay_when_unavailable(),
                        )
            
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
    
    def add_thumbnail(self, window_title: str, window_hwnd: int,
                      window_class: str = None, window_size: tuple = None,
                      monitor_id: int = None) -> Optional[str]:
        """Add new thumbnail for window
        
        Args:
            window_title: Window title
            window_hwnd: Window handle
            window_class: Optional window class hint from selector
            window_size: Optional window size hint from selector
            monitor_id: Optional monitor index hint from selector
        
        Returns:
            Thumbnail ID or None if failed
        """
        try:
            # Capture window metadata for identity validation on reconnect.
            # Prefer explicit values from selector, fill any missing values from live metadata.
            metadata = self.window_manager.get_window_metadata(window_hwnd)
            resolved_window_class = window_class or (metadata.get('class', '') if metadata else '')
            resolved_window_size = window_size or (metadata.get('size') if metadata else None)
            resolved_monitor_id = monitor_id if monitor_id is not None else (metadata.get('monitor_id') if metadata else None)
            
            # Create config entry with metadata
            thumbnail_id = self.config.add_thumbnail(
                window_title, window_hwnd,
                window_class=resolved_window_class,
                window_size=resolved_window_size,
                monitor_id=resolved_monitor_id
            )
            
            # Get config
            config = self.config.get_thumbnail(thumbnail_id)
            
            # Add to renderer
            if not self.renderer.add_thumbnail(thumbnail_id, config):
                self.config.remove_thumbnail(thumbnail_id)
                return None
            
            # Immediately capture and display the window (don't wait for monitoring to start)
            logger.info(f"[{thumbnail_id}] Capturing initial window image...")
            window_image = self.window_manager.capture_window(window_hwnd)
            if window_image:
                logger.info(f"[{thumbnail_id}] Initial capture: {window_image.size}")
                self.renderer.update_thumbnail_image(thumbnail_id, window_image)
                self.renderer.set_thumbnail_availability(thumbnail_id, True)
            else:
                logger.warning(f"[{thumbnail_id}] Failed to capture initial image")
                self.renderer.set_thumbnail_availability(
                    thumbnail_id,
                    False,
                    self.config.get_show_overlay_when_unavailable(),
                )
            
            self.config.save()
            logger.info(f"Added thumbnail: {thumbnail_id}")
            self.plugin_hooks.emit("thumbnail.added", thumbnail_id=thumbnail_id, hwnd=window_hwnd, title=window_title)
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
            self.plugin_hooks.emit("thumbnail.removed", thumbnail_id=thumbnail_id)
            return True
        
        except Exception as e:
            logger.error(f"Error removing thumbnail: {e}")
            return False
    
    def add_region(self, thumbnail_id: str, name: str, rect: tuple,
                  alert_threshold: float = None) -> Optional[str]:
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
                "alert_threshold": alert_threshold if alert_threshold is not None else self.config.get_default_alert_threshold(),
                "change_detection_method": self.config.get_change_detection_method(),
                "enabled": True,
                "sound_file": self.config.get_default_sound_file(),
                "tts_message": "Alert {window} {region_name}"
            }
            
            region_id = self.config.add_region_to_thumbnail(thumbnail_id, region_config)
            if region_id:
                self.monitoring_engine.add_region(region_id, thumbnail_id, region_config)
                self.config.save()
                logger.info(f"Added region: {region_id}")
                self.plugin_hooks.emit("region.added", thumbnail_id=thumbnail_id, region_id=region_id, name=name)
            
            return region_id
        
        except Exception as e:
            logger.error(f"Error adding region: {e}")
            return None

    def _render_tts_message(self, template: str, window_title: str, region_name: str) -> str:
        """Render TTS template with supported placeholders.

        Supported placeholders:
            {window}
            {region_name}

        Unknown placeholders are preserved as literals.
        """
        if not template:
            return ""

        mapping = {
            "window": window_title or "Unknown Window",
            "region_name": region_name or "Region",
        }

        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        try:
            return string.Formatter().vformat(template, (), _SafeDict(mapping)).strip()
        except Exception:
            return template.strip()
    
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
            self.plugin_hooks.emit("engine.started")
            return True
        
        except Exception as e:
            logger.error(f"Error starting engine: {e}")
            self.running = False
            return False
    
    def stop(self) -> None:
        """Stop the engine"""
        self.running = False
        try:
            self.renderer.stop()
        except Exception as error:
            logger.error(f"Error stopping renderer: {error}")

        if self.loop_thread:
            try:
                self.loop_thread.join(timeout=5.0)
            except Exception as error:
                logger.error(f"Error joining loop thread: {error}")

        try:
            self.config.save()
        except Exception as error:
            logger.error(f"Error saving config during stop: {error}")

        try:
            self.alert_system.cleanup()
        except Exception as error:
            logger.error(f"Error cleaning alert system: {error}")

        try:
            self.cache_manager.invalidate_all()
            self.cache_manager.cleanup_temp_files(TEMP_DIR, max_age_seconds=0)
        except Exception as error:
            logger.error(f"Error cleaning cache/temp files: {error}")

        try:
            self.plugin_hooks.emit("engine.stopped")
        except Exception as error:
            logger.error(f"Error emitting engine.stopped hook: {error}")
        
        logger.info("ScreenAlert engine stopped")
    
    def set_paused(self, paused: bool) -> None:
        """Pause/resume monitoring"""
        self.paused = paused
        logger.info(f"Monitoring paused: {paused}")

    def reconnect_all_windows(self) -> Dict[str, int]:
        """Manually attempt strict reconnect for all configured thumbnails.

        Returns:
            Dict with counters: total, attempted, reconnected, failed, already_valid.
        """
        with self.lock:
            thumbnails = list(self.config.get_all_thumbnails())

        result = {
            "total": len(thumbnails),
            "attempted": 0,
            "reconnected": 0,
            "failed": 0,
            "already_valid": 0,
        }

        for thumbnail_config in thumbnails:
            thumbnail_id = thumbnail_config.get("id")
            if not thumbnail_id:
                continue

            window_hwnd = thumbnail_config.get("window_hwnd")
            window_title = thumbnail_config.get("window_title", "")
            expected_class = thumbnail_config.get("window_class") or None
            expected_size = tuple(thumbnail_config["window_size"]) if thumbnail_config.get("window_size") else None
            expected_monitor = thumbnail_config.get("monitor_id")

            # Manual reconnect should always permit a fresh attempt.
            self._reconnect_attempted_once.discard(thumbnail_id)
            self._window_lost_notified.discard(thumbnail_id)

            is_valid = self.window_manager.validate_window_identity(
                window_hwnd,
                expected_title=window_title,
                expected_class=expected_class,
                expected_monitor_id=expected_monitor,
                expected_size=expected_size,
            )

            if is_valid:
                self.renderer.set_thumbnail_availability(thumbnail_id, True)
                result["already_valid"] += 1
                continue

            result["attempted"] += 1
            new_window = self._try_reconnect(
                thumbnail_id,
                window_title,
                expected_class,
                expected_size,
                expected_monitor,
            )

            if new_window:
                self.renderer.set_thumbnail_availability(thumbnail_id, True)
                result["reconnected"] += 1
            else:
                self._reconnect_attempted_once.add(thumbnail_id)
                self._window_lost_notified.add(thumbnail_id)
                self.renderer.set_thumbnail_availability(
                    thumbnail_id,
                    False,
                    self.config.get_show_overlay_when_unavailable(),
                )
                result["failed"] += 1

        return result

    def reconnect_window(self, thumbnail_id: str) -> str:
        """Manually attempt strict reconnect for a single thumbnail.

        Returns one of: "missing", "already_valid", "reconnected", "failed".
        """
        thumbnail_config = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail_config:
            return "missing"

        window_hwnd = thumbnail_config.get("window_hwnd")
        window_title = thumbnail_config.get("window_title", "")
        expected_class = thumbnail_config.get("window_class") or None
        expected_size = tuple(thumbnail_config["window_size"]) if thumbnail_config.get("window_size") else None
        expected_monitor = thumbnail_config.get("monitor_id")

        self._reconnect_attempted_once.discard(thumbnail_id)
        self._window_lost_notified.discard(thumbnail_id)

        is_valid = self.window_manager.validate_window_identity(
            window_hwnd,
            expected_title=window_title,
            expected_class=expected_class,
            expected_monitor_id=expected_monitor,
            expected_size=expected_size,
        )
        if is_valid:
            self.renderer.set_thumbnail_availability(thumbnail_id, True)
            return "already_valid"

        new_window = self._try_reconnect(
            thumbnail_id,
            window_title,
            expected_class,
            expected_size,
            expected_monitor,
        )
        if new_window:
            self.renderer.set_thumbnail_availability(thumbnail_id, True)
            return "reconnected"

        self._reconnect_attempted_once.add(thumbnail_id)
        self._window_lost_notified.add(thumbnail_id)
        self.renderer.set_thumbnail_availability(
            thumbnail_id,
            False,
            self.config.get_show_overlay_when_unavailable(),
        )
        return "failed"
    
    def _try_reconnect(self, thumbnail_id: str, window_title: str,
                       expected_class: str = None,
                       expected_size=None,
                       expected_monitor_id: int = None) -> Optional[Dict]:
        """Try to reconnect to a window when the current handle is invalid.
        
        Returns:
            New window dict if reconnected, None otherwise
        """
        logger.info(f"[{thumbnail_id}] Attempting reconnection for '{window_title}'")
        
        # Strict reconnect: exact title + exact size (+ optional class/monitor).
        # No fallback matching is allowed.
        if not expected_size:
            logger.warning(
                f"[{thumbnail_id}] Reconnection aborted: missing expected size for strict matching"
            )
            return None

        new_window = self.window_manager.find_window_by_title(
            window_title, exact=True,
            expected_size=expected_size, size_tolerance=0,
            expected_monitor_id=expected_monitor_id,
            expected_class_name=expected_class,
        )
        
        if new_window:
            new_hwnd = new_window['hwnd']
            logger.info(f"[{thumbnail_id}] Reconnected: "
                        f"new hwnd={new_hwnd}, size={new_window.get('size')}")
            
            # Update config with new handle and refreshed metadata
            metadata = self.window_manager.get_window_metadata(new_hwnd)
            updates = {"window_hwnd": new_hwnd}
            if metadata:
                updates["window_class"] = metadata.get('class', '')
                updates["window_size"] = list(metadata.get('size', []))
                updates["monitor_id"] = metadata.get('monitor_id')
            
            with self.lock:
                self.config.update_thumbnail(thumbnail_id, updates)
                self.config.save()
            
            return new_window
        
        logger.warning(f"[{thumbnail_id}] Reconnection failed for '{window_title}'")
        return None
    
    def _main_loop(self) -> None:
        """Main unified capture and processing loop"""
        # Track previous state per region to fire callbacks only on transitions
        _prev_region_state: dict[str, str] = {}

        while self.running:
            try:
                start_time = time.time()
                refresh_rate_ms = self.config.get_refresh_rate()
                
                # Get snapshot of all thumbnails (copy to avoid mutation during iteration)
                with self.lock:
                    thumbnails = list(self.config.get_all_thumbnails())
                
                # Process each thumbnail
                for thumbnail_config in thumbnails:
                    if not thumbnail_config.get("enabled", True):
                        continue
                    
                    thumbnail_id = thumbnail_config["id"]
                    window_hwnd = thumbnail_config["window_hwnd"]
                    window_title = thumbnail_config["window_title"]
                    
                    # Validate window: both existence AND identity
                    expected_class = thumbnail_config.get("window_class") or None
                    expected_size = tuple(thumbnail_config["window_size"]) if thumbnail_config.get("window_size") else None
                    expected_monitor = thumbnail_config.get("monitor_id")
                    
                    window_ok = self.window_manager.validate_window_identity(
                        window_hwnd,
                        expected_title=window_title,
                        expected_class=expected_class,
                        expected_monitor_id=expected_monitor,
                        expected_size=expected_size
                    )

                    if window_ok:
                        self._reconnect_attempted_once.discard(thumbnail_id)
                        self._window_lost_notified.discard(thumbnail_id)
                    
                    if not window_ok:
                        if thumbnail_id in self._reconnect_attempted_once:
                            self.renderer.set_thumbnail_availability(
                                thumbnail_id,
                                False,
                                self.config.get_show_overlay_when_unavailable(),
                            )
                            if thumbnail_id not in self._window_lost_notified:
                                self.plugin_hooks.emit("window.lost", thumbnail_id=thumbnail_id, title=window_title)
                                self.on_window_lost(thumbnail_id, window_title)
                                self._window_lost_notified.add(thumbnail_id)
                            continue

                        # Try to reconnect to the correct window
                        new_window = self._try_reconnect(
                            thumbnail_id, window_title,
                            expected_class, expected_size, expected_monitor
                        )
                        if new_window:
                            window_hwnd = new_window['hwnd']
                            self._reconnect_attempted_once.discard(thumbnail_id)
                            self._window_lost_notified.discard(thumbnail_id)
                        else:
                            self._reconnect_attempted_once.add(thumbnail_id)
                            self.renderer.set_thumbnail_availability(
                                thumbnail_id,
                                False,
                                self.config.get_show_overlay_when_unavailable(),
                            )
                            if thumbnail_id not in self._window_lost_notified:
                                self.plugin_hooks.emit("window.lost", thumbnail_id=thumbnail_id, title=window_title)
                                self.on_window_lost(thumbnail_id, window_title)
                                self._window_lost_notified.add(thumbnail_id)
                            continue
                    
                    # UNIFIED CAPTURE
                    capture_start = time.perf_counter()
                    cached_image = self.cache_manager.get(window_hwnd)
                    if cached_image is None:
                        window_image = self.window_manager.capture_window(window_hwnd)
                        if window_image:
                            self.cache_manager.set(window_hwnd, window_image)
                            self.renderer.set_thumbnail_availability(thumbnail_id, True)
                            logger.debug(f"[{thumbnail_id}] CAPTURED: size {window_image.size}")
                        else:
                            self.renderer.set_thumbnail_availability(
                                thumbnail_id,
                                False,
                                self.config.get_show_overlay_when_unavailable(),
                            )
                            logger.error(f"[{thumbnail_id}] CAPTURE FAILED: hwnd={window_hwnd}")
                            continue
                    else:
                        window_image = cached_image
                        self.renderer.set_thumbnail_availability(thumbnail_id, True)
                        logger.debug(f"[{thumbnail_id}] Using cached image: {window_image.size}")
                    self._diag_capture_ms += (time.perf_counter() - capture_start) * 1000.0
                    
                    # Update renderer with full window image
                    render_start = time.perf_counter()
                    logger.debug(f"[{thumbnail_id}] Sending to renderer: {window_image.size}")
                    result = self.renderer.update_thumbnail_image(thumbnail_id, window_image)
                    if not result:
                        logger.error(f"[{thumbnail_id}] RENDERER REJECTED (thumbnail not found?)")
                    else:
                        logger.debug(f"[{thumbnail_id}] Renderer accepted image")
                    self._diag_render_ms += (time.perf_counter() - render_start) * 1000.0
                    
                    # Process monitoring regions (uses same captured image)
                    if not self.paused:
                        monitor_start = time.perf_counter()
                        alert_hold_seconds = self.config.get_alert_hold_seconds()
                        region_results = self.monitoring_engine.update_regions(
                            thumbnail_id, window_image, alert_hold_seconds
                        )
                        self._diag_monitor_ms += (time.perf_counter() - monitor_start) * 1000.0
                        
                        for region_id, state, should_play_sound in region_results:
                            # Fire state-change callback when state transitions
                            prev = _prev_region_state.get(region_id)
                            if state != prev:
                                _prev_region_state[region_id] = state
                                self._diag_change_count += 1
                                self.plugin_hooks.emit("region.changed", thumbnail_id=thumbnail_id, region_id=region_id)
                                self.on_region_change(thumbnail_id, region_id, state)
                            
                            if should_play_sound:
                                # Play alert sound
                                region = self.monitoring_engine.get_monitor(region_id)
                                if region:
                                    config = region.config
                                    sound_file = config.get("sound_file", "")
                                    tts_template = config.get("tts_message", "") or self.config.get_default_tts_message()
                                    tts_message = self._render_tts_message(
                                        tts_template,
                                        thumbnail_config.get("window_title", "Unknown"),
                                        config.get("name", "Region"),
                                    )

                                    # Optional: suppress alerts during fullscreen apps
                                    if self.config.get_suppress_fullscreen() and self.window_manager.is_foreground_fullscreen():
                                        logger.info("Suppressing alert due to fullscreen foreground application")
                                        continue

                                    # Optional: global mute timer
                                    mute_until = self.config.get_mute_until_ts()
                                    if mute_until > int(time.time()):
                                        logger.info("Alert muted by countdown timer")
                                    else:
                                        play_sound = sound_file if self.config.get_enable_sound() else ""
                                        play_tts = tts_message if self.config.get_enable_tts() else ""
                                        logger.info(
                                            "Dispatching alert media: sound=%s tts=%s message=%s",
                                            bool(play_sound),
                                            bool(play_tts),
                                            play_tts if play_tts else ""
                                        )
                                        self.alert_system.play_alert(play_sound, play_tts)

                                    # Optional: capture screenshot on alert
                                    if self.config.get_capture_on_alert():
                                        self._capture_region_snapshot(thumbnail_config, config, window_image, status="alert")

                                    # Alert history
                                    self.config.add_alert_history({
                                        "timestamp": datetime.now().isoformat(),
                                        "thumbnail_id": thumbnail_id,
                                        "region_id": region_id,
                                        "window_title": thumbnail_config.get("window_title", "Unknown"),
                                        "region_name": config.get("name", "Region"),
                                        "status": "alert"
                                    })
                                    self.plugin_hooks.emit(
                                        "alert",
                                        thumbnail_id=thumbnail_id,
                                        region_id=region_id,
                                        region_name=config.get("name", "")
                                    )
                                    self._diag_alert_count += 1
                                    self.on_alert(thumbnail_id, region_id, config.get("name", ""))
                
                # Sleep to maintain refresh rate
                elapsed = (time.time() - start_time) * 1000  # Convert to ms
                sleep_time = max(1, refresh_rate_ms - elapsed) / 1000  # Convert to seconds

                if self.config.get_diagnostics_enabled():
                    self._diag_loop_count += 1
                    now = time.time()
                    if (now - self._diag_last_report_ts) >= 10.0:
                        logger.info(
                            "[ENGINE DIAG] loops=%s elapsed_ms=%.2f capture_ms=%.2f render_ms=%.2f monitor_ms=%.2f changes=%s alerts=%s thumbnails=%s",
                            self._diag_loop_count,
                            elapsed,
                            self._diag_capture_ms,
                            self._diag_render_ms,
                            self._diag_monitor_ms,
                            self._diag_change_count,
                            self._diag_alert_count,
                            len(thumbnails),
                        )
                        if elapsed > (refresh_rate_ms * 1.5):
                            logger.warning(
                                "[ENGINE DIAG] loop overrun: elapsed_ms=%.2f refresh_rate_ms=%s",
                                elapsed,
                                refresh_rate_ms,
                            )
                        self._diag_last_report_ts = now
                        self._diag_loop_count = 0
                        self._diag_capture_ms = 0.0
                        self._diag_render_ms = 0.0
                        self._diag_monitor_ms = 0.0
                        self._diag_alert_count = 0
                        self._diag_change_count = 0

                time.sleep(sleep_time)
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(0.1)

    def _capture_region_snapshot(self, thumbnail_config: Dict, region_config: Dict,
                                 window_image: Image.Image, status: str = "alert") -> None:
        """Capture and persist region snapshot image."""
        try:
            capture_dir = self.config.get_capture_dir()
            os.makedirs(capture_dir, exist_ok=True)

            window_title = thumbnail_config.get("window_title", "window")
            region_name = region_config.get("name", "region")

            def safe(text: str) -> str:
                text = re.sub(r'[^a-zA-Z0-9._-]+', '_', text or "")
                return text[:64] or "item"

            pattern = self.config.get_capture_filename_format()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = pattern.format(
                timestamp=timestamp,
                window=safe(window_title),
                region=safe(region_name),
                status=safe(status),
            )
            if not filename.lower().endswith(".png"):
                filename += ".png"
            output_path = os.path.join(capture_dir, filename)

            rect = region_config.get("rect", (0, 0, 0, 0))
            region_img = ImageProcessor.crop_region(window_image, tuple(rect))
            region_img.save(output_path, format="PNG")
            logger.info(f"Saved snapshot: {output_path}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot: {e}")
    
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
