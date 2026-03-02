"""Configuration management for ScreenAlert"""

import json
import logging
import os
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path

from screenalert_core.utils.constants import (
    CONFIG_FILE, CONFIG_DIR, DEFAULT_REFRESH_RATE_MS, DEFAULT_OPACITY,
    DEFAULT_ALERT_THRESHOLD, THUMBNAIL_DEFAULT_WIDTH, THUMBNAIL_DEFAULT_HEIGHT
)
from screenalert_core.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages ScreenAlert configuration with new schema"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager
        
        Args:
            config_path: Path to config file (default: standard location)
        """
        self.config_path = config_path or CONFIG_FILE
        self._config = self._load_or_create_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure"""
        return {
            "version": "2.0.0",
            "app": {
                "refresh_rate_ms": DEFAULT_REFRESH_RATE_MS,
                "opacity": DEFAULT_OPACITY,
                "always_on_top": True,
                "show_overlay_when_unavailable": False,
                "log_verbose": False,
                "high_contrast": False,
                "last_window_filter": "",
                "last_window_size_filter_op": "==",
                "last_window_size_filter_value": "",
                "default_alert_threshold": DEFAULT_ALERT_THRESHOLD,
                "change_detection_method": "ssim",
                "alert_hold_seconds": 10,
                "enable_sound": False,
                "enable_tts": True,
                "default_sound_file": "",
                "default_tts_message": "Alert {window} {region_name}",
                "mute_until_ts": 0,
                "pause_reminder_interval_sec": 60,
                "capture_on_alert": False,
                "capture_on_green": False,
                "capture_dir": os.path.join(CONFIG_DIR, "captures"),
                "capture_filename_format": "{timestamp}_{window}_{region}_{status}.png",
                "anonymize_logs": False,
                "suppress_fullscreen": False,
                "update_check_enabled": False,
                "headless": False,
                "diagnostics_enabled": False,
            },
            "thumbnails": [],
            "ui": {
                "main_window_geometry": "1200x800+100+100",
                "settings_expanded": False,
            },
            "plugins": {
                "hooks": {}
            },
            "history": {
                "alerts": []
            }
        }

    def _get_legacy_paths(self) -> List[str]:
        """Known legacy locations for config migration."""
        home = str(Path.home())
        return [
            os.path.join(home, "screenalert_config.json"),
            os.path.join(os.getcwd(), "screenalert_config.json"),
            os.path.join(home, ".screenalert", "screenalert_config.json"),
        ]

    def _try_migrate_legacy_config(self) -> bool:
        """Attempt to migrate config from legacy locations into current config path."""
        try:
            if os.path.exists(self.config_path):
                return True
            for legacy in self._get_legacy_paths():
                if os.path.exists(legacy):
                    os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                    shutil.copy2(legacy, self.config_path)
                    logger.info(f"Migrated legacy config from {legacy} to {self.config_path}")
                    return True
        except Exception as e:
            logger.warning(f"Legacy config migration failed: {e}")
        return False
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load config from file or create default"""
        try:
            if os.path.exists(self.config_path):
                logger.info(f"Loading config from {self.config_path}")
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                logger.info(f"Config file not found, creating default at {self.config_path}")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return self._get_default_config()
    
    def _merge_configs(self, defaults: Dict, loaded: Dict) -> Dict:
        """Merge loaded config with defaults, preserving user settings"""
        result = defaults.copy()
        if not loaded:
            return result
        
        # Merge app settings
        if "app" in loaded and isinstance(loaded["app"], dict):
            result["app"].update(loaded["app"])
        
        # Keep user's thumbnails
        if "thumbnails" in loaded and isinstance(loaded["thumbnails"], list):
            result["thumbnails"] = loaded["thumbnails"]
        
        # Merge UI settings
        if "ui" in loaded and isinstance(loaded["ui"], dict):
            result["ui"].update(loaded["ui"])
        
        return result
    
    def save(self) -> bool:
        """Save current config to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    # App settings
    def get_refresh_rate(self) -> int:
        """Get refresh rate in milliseconds"""
        return self._config.get("app", {}).get("refresh_rate_ms", DEFAULT_REFRESH_RATE_MS)
    
    def set_refresh_rate(self, ms: int) -> None:
        """Set refresh rate in milliseconds"""
        self._config["app"]["refresh_rate_ms"] = max(300, min(ms, 5000))  # Clamp 300-5000ms
    
    def get_opacity(self) -> float:
        """Get default thumbnail opacity (0.0-1.0)"""
        return self._config.get("app", {}).get("opacity", DEFAULT_OPACITY)
    
    def set_opacity(self, opacity: float) -> None:
        """Set default thumbnail opacity"""
        self._config["app"]["opacity"] = max(0.2, min(opacity, 1.0))
    
    def get_always_on_top(self) -> bool:
        """Get whether thumbnails should stay on top"""
        return self._config.get("app", {}).get("always_on_top", True)
    
    def set_always_on_top(self, on_top: bool) -> None:
        """Set whether thumbnails should stay on top"""
        self._config["app"]["always_on_top"] = on_top

    def get_show_overlay_when_unavailable(self) -> bool:
        """Get whether overlays should remain visible when source window is unavailable."""
        return bool(self._config.get("app", {}).get("show_overlay_when_unavailable", False))

    def set_show_overlay_when_unavailable(self, enabled: bool) -> None:
        """Set whether overlays remain visible with a Not Available placeholder."""
        self._config["app"]["show_overlay_when_unavailable"] = bool(enabled)
    
    def get_verbose_logging(self) -> bool:
        """Get verbose logging setting"""
        return self._config.get("app", {}).get("log_verbose", False)
    
    def set_verbose_logging(self, verbose: bool) -> None:
        """Set verbose logging"""
        self._config["app"]["log_verbose"] = verbose

    def get_high_contrast(self) -> bool:
        """Get high contrast mode setting."""
        return bool(self._config.get("app", {}).get("high_contrast", False))

    def set_high_contrast(self, enabled: bool) -> None:
        """Set high contrast mode setting."""
        self._config["app"]["high_contrast"] = bool(enabled)

    def get_default_alert_threshold(self) -> float:
        return float(self._config.get("app", {}).get("default_alert_threshold", DEFAULT_ALERT_THRESHOLD))

    def set_default_alert_threshold(self, threshold: float) -> None:
        self._config["app"]["default_alert_threshold"] = max(0.1, min(float(threshold), 1.0))

    def get_change_detection_method(self) -> str:
        method = self._config.get("app", {}).get("change_detection_method", "ssim")
        return method if method in ("ssim", "phash") else "ssim"

    def set_change_detection_method(self, method: str) -> None:
        self._config["app"]["change_detection_method"] = method if method in ("ssim", "phash") else "ssim"

    def get_alert_hold_seconds(self) -> int:
        return int(self._config.get("app", {}).get("alert_hold_seconds", 10))

    def set_alert_hold_seconds(self, seconds: int) -> None:
        self._config["app"]["alert_hold_seconds"] = max(1, min(int(seconds), 120))

    def get_enable_sound(self) -> bool:
        return bool(self._config.get("app", {}).get("enable_sound", False))

    def set_enable_sound(self, enabled: bool) -> None:
        self._config["app"]["enable_sound"] = bool(enabled)

    def get_enable_tts(self) -> bool:
        return bool(self._config.get("app", {}).get("enable_tts", True))

    def set_enable_tts(self, enabled: bool) -> None:
        self._config["app"]["enable_tts"] = bool(enabled)

    def get_default_sound_file(self) -> str:
        return self._config.get("app", {}).get("default_sound_file", "")

    def set_default_sound_file(self, path: str) -> None:
        self._config["app"]["default_sound_file"] = path or ""

    def get_default_tts_message(self) -> str:
        return self._config.get("app", {}).get("default_tts_message", "Alert {window} {region_name}")

    def set_default_tts_message(self, message: str) -> None:
        self._config["app"]["default_tts_message"] = message or "Alert {window} {region_name}"

    def get_mute_until_ts(self) -> int:
        return int(self._config.get("app", {}).get("mute_until_ts", 0))

    def set_mute_until_ts(self, timestamp: int) -> None:
        self._config["app"]["mute_until_ts"] = max(0, int(timestamp))

    def get_pause_reminder_interval_sec(self) -> int:
        return int(self._config.get("app", {}).get("pause_reminder_interval_sec", 60))

    def set_pause_reminder_interval_sec(self, seconds: int) -> None:
        self._config["app"]["pause_reminder_interval_sec"] = max(10, min(int(seconds), 3600))

    def get_capture_on_alert(self) -> bool:
        return bool(self._config.get("app", {}).get("capture_on_alert", False))

    def set_capture_on_alert(self, enabled: bool) -> None:
        self._config["app"]["capture_on_alert"] = bool(enabled)

    def get_capture_on_green(self) -> bool:
        return bool(self._config.get("app", {}).get("capture_on_green", False))

    def set_capture_on_green(self, enabled: bool) -> None:
        self._config["app"]["capture_on_green"] = bool(enabled)

    def get_capture_dir(self) -> str:
        return self._config.get("app", {}).get("capture_dir", os.path.join(CONFIG_DIR, "captures"))

    def set_capture_dir(self, path: str) -> None:
        self._config["app"]["capture_dir"] = path or os.path.join(CONFIG_DIR, "captures")

    def get_capture_filename_format(self) -> str:
        return self._config.get("app", {}).get("capture_filename_format", "{timestamp}_{window}_{region}_{status}.png")

    def set_capture_filename_format(self, pattern: str) -> None:
        self._config["app"]["capture_filename_format"] = pattern or "{timestamp}_{window}_{region}_{status}.png"

    def get_anonymize_logs(self) -> bool:
        return bool(self._config.get("app", {}).get("anonymize_logs", False))

    def set_anonymize_logs(self, enabled: bool) -> None:
        self._config["app"]["anonymize_logs"] = bool(enabled)

    def get_suppress_fullscreen(self) -> bool:
        return bool(self._config.get("app", {}).get("suppress_fullscreen", False))

    def set_suppress_fullscreen(self, enabled: bool) -> None:
        self._config["app"]["suppress_fullscreen"] = bool(enabled)

    def get_update_check_enabled(self) -> bool:
        return bool(self._config.get("app", {}).get("update_check_enabled", False))

    def set_update_check_enabled(self, enabled: bool) -> None:
        self._config["app"]["update_check_enabled"] = bool(enabled)

    def get_diagnostics_enabled(self) -> bool:
        return bool(self._config.get("app", {}).get("diagnostics_enabled", False))

    def set_diagnostics_enabled(self, enabled: bool) -> None:
        self._config["app"]["diagnostics_enabled"] = bool(enabled)

    def get_headless(self) -> bool:
        return bool(self._config.get("app", {}).get("headless", False))

    def set_headless(self, enabled: bool) -> None:
        self._config["app"]["headless"] = bool(enabled)
    
    def get_last_window_filter(self) -> str:
        """Get last used window filter"""
        return self._config.get("app", {}).get("last_window_filter", "")
    
    def set_last_window_filter(self, filter_text: str) -> None:
        """Set last used window filter"""
        self._config["app"]["last_window_filter"] = filter_text

    def get_last_window_size_filter_op(self) -> str:
        """Get last used size filter operator."""
        value = self._config.get("app", {}).get("last_window_size_filter_op", "==")
        return value if value in ("==", "<=", ">=") else "=="

    def set_last_window_size_filter_op(self, op: str) -> None:
        """Set last used size filter operator."""
        self._config["app"]["last_window_size_filter_op"] = op if op in ("==", "<=", ">=") else "=="

    def get_last_window_size_filter_value(self) -> str:
        """Get last used size filter value text."""
        return self._config.get("app", {}).get("last_window_size_filter_value", "")

    def set_last_window_size_filter_value(self, value: str) -> None:
        """Set last used size filter value text."""
        self._config["app"]["last_window_size_filter_value"] = value or ""
    
    # Thumbnail management
    def add_thumbnail(self, window_title: str, window_hwnd: int, 
                     position: Dict = None, size: Dict = None,
                     window_class: str = None, window_size: tuple = None,
                     monitor_id: int = None) -> str:
        """Add a new thumbnail configuration
        
        Args:
            window_title: Title of the monitored window
            window_hwnd: Handle of the monitored window
            position: Thumbnail display position
            size: Thumbnail display size
            window_class: Window class name (for identity validation)
            window_size: Actual window dimensions (width, height)
            monitor_id: Monitor index the window is on
        
        Returns:
            Thumbnail ID
        """
        thumbnail_id = generate_uuid()
        
        position = position or {"x": 0, "y": 0, "monitor": 0}
        size = size or {"width": THUMBNAIL_DEFAULT_WIDTH, "height": THUMBNAIL_DEFAULT_HEIGHT}
        
        thumbnail = {
            "id": thumbnail_id,
            "window_title": window_title,
            "window_hwnd": window_hwnd,
            "window_class": window_class or "",
            "window_size": list(window_size) if window_size else None,
            "monitor_id": monitor_id,
            "position": position,
            "size": size,
            "opacity": DEFAULT_OPACITY,
            "show_border": True,
            "enabled": True,
            "monitored_regions": []
        }
        
        self._config["thumbnails"].append(thumbnail)
        logger.info(f"Added thumbnail: {window_title} (ID: {thumbnail_id})")
        return thumbnail_id
    
    def get_thumbnail(self, thumbnail_id: str) -> Optional[Dict]:
        """Get thumbnail configuration by ID"""
        for thumb in self._config["thumbnails"]:
            if thumb["id"] == thumbnail_id:
                return thumb
        return None
    
    def get_all_thumbnails(self) -> List[Dict]:
        """Get all thumbnails"""
        return self._config.get("thumbnails", [])
    
    def update_thumbnail(self, thumbnail_id: str, updates: Dict) -> bool:
        """Update thumbnail configuration"""
        thumbnail = self.get_thumbnail(thumbnail_id)
        if not thumbnail:
            logger.warning(f"Thumbnail not found: {thumbnail_id}")
            return False
        
        thumbnail.update(updates)
        logger.info(f"Updated thumbnail: {thumbnail_id}")
        return True
    
    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        """Remove a thumbnail"""
        self._config["thumbnails"] = [
            t for t in self._config["thumbnails"] if t["id"] != thumbnail_id
        ]
        logger.info(f"Removed thumbnail: {thumbnail_id}")
        return True
    
    def update_thumbnail_position(self, thumbnail_id: str, x: int, y: int, monitor: int = 0) -> bool:
        """Update thumbnail position"""
        return self.update_thumbnail(thumbnail_id, {
            "position": {"x": x, "y": y, "monitor": monitor}
        })
    
    def update_thumbnail_size(self, thumbnail_id: str, width: int, height: int) -> bool:
        """Update thumbnail size"""
        return self.update_thumbnail(thumbnail_id, {
            "size": {"width": width, "height": height}
        })
    
    def add_region_to_thumbnail(self, thumbnail_id: str, region: Dict) -> Optional[str]:
        """Add monitoring region to thumbnail
        
        Region format:
        {
            "name": "Region Name",
            "rect": [x, y, width, height],
            "alert_threshold": 0.99,
            "sound_file": "path/to/sound.wav",
            "tts_message": "Alert!",
            "enabled": True
        }
        """
        thumbnail = self.get_thumbnail(thumbnail_id)
        if not thumbnail:
            logger.warning(f"Thumbnail not found: {thumbnail_id}")
            return None
        
        region_id = generate_uuid()
        region["id"] = region_id
        region.setdefault("alert_threshold", DEFAULT_ALERT_THRESHOLD)
        region.setdefault("enabled", True)
        region.setdefault("sound_file", "")
        region.setdefault("tts_message", self.get_default_tts_message())
        
        thumbnail["monitored_regions"].append(region)
        logger.info(f"Added region to thumbnail {thumbnail_id}: {region.get('name', region_id)}")
        return region_id
    
    def get_region(self, thumbnail_id: str, region_id: str) -> Optional[Dict]:
        """Get specific region"""
        thumbnail = self.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return None
        
        for region in thumbnail.get("monitored_regions", []):
            if region.get("id") == region_id:
                return region
        return None
    
    def update_region(self, thumbnail_id: str, region_id: str, updates: Dict) -> bool:
        """Update region configuration"""
        region = self.get_region(thumbnail_id, region_id)
        if not region:
            logger.warning(f"Region not found: {region_id}")
            return False
        
        region.update(updates)
        logger.info(f"Updated region {region_id}")
        return True
    
    def remove_region(self, thumbnail_id: str, region_id: str) -> bool:
        """Remove monitoring region"""
        thumbnail = self.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return False
        
        thumbnail["monitored_regions"] = [
            r for r in thumbnail["monitored_regions"] if r.get("id") != region_id
        ]
        logger.info(f"Removed region: {region_id}")
        return True
    
    # UI state
    def get_main_window_geometry(self) -> str:
        """Get saved main window geometry"""
        return self._config.get("ui", {}).get("main_window_geometry", "1200x800+100+100")
    
    def set_main_window_geometry(self, geometry: str) -> None:
        """Save main window geometry"""
        self._config["ui"]["main_window_geometry"] = geometry

    def export_config(self, export_path: str) -> bool:
        """Export current config to a specified path."""
        try:
            with open(export_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting config to {export_path}: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """Import config from a file path and merge with defaults."""
        try:
            with open(import_path, 'r') as f:
                imported = json.load(f)
            defaults = self._get_default_config()
            self._config = self._merge_configs(defaults, imported)
            return self.save()
        except Exception as e:
            logger.error(f"Error importing config from {import_path}: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Reset all configuration to defaults and persist."""
        self._config = self._get_default_config()
        return self.save()

    def add_alert_history(self, item: Dict[str, Any], max_items: int = 200) -> None:
        """Append alert event history and keep bounded size."""
        history = self._config.setdefault("history", {}).setdefault("alerts", [])
        history.append(item)
        if len(history) > max_items:
            self._config["history"]["alerts"] = history[-max_items:]

    def get_alert_history(self) -> List[Dict[str, Any]]:
        """Get alert history list."""
        return list(self._config.get("history", {}).get("alerts", []))
