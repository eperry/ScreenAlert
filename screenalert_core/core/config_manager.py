"""Configuration management for ScreenAlert"""

import json
import logging
import os
from typing import Dict, Any, Optional, List

from screenalert_core.utils.constants import (
    CONFIG_FILE, WINDOW_REGION_CONFIG_FILE, CONFIG_DIR, DEFAULT_REFRESH_RATE_MS, DEFAULT_OPACITY,
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
        self.window_region_config_path = self._derive_window_region_config_path(self.config_path)
        self._config = self._load_or_create_config()

    def _derive_window_region_config_path(self, app_config_path: str) -> str:
        """Derive window/region data config path from app config path."""
        if os.path.abspath(app_config_path) == os.path.abspath(CONFIG_FILE):
            return WINDOW_REGION_CONFIG_FILE

        base_dir = os.path.dirname(app_config_path) or CONFIG_DIR
        base_name = os.path.splitext(os.path.basename(app_config_path))[0]
        return os.path.join(base_dir, f"{base_name}_windows_regions.json")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure"""
        return {
            "version": "2.0.2",
            "app": {
                "refresh_rate_ms": DEFAULT_REFRESH_RATE_MS,
                "opacity": DEFAULT_OPACITY,
                "always_on_top": True,
                "show_borders": True,
                "show_overlay_when_unavailable": False,
                "log_verbose": False,
                "high_contrast": False,
                "last_window_filter": "",
                "last_window_size_filter_op": "==",
                "last_window_size_filter_value": "",
                "default_alert_threshold": DEFAULT_ALERT_THRESHOLD,
                "change_detection_method": "ssim",
                "min_edge_fraction": 0.003,
                "canny_low": 40,
                "canny_high": 120,
                "edge_binarize": False,
                "bg_history": 500,
                "bg_var_threshold": 16.0,
                "bg_learning_rate": -1.0,
                "bg_warmup_frames": 30,
                "bg_min_fg_fraction": 0.003,
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
                "save_alert_diagnostics": False,
                "reconnect_size_tolerance": 20,
                "prompt_on_reconnect_fail": True,
            },
            "thumbnails": [],
            "ui": {
                "main_window_geometry": "1200x800+100+100",
                "settings_expanded": False,
                "theme_preset": "default",
            },
            "plugins": {
                "hooks": {}
            },
            "history": {
                "alerts": []
            }
        }

    def _load_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load JSON file safely and return dict payload or None."""
        try:
            if not os.path.exists(file_path):
                return None
            with open(file_path, 'r') as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
            logger.warning(f"Invalid JSON root (expected object) in {file_path}")
        except Exception as e:
            logger.error(f"Error loading config file {file_path}: {e}")
        return None

    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load split config files (app/ui + windows/regions) or use defaults."""
        result = self._get_default_config()

        app_loaded = self._load_json_file(self.config_path)
        if app_loaded:
            if "version" in app_loaded:
                result["version"] = app_loaded["version"]
            if isinstance(app_loaded.get("app"), dict):
                result["app"].update(app_loaded["app"])
            if isinstance(app_loaded.get("ui"), dict):
                result["ui"].update(app_loaded["ui"])
            if isinstance(app_loaded.get("plugins"), dict):
                result["plugins"].update(app_loaded["plugins"])
            if isinstance(app_loaded.get("history"), dict):
                result["history"].update(app_loaded["history"])
            logger.info(f"Loaded app/UI config from {self.config_path}")
        else:
            logger.info(f"App/UI config not found, using defaults at {self.config_path}")

        data_loaded = self._load_json_file(self.window_region_config_path)
        if data_loaded and isinstance(data_loaded.get("thumbnails"), list):
            # Normalize and dedupe thumbnails by window title (case-insensitive, trimmed)
            seen = set()
            deduped = []
            for thumb in data_loaded["thumbnails"]:
                title = str(thumb.get("window_title", "") or "").strip().lower()
                if not title:
                    deduped.append(thumb)
                    continue
                if title in seen:
                    logger.warning(f"Duplicate thumbnail title in config ignored: {thumb.get('window_title')} (id={thumb.get('id')})")
                    continue
                seen.add(title)
                deduped.append(thumb)

            result["thumbnails"] = deduped
            logger.info(f"Loaded window/region config from {self.window_region_config_path}")
        else:
            logger.info(f"Window/region config not found, using defaults at {self.window_region_config_path}")

        return result
    
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
        """Save split config files (app/UI and windows/regions)."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            os.makedirs(os.path.dirname(self.window_region_config_path), exist_ok=True)

            app_payload = {
                "version": self._config.get("version", "2.0.2"),
                "app": self._config.get("app", {}),
                "ui": self._config.get("ui", {}),
                "plugins": self._config.get("plugins", {}),
                "history": self._config.get("history", {}),
            }
            data_payload = {
                "version": self._config.get("version", "2.0.2"),
                "thumbnails": self._config.get("thumbnails", []),
            }

            with open(self.config_path, 'w') as f:
                json.dump(app_payload, f, indent=2)
            with open(self.window_region_config_path, 'w') as f:
                json.dump(data_payload, f, indent=2)

            logger.info(
                f"Config saved to app/ui={self.config_path} and windows/regions={self.window_region_config_path}"
            )
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

    def get_show_borders(self) -> bool:
        """Get whether overlay borders are shown for thumbnails."""
        return bool(self._config.get("app", {}).get("show_borders", True))

    def set_show_borders(self, enabled: bool) -> None:
        """Set whether overlay borders are shown and persist to thumbnail configs."""
        value = bool(enabled)
        self._config["app"]["show_borders"] = value
        for thumbnail in self._config.get("thumbnails", []):
            thumbnail["show_border"] = value

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
        ui_preset = str(self._config.get("ui", {}).get("theme_preset", "") or "").strip().lower()
        if ui_preset == "high-contrast":
            return True
        return bool(self._config.get("app", {}).get("high_contrast", False))

    def set_high_contrast(self, enabled: bool) -> None:
        """Set high contrast mode setting."""
        value = bool(enabled)
        self._config["app"]["high_contrast"] = value
        if value:
            self._config.setdefault("ui", {})["theme_preset"] = "high-contrast"
        else:
            current = str(self._config.get("ui", {}).get("theme_preset", "default") or "default").strip().lower()
            if current == "high-contrast":
                self._config.setdefault("ui", {})["theme_preset"] = "default"

    def get_region_state_filters(self) -> dict:
        """Return persisted region state filter map (state -> bool).

        Defaults to showing all states when not present in config.
        """
        ui = self._config.get("ui", {})
        defaults = {
            "alert": True,
            "warning": True,
            "paused": True,
            "ok": True,
            "disabled": True,
            "unavailable": True,
        }
        stored = ui.get("region_state_filters")
        if not isinstance(stored, dict):
            return defaults
        # Merge stored values with defaults to ensure keys exist
        result = defaults.copy()
        for k, v in stored.items():
            result[str(k)] = bool(v)
        return result

    def set_region_state_filters(self, mapping: dict) -> None:
        """Persist the mapping of region state -> visible (bool) into UI config."""
        safe_map = {}
        for k, v in (mapping or {}).items():
            safe_map[str(k)] = bool(v)
        self._config.setdefault("ui", {})["region_state_filters"] = safe_map

    def get_default_alert_threshold(self) -> float:
        return float(self._config.get("app", {}).get("default_alert_threshold", DEFAULT_ALERT_THRESHOLD))

    def set_default_alert_threshold(self, threshold: float) -> None:
        self._config["app"]["default_alert_threshold"] = max(0.1, min(float(threshold), 1.0))

    def get_change_detection_method(self) -> str:
        method = self._config.get("app", {}).get("change_detection_method", "ssim")
        return method if method in ("ssim", "phash", "edge_only", "background_subtraction") else "ssim"

    def set_change_detection_method(self, method: str) -> None:
        self._config["app"]["change_detection_method"] = method if method in ("ssim", "phash", "edge_only", "background_subtraction") else "ssim"

    def get_min_edge_fraction(self) -> float:
        return float(self._config.get("app", {}).get("min_edge_fraction", 0.003))

    def set_min_edge_fraction(self, value: float) -> None:
        self._config["app"]["min_edge_fraction"] = max(0.0, min(float(value), 1.0))

    def get_canny_low(self) -> int:
        return int(self._config.get("app", {}).get("canny_low", 40))

    def set_canny_low(self, value: int) -> None:
        self._config["app"]["canny_low"] = max(1, min(int(value), 500))

    def get_canny_high(self) -> int:
        return int(self._config.get("app", {}).get("canny_high", 120))

    def set_canny_high(self, value: int) -> None:
        self._config["app"]["canny_high"] = max(1, min(int(value), 500))

    def get_edge_binarize(self) -> bool:
        return bool(self._config.get("app", {}).get("edge_binarize", False))

    def set_edge_binarize(self, enabled: bool) -> None:
        self._config["app"]["edge_binarize"] = bool(enabled)

    def get_bg_history(self) -> int:
        return int(self._config.get("app", {}).get("bg_history", 500))

    def set_bg_history(self, value: int) -> None:
        self._config["app"]["bg_history"] = max(10, min(int(value), 5000))

    def get_bg_var_threshold(self) -> float:
        return float(self._config.get("app", {}).get("bg_var_threshold", 16.0))

    def set_bg_var_threshold(self, value: float) -> None:
        self._config["app"]["bg_var_threshold"] = max(1.0, min(float(value), 100.0))

    def get_bg_learning_rate(self) -> float:
        return float(self._config.get("app", {}).get("bg_learning_rate", -1.0))

    def set_bg_learning_rate(self, value: float) -> None:
        self._config["app"]["bg_learning_rate"] = max(-1.0, min(float(value), 1.0))

    def get_bg_warmup_frames(self) -> int:
        return int(self._config.get("app", {}).get("bg_warmup_frames", 30))

    def set_bg_warmup_frames(self, value: int) -> None:
        self._config["app"]["bg_warmup_frames"] = max(0, min(int(value), 500))

    def get_bg_min_fg_fraction(self) -> float:
        return float(self._config.get("app", {}).get("bg_min_fg_fraction", 0.003))

    def set_bg_min_fg_fraction(self, value: float) -> None:
        self._config["app"]["bg_min_fg_fraction"] = max(0.0, min(float(value), 1.0))

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

    def get_save_alert_diagnostics(self) -> bool:
        return bool(self._config.get("app", {}).get("save_alert_diagnostics", False))

    def set_save_alert_diagnostics(self, enabled: bool) -> None:
        self._config["app"]["save_alert_diagnostics"] = bool(enabled)

    def get_headless(self) -> bool:
        return bool(self._config.get("app", {}).get("headless", False))

    def set_headless(self, enabled: bool) -> None:
        self._config["app"]["headless"] = bool(enabled)

    def get_reconnect_size_tolerance(self) -> int:
        return max(0, min(500, int(self._config.get("app", {}).get("reconnect_size_tolerance", 20))))

    def set_reconnect_size_tolerance(self, value: int) -> None:
        self._config["app"]["reconnect_size_tolerance"] = max(0, min(500, int(value)))

    def get_prompt_on_reconnect_fail(self) -> bool:
        return bool(self._config.get("app", {}).get("prompt_on_reconnect_fail", True))

    def set_prompt_on_reconnect_fail(self, enabled: bool) -> None:
        self._config["app"]["prompt_on_reconnect_fail"] = bool(enabled)

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
        # Normalize title and reject duplicate titles (case-insensitive)
        normalized_title = str(window_title or "").strip()
        for t in self._config.get("thumbnails", []):
            if str(t.get("window_title", "")).strip().lower() == normalized_title.lower():
                logger.warning(f"Thumbnail with title already exists (id={t.get('id')}), rejecting add for '{normalized_title}'")
                return None

        thumbnail_id = generate_uuid()
        
        position = position or {"x": 0, "y": 0, "monitor": 0}
        size = size or {"width": THUMBNAIL_DEFAULT_WIDTH, "height": THUMBNAIL_DEFAULT_HEIGHT}
        
        thumbnail = {
            "id": thumbnail_id,
            "window_title": normalized_title,
            "window_hwnd": window_hwnd,
            "window_slot": None,
            "window_class": window_class or "",
            "window_size": list(window_size) if window_size else None,
            "monitor_id": monitor_id,
            "position": position,
            "size": size,
            "opacity": self.get_opacity(),
            "always_on_top": self.get_always_on_top(),
            "show_border": self.get_show_borders(),
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
        # If updating title, normalize and prevent duplicates
        if "window_title" in updates:
            new_title = str(updates.get("window_title") or "").strip()
            for t in self._config.get("thumbnails", []):
                if t.get("id") == thumbnail_id:
                    continue
                if str(t.get("window_title", "")).strip().lower() == new_title.lower():
                    logger.warning(f"Rejecting update: another thumbnail already uses title '{new_title}'")
                    return False
            updates["window_title"] = new_title

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

    def set_all_thumbnail_opacity(self, opacity: float) -> None:
        """Set opacity for all existing thumbnails."""
        clamped = max(0.2, min(float(opacity), 1.0))
        for thumbnail in self._config.get("thumbnails", []):
            thumbnail["opacity"] = clamped
    
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

    def get_theme_preset(self) -> str:
        """Get UI theme name."""
        preset = str(self._config.get("ui", {}).get("theme_preset", "default") or "default").strip().lower()
        if preset in ("default", "slate", "midnight", "high-contrast"):
            return preset
        if bool(self._config.get("app", {}).get("high_contrast", False)):
            return "high-contrast"
        return "default"

    def set_theme_preset(self, preset: str) -> None:
        """Set UI theme name."""
        normalized = str(preset or "default").strip().lower()
        if normalized not in ("default", "slate", "midnight", "high-contrast"):
            normalized = "default"
        self._config.setdefault("ui", {})["theme_preset"] = normalized
        self._config.setdefault("app", {})["high_contrast"] = normalized == "high-contrast"

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
