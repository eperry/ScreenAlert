"""Configuration management for ScreenAlert"""

import json
import logging
import os
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
                "log_verbose": False,
                "last_window_filter": "",
            },
            "thumbnails": [],
            "ui": {
                "main_window_geometry": "1200x800+100+100",
                "settings_expanded": False,
            }
        }
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load config from file or create default"""
        try:
            if os.path.exists(self.config_path):
                logger.info(f"Loading config from {self.config_path}")
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                # Merge with defaults to handle missing keys
                defaults = self._get_default_config()
                loaded_config = self._merge_configs(defaults, loaded_config)
                return loaded_config
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
    
    def get_verbose_logging(self) -> bool:
        """Get verbose logging setting"""
        return self._config.get("app", {}).get("log_verbose", False)
    
    def set_verbose_logging(self, verbose: bool) -> None:
        """Set verbose logging"""
        self._config["app"]["log_verbose"] = verbose
    
    def get_last_window_filter(self) -> str:
        """Get last used window filter"""
        return self._config.get("app", {}).get("last_window_filter", "")
    
    def set_last_window_filter(self, filter_text: str) -> None:
        """Set last used window filter"""
        self._config["app"]["last_window_filter"] = filter_text
    
    # Thumbnail management
    def add_thumbnail(self, window_title: str, window_hwnd: int, 
                     position: Dict = None, size: Dict = None) -> str:
        """Add a new thumbnail configuration
        
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
        region.setdefault("tts_message", "")
        
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
