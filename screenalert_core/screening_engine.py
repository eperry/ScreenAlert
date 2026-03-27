"""Main ScreenAlert engine - unified capture and processing loop"""

import logging
import threading
import time
import os
import re
import string
import ctypes
import tkinter as tk
from datetime import datetime
from typing import Dict, Optional, List, Callable, Tuple
from PIL import Image

from screenalert_core.core.config_manager import ConfigManager
from screenalert_core.core.window_manager import WindowManager
from screenalert_core.core.cache_manager import CacheManager
from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.monitoring.region_monitor import MonitoringEngine
from screenalert_core.monitoring.alert_system import AlertSystem
from screenalert_core.rendering.overlay_manager import OverlayManager
from screenalert_core.utils.plugin_hooks import PluginHooks
from screenalert_core.utils.constants import DEFAULT_REFRESH_RATE_MS, TEMP_DIR
from screenalert_core.utils.diagnostics import save_alert_diagnostics

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
        self.renderer = OverlayManager(manager_callback=self._on_thumbnail_interaction, parent_root=None)
        
        # State
        self.running = False
        self.paused = False
        self.loop_thread: Optional[threading.Thread] = None
        self._discovery_thread: Optional[threading.Thread] = None
        self._discovery_stop_event = threading.Event()
        self.foreground_hook_thread: Optional[threading.Thread] = None
        self._foreground_hook_thread_id: Optional[int] = None
        self._foreground_event_hook_handle = None
        self._foreground_event_proc = None
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
        self._last_foreground_sync_ts = 0.0
        self._reconnect_attempted_once: set[str] = set()
        self._window_lost_notified: set[str] = set()
        self._thumbnail_connected: Dict[str, bool] = {}
        self._prev_window_images: Dict[str, Image.Image] = {}
        logger.info("ScreenAlert engine initialized")
        logger.debug(f"Config path: {config_path}")
        logger.debug("WindowManager, CacheManager, MonitoringEngine, AlertSystem, OverlayManager initialized")

    def register_plugin_hook(self, event_name: str, callback: Callable[..., None]) -> None:
        """Register callback for plugin extension events."""
        self.plugin_hooks.register(event_name, callback)

    def unregister_plugin_hook(self, event_name: str, callback: Callable[..., None]) -> bool:
        """Unregister callback for plugin extension events."""
        return self.plugin_hooks.unregister(event_name, callback)

    def list_plugin_events(self) -> List[str]:
        """Return currently registered plugin event names."""
        return self.plugin_hooks.list_events()

    def is_thumbnail_connected(self, thumbnail_id: str) -> bool:
        """Return cached connection status for a thumbnail (non-blocking)."""
        return self._thumbnail_connected.get(thumbnail_id, False)

    def get_attached_hwnds(self, exclude_thumbnail_id: str = None) -> set:
        """Return set of window hwnds currently attached to thumbnails.

        Args:
            exclude_thumbnail_id: Optionally exclude this thumbnail (e.g. when
                reconnecting it, its own hwnd shouldn't block the search).
        """
        attached = set()
        with self.lock:
            for tc in self.config.get_all_thumbnails():
                tid = tc.get("id")
                if tid == exclude_thumbnail_id:
                    continue
                if self._thumbnail_connected.get(tid, False):
                    hwnd = tc.get("window_hwnd")
                    if hwnd:
                        attached.add(hwnd)
        return attached

    def _get_global_detection_config(self) -> Dict:
        """Build a flat dict of global detection settings for detector creation."""
        return {
            "detection_method": self.config.get_change_detection_method(),
            "alert_threshold": self.config.get_default_alert_threshold(),
            "min_edge_fraction": self.config.get_min_edge_fraction(),
            "canny_low": self.config.get_canny_low(),
            "canny_high": self.config.get_canny_high(),
            "edge_binarize": self.config.get_edge_binarize(),
            "bg_history": self.config.get_bg_history(),
            "bg_var_threshold": self.config.get_bg_var_threshold(),
            "bg_learning_rate": self.config.get_bg_learning_rate(),
            "bg_min_fg_fraction": self.config.get_bg_min_fg_fraction(),
            "bg_warmup_frames": self.config.get_bg_warmup_frames(),
        }
    
    def set_tkinter_root(self, root: 'tk.Tk') -> None:
        """Set the main tkinter root for overlay windows
        
        Args:
            root: The main tkinter Tk instance
        """
        self.tkinter_root = root
        # OverlayManager does not use tkinter; parent_root kept for compat
        self.renderer.parent_root = root
        logger.debug("Set tkinter root")
        # Now that we have a tkinter root, initialize from config
        if not self._config_initialized:
            self._initialize_from_config()
            self._config_initialized = True
            logger.debug("Initialized thumbnails from config")
        logger.info("tkinter root set, config initialized")
    
    # ── Window identity helpers ───────────────────────────────────────────

    @staticmethod
    def _extract_window_identity(tc: Dict) -> Tuple[str, Optional[str], Optional[tuple], Optional[int]]:
        """Extract (title, class, size, monitor_id) from a thumbnail config dict."""
        title = tc.get("window_title", "")
        cls = tc.get("window_class") or None
        raw_size = tc.get("window_size")
        size = tuple(raw_size) if raw_size else None
        monitor = tc.get("monitor_id")
        return title, cls, size, monitor

    def _validate_thumbnail_window(self, tc: Dict, hwnd: int) -> bool:
        """Return True if *hwnd* matches the identity stored in thumbnail config *tc*."""
        title, cls, size, monitor = self._extract_window_identity(tc)
        try:
            return self.window_manager.validate_window_identity(
                hwnd,
                expected_title=title,
                expected_class=cls,
                expected_monitor_id=monitor,
                expected_size=size,
                size_tolerance=self.config.get_reconnect_size_tolerance(),
            )
        except Exception as exc:
            logger.warning("validate_window_identity error for hwnd=%s: %s", hwnd, exc)
            return False

    # ── Config initialisation ─────────────────────────────────────────────

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
                config["always_on_top"] = self.config.get_always_on_top()
                # Already in config, just add to renderer
                if not self.renderer.add_thumbnail(thumbnail_id, config):
                    logger.warning(f"Failed to add renderer for {thumbnail_id}")
                    return False

                # Apply persisted overlay visibility before availability updates.
                self.renderer.set_thumbnail_user_visibility(
                    thumbnail_id,
                    bool(config.get("overlay_visible", config.get("overview_visible", True))),
                )
                
                # Immediately capture and display (same as add_thumbnail)
                window_hwnd = config.get("window_hwnd")
                if window_hwnd:
                    if self._validate_thumbnail_window(config, window_hwnd):
                        self._thumbnail_connected[thumbnail_id] = True
                        self.renderer.set_source_hwnd(thumbnail_id, window_hwnd)
                        self.renderer.set_thumbnail_availability(thumbnail_id, True)
                        logger.info(f"[{thumbnail_id}] DWM thumbnail linked from config: hwnd={window_hwnd}")
                    else:
                        self._thumbnail_connected[thumbnail_id] = False
                        self.renderer.set_thumbnail_availability(
                            thumbnail_id,
                            False,
                            self.config.get_show_overlay_when_unavailable(),
                        )
            
            # Load regions  
            for region_config in config.get("monitored_regions", []):
                region_id = region_config.get("id")
                if region_id:
                    self.monitoring_engine.add_region(
                        region_id, thumbnail_id, region_config,
                        global_config=self._get_global_detection_config(),
                    )
            
            logger.info(f"Loaded thumbnail from config: {thumbnail_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading thumbnail from config: {e}", exc_info=True)
            return False

    def apply_runtime_settings(
        self,
        opacity: Optional[float] = None,
        always_on_top: Optional[bool] = None,
        show_borders: Optional[bool] = None,
        show_overlay_when_unavailable: Optional[bool] = None,
        overlay_scaling_mode: Optional[str] = None,
    ) -> None:
        """Apply selected settings to active runtime components immediately."""
        if opacity is not None:
            self.config.set_all_thumbnail_opacity(opacity)
            self.renderer.set_all_thumbnail_opacity(opacity)

        if always_on_top is not None:
            self.renderer.set_all_thumbnail_topmost(bool(always_on_top))
            with self.lock:
                for thumbnail in self.config.get_all_thumbnails():
                    thumbnail["always_on_top"] = bool(always_on_top)

        if show_borders is not None:
            self.renderer.set_all_thumbnail_borders(bool(show_borders))
            with self.lock:
                for thumbnail in self.config.get_all_thumbnails():
                    thumbnail["show_border"] = bool(show_borders)

        if show_overlay_when_unavailable is not None:
            self.renderer.refresh_unavailable_thumbnails(bool(show_overlay_when_unavailable))

        if overlay_scaling_mode is not None:
            self.renderer.set_all_thumbnail_scaling_mode(overlay_scaling_mode)

    def refresh_thumbnail_titles(self) -> None:
        """Refresh overlay title text for all active thumbnails."""
        self.renderer.refresh_thumbnail_titles()
    
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

            if not thumbnail_id:
                logger.warning(f"Duplicate title rejected by config: '{window_title}'")
                return None

            # Get config
            config = self.config.get_thumbnail(thumbnail_id)
            
            # Add to renderer
            if not self.renderer.add_thumbnail(thumbnail_id, config):
                self.config.remove_thumbnail(thumbnail_id)
                return None

            # New windows start with overlay visible unless config says otherwise.
            self.renderer.set_thumbnail_user_visibility(
                thumbnail_id,
                bool(config.get("overlay_visible", config.get("overview_visible", True))),
            )
            
            # Link DWM thumbnail to source window immediately
            self.renderer.set_source_hwnd(thumbnail_id, window_hwnd)
            if self.window_manager.is_window_valid(window_hwnd):
                self.renderer.set_thumbnail_availability(thumbnail_id, True)
                logger.info(f"[{thumbnail_id}] DWM thumbnail linked: hwnd={window_hwnd}")
            else:
                logger.warning(f"[{thumbnail_id}] Source window not valid")
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
                self.monitoring_engine.add_region(
                    region_id, thumbnail_id, region_config,
                    global_config=self._get_global_detection_config(),
                )
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
            self.renderer.set_all_thumbnail_scaling_mode(self.config.get_overlay_scaling_mode())
            self.renderer.start()
            
            # Start main loop thread
            self.loop_thread = threading.Thread(target=self._main_loop, daemon=True)
            self.loop_thread.start()

            # Start Windows foreground-change event hook (no polling)
            self._start_foreground_event_hook()

            # Start auto-discovery thread for finding disconnected windows
            self._start_auto_discovery()

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

        self._stop_auto_discovery()

        try:
            self.renderer.stop()
        except Exception as error:
            logger.error(f"Error stopping renderer: {error}")

        if self.loop_thread:
            try:
                self.loop_thread.join(timeout=5.0)
            except Exception as error:
                logger.error(f"Error joining loop thread: {error}")

        self._stop_foreground_event_hook()

        try:
            self.monitoring_engine.save_all_detector_states()
        except Exception as error:
            logger.error(f"Error saving detector states: {error}")

        try:
            self.monitoring_engine.shutdown()
        except Exception as error:
            logger.error(f"Error shutting down monitoring thread pool: {error}")

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
            _, expected_class, expected_size, expected_monitor = self._extract_window_identity(thumbnail_config)
            window_title = thumbnail_config.get("window_title", "")

            # Manual reconnect should always permit a fresh attempt.
            self._reconnect_attempted_once.discard(thumbnail_id)
            self._window_lost_notified.discard(thumbnail_id)

            is_valid = self._validate_thumbnail_window(thumbnail_config, window_hwnd)

            if is_valid:
                self._mark_connected(thumbnail_id, window_hwnd, update_config=False)
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
                self._mark_connected(thumbnail_id, new_window['hwnd'], update_config=False)
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
        window_title, expected_class, expected_size, expected_monitor = self._extract_window_identity(thumbnail_config)

        self._reconnect_attempted_once.discard(thumbnail_id)
        self._window_lost_notified.discard(thumbnail_id)

        is_valid = self._validate_thumbnail_window(thumbnail_config, window_hwnd)
        if is_valid:
            self._mark_connected(thumbnail_id, window_hwnd, update_config=False)
            return "already_valid"

        new_window = self._try_reconnect(
            thumbnail_id,
            window_title,
            expected_class,
            expected_size,
            expected_monitor,
        )
        if new_window:
            self._mark_connected(thumbnail_id, new_window['hwnd'], update_config=False)
            return "reconnected"

        self._reconnect_attempted_once.add(thumbnail_id)
        self._window_lost_notified.add(thumbnail_id)
        self.renderer.set_thumbnail_availability(
            thumbnail_id,
            False,
            self.config.get_show_overlay_when_unavailable(),
        )
        return "failed"
    
    # ── Auto-discovery ────────────────────────────────────────────────

    def _start_auto_discovery(self) -> None:
        """Start background thread that periodically discovers disconnected windows."""
        if not self.config.get_auto_discovery_enabled():
            logger.info("Auto-discovery is disabled")
            return
        self._discovery_stop_event.clear()
        self._discovery_thread = threading.Thread(
            target=self._auto_discovery_loop, name="auto-discovery", daemon=True
        )
        self._discovery_thread.start()
        logger.info("Auto-discovery started (interval=%ds)",
                     self.config.get_auto_discovery_interval_sec())

    def _stop_auto_discovery(self) -> None:
        """Signal the auto-discovery thread to stop and wait for it."""
        self._discovery_stop_event.set()
        if self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=5.0)
            if self._discovery_thread.is_alive():
                logger.warning("Auto-discovery thread did not exit within timeout")
        self._discovery_thread = None

    def _auto_discovery_loop(self) -> None:
        """Periodically scan for disconnected thumbnails and try to reconnect."""
        logger.debug("Auto-discovery thread running")
        try:
            while not self._discovery_stop_event.is_set():
                interval = self.config.get_auto_discovery_interval_sec()
                # Sleep in small increments so we can exit promptly
                if self._discovery_stop_event.wait(timeout=interval):
                    break  # stop was requested

                if not self.running:
                    break

                self._auto_discover_disconnected()
        except Exception:
            logger.exception("Auto-discovery thread error")
        finally:
            logger.debug("Auto-discovery thread exited")

    def _mark_connected(self, thumbnail_id: str, hwnd: int,
                        update_config: bool = True) -> None:
        """Common post-connect actions: update config, link DWM, set available, show overlay.

        Args:
            update_config: If True, persist the new hwnd and metadata to config.
                          Set False when the caller already updated config (e.g. _try_reconnect).
        """
        if update_config:
            metadata = self.window_manager.get_window_metadata(hwnd)
            updates = {"window_hwnd": hwnd}
            if metadata:
                updates["window_class"] = metadata.get('class', '')
                updates["window_size"] = list(metadata.get('size', []))
                updates["monitor_id"] = metadata.get('monitor_id')
            with self.lock:
                self.config.update_thumbnail(thumbnail_id, updates)
            self.config.save()

        self.renderer.set_source_hwnd(thumbnail_id, hwnd)
        self.renderer.set_thumbnail_availability(thumbnail_id, True)
        if self.config.get_show_overlay_on_connect():
            self.renderer.set_thumbnail_user_visibility(thumbnail_id, True)
        self._thumbnail_connected[thumbnail_id] = True
        self._reconnect_attempted_once.discard(thumbnail_id)
        self._window_lost_notified.discard(thumbnail_id)

    def _auto_discover_disconnected(self) -> None:
        """Try to reconnect only thumbnails that are currently disconnected."""
        with self.lock:
            thumbnails = list(self.config.get_all_thumbnails())

        reconnected = 0
        attempted = 0

        for tc in thumbnails:
            thumbnail_id = tc.get("id")
            if not thumbnail_id or not tc.get("enabled", True):
                continue

            # Skip already-connected thumbnails
            if self._thumbnail_connected.get(thumbnail_id, False):
                continue

            window_hwnd = tc.get("window_hwnd")
            window_title = tc.get("window_title", "")
            if not window_title:
                continue

            _, expected_class, expected_size, expected_monitor = self._extract_window_identity(tc)

            # Quick check: maybe the stored hwnd became valid again (app restarted with same hwnd)
            if window_hwnd and self.window_manager.is_window_valid(window_hwnd):
                if self._validate_thumbnail_window(tc, window_hwnd):
                    self._mark_connected(thumbnail_id, window_hwnd)
                    reconnected += 1
                    logger.info("[%s] Auto-discovery: existing hwnd valid again", thumbnail_id)
                    continue

            # Search for the window by title
            attempted += 1
            new_window = self._try_reconnect(
                thumbnail_id, window_title, expected_class,
                expected_size, expected_monitor,
            )
            if new_window:
                self._mark_connected(thumbnail_id, new_window['hwnd'])
                reconnected += 1
                logger.info("[%s] Auto-discovery: reconnected to hwnd=%s",
                            thumbnail_id, new_window['hwnd'])

        if reconnected:
            logger.info("Auto-discovery: reconnected %d/%d disconnected thumbnails",
                        reconnected, attempted)
        else:
            logger.debug("Auto-discovery: no disconnected thumbnails found (%d checked)", attempted)

    def scale_regions_for_new_size(self, thumbnail_id: str,
                                   old_size: tuple, new_size: tuple) -> int:
        """Scale all region rects proportionally when the window size changes.

        Args:
            thumbnail_id: Thumbnail whose regions to scale.
            old_size: Previous (width, height).
            new_size: New (width, height).

        Returns:
            Number of regions scaled.
        """
        if not old_size or not new_size:
            return 0
        old_w, old_h = old_size
        new_w, new_h = new_size
        if old_w <= 0 or old_h <= 0 or (old_w == new_w and old_h == new_h):
            return 0

        sx = new_w / old_w
        sy = new_h / old_h

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return 0

        count = 0
        for region in thumbnail.get("monitored_regions", []):
            rect = region.get("rect")
            if not rect or len(rect) != 4:
                continue
            x, y, w, h = rect
            region["rect"] = [
                int(round(x * sx)),
                int(round(y * sy)),
                int(round(w * sx)),
                int(round(h * sy)),
            ]
            count += 1

        if count:
            self.config.save()
            logger.info(f"[{thumbnail_id}] Scaled {count} region(s): "
                        f"ratio {sx:.3f}x{sy:.3f} "
                        f"({old_w}x{old_h} -> {new_w}x{new_h})")
        return count

    def _try_reconnect(self, thumbnail_id: str, window_title: str,
                       expected_class: str = None,
                       expected_size=None,
                       expected_monitor_id: int = None) -> Optional[Dict]:
        """Try to reconnect to a window when the current handle is invalid.

        Returns:
            New window dict if reconnected, None otherwise
        """
        logger.info(f"[{thumbnail_id}] Attempting reconnection for '{window_title}'")

        # Collect hwnds already attached to other thumbnails so we don't steal them
        attached_hwnds = self.get_attached_hwnds(exclude_thumbnail_id=thumbnail_id)

        # Reconnect by exact title match, with optional class/monitor filtering.
        # Size is NOT used as a filter — windows may have been resized or
        # restarted at a different resolution.  The stored size is updated
        # after a successful reconnect so future validation cycles pass.
        new_window = self.window_manager.find_window_by_title(
            window_title, exact=True,
            expected_size=None,
            expected_monitor_id=expected_monitor_id,
            expected_class_name=expected_class,
        )

        # Skip windows already attached to another thumbnail
        if new_window and new_window['hwnd'] in attached_hwnds:
            logger.debug(f"[{thumbnail_id}] Skipping hwnd={new_window['hwnd']} — already attached to another thumbnail")
            new_window = None

        if new_window:
            new_hwnd = new_window['hwnd']
            new_size = new_window.get('size')
            if expected_size and new_size and tuple(new_size) != tuple(expected_size):
                logger.info(f"[{thumbnail_id}] Reconnected with size change: "
                            f"{list(expected_size)} -> {list(new_size)}")
            logger.info(f"[{thumbnail_id}] Reconnected: "
                        f"new hwnd={new_hwnd}, size={new_size}")

            # Update config with new handle and refreshed metadata
            metadata = self.window_manager.get_window_metadata(new_hwnd)
            updates = {"window_hwnd": new_hwnd}
            if metadata:
                updates["window_class"] = metadata.get('class', '')
                updates["window_size"] = list(metadata.get('size', []))
                updates["monitor_id"] = metadata.get('monitor_id')
            
            with self.lock:
                self.config.update_thumbnail(thumbnail_id, updates)

            # Scale regions if the window size changed
            if expected_size and new_size and tuple(new_size) != tuple(expected_size):
                self.scale_regions_for_new_size(
                    thumbnail_id, tuple(expected_size), tuple(new_size))

            self.config.save()

            return new_window

        logger.warning(f"[{thumbnail_id}] Reconnection failed for '{window_title}'")
        return None
    
    def _main_loop(self) -> None:
        """Main unified capture and processing loop"""
        # Track previous state per region to fire callbacks only on transitions
        _prev_region_state: dict[str, str] = {}
        last_refresh_rate_ms: Optional[int] = None

        while self.running:
            try:
                start_time = time.time()
                refresh_rate_ms = self.config.get_refresh_rate()

                if refresh_rate_ms != last_refresh_rate_ms:
                    self.cache_manager.lifetime = max(0.01, (refresh_rate_ms - 10) / 1000.0)
                    self.cache_manager.invalidate_all()
                    last_refresh_rate_ms = refresh_rate_ms
                    logger.info(
                        "Updated refresh rate to %sms (cache lifetime=%.3fs)",
                        refresh_rate_ms,
                        self.cache_manager.lifetime,
                    )
                
                # Get snapshot of all thumbnails (copy to avoid mutation during iteration)
                with self.lock:
                    thumbnails = list(self.config.get_all_thumbnails())

                # Fallback foreground sync (event hooks can occasionally miss transitions).
                now = time.time()
                if (now - self._last_foreground_sync_ts) >= 0.25:
                    foreground_hwnd = self.window_manager.get_foreground_window()
                    if foreground_hwnd:
                        self._update_overlay_active_by_foreground_source(thumbnails, foreground_hwnd)
                    self._last_foreground_sync_ts = now

                # Process each thumbnail
                for thumbnail_config in thumbnails:
                    if not thumbnail_config.get("enabled", True):
                        continue
                    
                    thumbnail_id = thumbnail_config["id"]
                    window_hwnd = thumbnail_config["window_hwnd"]
                    window_title, expected_class, expected_size, expected_monitor = \
                        self._extract_window_identity(thumbnail_config)

                    # Validate window: both existence AND identity
                    window_ok = self._validate_thumbnail_window(thumbnail_config, window_hwnd)

                    if window_ok:
                        was_disconnected = not self._thumbnail_connected.get(thumbnail_id, False)
                        self._reconnect_attempted_once.discard(thumbnail_id)
                        self._window_lost_notified.discard(thumbnail_id)
                        self._thumbnail_connected[thumbnail_id] = True
                        # If just transitioned from disconnected, show the overlay
                        if was_disconnected:
                            self.renderer.set_thumbnail_availability(thumbnail_id, True)
                            if self.config.get_show_overlay_on_connect():
                                self.renderer.set_thumbnail_user_visibility(thumbnail_id, True)

                    if not window_ok:
                        self._thumbnail_connected[thumbnail_id] = False
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
                            self._mark_connected(thumbnail_id, window_hwnd, update_config=False)
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
                            logger.debug(f"[{thumbnail_id}] CAPTURED: size {window_image.size}")
                        else:
                            # Capture failed but DWM overlay is independent — don't
                            # hide the overlay, just skip region monitoring this cycle.
                            logger.debug(f"[{thumbnail_id}] CAPTURE FAILED (skipping regions): hwnd={window_hwnd}")
                            continue
                    else:
                        window_image = cached_image
                        logger.debug(f"[{thumbnail_id}] Using cached image: {window_image.size}")
                    self._diag_capture_ms += (time.perf_counter() - capture_start) * 1000.0

                    # DWM handles thumbnail display; no image sent to renderer.
                    # Ensure DWM link is established for this hwnd.
                    self.renderer.set_source_hwnd(thumbnail_id, window_hwnd)

                    # Process monitoring regions (uses captured image for analysis)
                    if not self.paused:
                        monitor_start = time.perf_counter()
                        alert_hold_seconds = self.config.get_alert_hold_seconds()
                        region_results = self.monitoring_engine.update_regions(
                            thumbnail_id, window_image, alert_hold_seconds,
                        )
                        self._diag_monitor_ms += (time.perf_counter() - monitor_start) * 1000.0
                        # Store window image for next iteration's diagnostics
                        self._prev_window_images[thumbnail_id] = window_image
                        
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

                                    # Optional: save diagnostic images (background thread to avoid blocking loop)
                                    if self.config.get_save_alert_diagnostics():
                                        threading.Thread(
                                            target=save_alert_diagnostics,
                                            args=(
                                                self.config.get_capture_dir(),
                                                thumbnail_config.copy(),
                                                config.copy(),
                                                window_image.copy(),
                                                region,
                                                self._prev_window_images.get(thumbnail_id),
                                                self.config.get_canny_low(),
                                                self.config.get_canny_high(),
                                                self.config.get_edge_binarize(),
                                            ),
                                            daemon=True,
                                        ).start()

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

    def _update_overlay_active_by_foreground_source(self, thumbnails: List[Dict], foreground_hwnd: int) -> None:
        """Highlight overlay whose monitored source window is currently foreground."""
        try:
            if not foreground_hwnd:
                return

            foreground_family = self.window_manager.get_window_handle_family(foreground_hwnd)
            if not foreground_family:
                foreground_family = {int(foreground_hwnd)}

            active_thumbnail_id: Optional[str] = None
            for thumbnail in thumbnails:
                if not thumbnail.get("enabled", True):
                    continue
                thumbnail_id = thumbnail.get("id")
                hwnd = thumbnail.get("window_hwnd")
                if not thumbnail_id or not hwnd:
                    continue

                source_family = self.window_manager.get_window_handle_family(int(hwnd))
                if not source_family:
                    source_family = {int(hwnd)}

                if source_family.intersection(foreground_family):
                    active_thumbnail_id = thumbnail_id
                    break

            if active_thumbnail_id:
                self.renderer.set_active_thumbnail(active_thumbnail_id, bring_to_front=False)
            else:
                self.renderer.clear_active_thumbnail()
        except Exception as error:
            logger.debug(f"Unable to update active overlay from foreground source: {error}")

    def _start_foreground_event_hook(self) -> None:
        """Start Windows foreground window event hook (EVENT_SYSTEM_FOREGROUND)."""
        if os.name != "nt":
            return
        if self.foreground_hook_thread and self.foreground_hook_thread.is_alive():
            return

        self.foreground_hook_thread = threading.Thread(
            target=self._foreground_event_hook_loop,
            daemon=True,
            name="foreground-event-hook",
        )
        self.foreground_hook_thread.start()

    def _stop_foreground_event_hook(self) -> None:
        """Stop foreground event hook thread and unhook Windows event."""
        if os.name != "nt":
            return

        try:
            if self._foreground_hook_thread_id:
                ctypes.windll.user32.PostThreadMessageW(self._foreground_hook_thread_id, 0x0012, 0, 0)
        except Exception as error:
            logger.debug(f"Unable to post WM_QUIT to foreground hook thread: {error}")

        if self.foreground_hook_thread:
            try:
                self.foreground_hook_thread.join(timeout=2.0)
            except Exception as error:
                logger.debug(f"Unable to join foreground hook thread: {error}")

        self.foreground_hook_thread = None
        self._foreground_hook_thread_id = None
        self._foreground_event_proc = None
        self._foreground_event_hook_handle = None

    def _foreground_event_hook_loop(self) -> None:
        """Windows message loop for foreground-change events."""
        if os.name != "nt":
            return

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._foreground_hook_thread_id = int(kernel32.GetCurrentThreadId())

            EVENT_SYSTEM_FOREGROUND = 0x0003
            WINEVENT_OUTOFCONTEXT = 0x0000
            WINEVENT_SKIPOWNPROCESS = 0x0002

            WinEventProcType = ctypes.WINFUNCTYPE(
                None,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_long,
                ctypes.c_long,
                ctypes.c_uint,
                ctypes.c_uint,
            )

            def _win_event_callback(_hook, _event, hwnd, _id_object, _id_child, _event_thread, _event_time):
                try:
                    if not hwnd:
                        return
                    foreground_hwnd = int(hwnd)
                    with self.lock:
                        thumbnails = list(self.config.get_all_thumbnails())
                    self._update_overlay_active_by_foreground_source(thumbnails, foreground_hwnd)
                except Exception as callback_error:
                    logger.debug(f"Foreground hook callback error: {callback_error}")

            self._foreground_event_proc = WinEventProcType(_win_event_callback)

            self._foreground_event_hook_handle = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND,
                EVENT_SYSTEM_FOREGROUND,
                0,
                self._foreground_event_proc,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )

            if not self._foreground_event_hook_handle:
                logger.warning("Failed to install foreground event hook")
                return

            msg = ctypes.wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as error:
            logger.warning(f"Foreground event hook loop failed: {error}")
        finally:
            try:
                if self._foreground_event_hook_handle:
                    ctypes.windll.user32.UnhookWinEvent(self._foreground_event_hook_handle)
            except Exception:
                pass

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
    
    def _on_thumbnail_interaction(self, thumbnail_id: str, action: str, payload: Optional[Dict] = None) -> None:
        """Handle thumbnail user interactions"""
        payload = payload or {}
        logger.debug(f"Thumbnail {thumbnail_id} action: {action} payload={payload}")
        
        if action == "activated":
            # Bring corresponding window to front
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            if thumbnail:
                hwnd = thumbnail["window_hwnd"]
                self.window_manager.activate_window(hwnd)

        elif action == "overlay_closed":
            # User closed overlay window: hide overlay only, keep monitoring active.
            with self.lock:
                self.config.update_thumbnail(thumbnail_id, {"overlay_visible": False})
            self.config.save()
            self.renderer.set_thumbnail_user_visibility(thumbnail_id, False)

        elif action == "position_changed":
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            if not thumbnail:
                return
            position = thumbnail.get("position", {})
            monitor = position.get("monitor", 0)
            x = int(payload.get("x", position.get("x", 0)))
            y = int(payload.get("y", position.get("y", 0)))
            with self.lock:
                self.config.update_thumbnail_position(thumbnail_id, x, y, monitor)
            self.config.save()

        elif action == "size_changed":
            thumbnail = self.config.get_thumbnail(thumbnail_id)
            if not thumbnail:
                return
            size = thumbnail.get("size", {})
            width = int(payload.get("width", size.get("width", 320)))
            height = int(payload.get("height", size.get("height", 240)))
            with self.lock:
                self.config.update_thumbnail_size(thumbnail_id, width, height)
            self.config.save()

        elif action == "bulk_geometry_changed":
            geometries = payload.get("geometries", {})
            if not isinstance(geometries, dict) or not geometries:
                return
            with self.lock:
                for target_id, geometry in geometries.items():
                    if not isinstance(geometry, dict):
                        continue
                    thumbnail = self.config.get_thumbnail(target_id)
                    if not thumbnail:
                        continue
                    position = thumbnail.get("position", {})
                    monitor = position.get("monitor", 0)
                    x = int(geometry.get("x", position.get("x", 0)))
                    y = int(geometry.get("y", position.get("y", 0)))
                    width = int(geometry.get("width", thumbnail.get("size", {}).get("width", 320)))
                    height = int(geometry.get("height", thumbnail.get("size", {}).get("height", 240)))
                    self.config.update_thumbnail_position(target_id, x, y, monitor)
                    self.config.update_thumbnail_size(target_id, width, height)
            self.config.save()
    
    def is_running(self) -> bool:
        """Check if engine is running"""
        return self.running
