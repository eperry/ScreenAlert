"""Region monitoring and change detection"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.constants import DEFAULT_ALERT_THRESHOLD

logger = logging.getLogger(__name__)


class RegionMonitor:
    """Monitors a specific region in a window for changes"""
    
    def __init__(self, region_id: str, thumbnail_id: str, region_config: Dict):
        """Initialize region monitor
        
        Args:
            region_id: Unique region ID
            thumbnail_id: Parent thumbnail ID
            region_config: Region configuration dict
        """
        self.region_id = region_id
        self.thumbnail_id = thumbnail_id
        self.config = region_config
        
        self.previous_image: Optional[Image.Image] = None
        self.is_alert = False
        self.last_alert_time = 0
        self.paused = False
        self.disabled = region_config.get("enabled", True) is False
    
    def update(self, window_image: Image.Image, 
              highlight_time_sec: int = 5) -> Tuple[bool, bool]:
        """Update region state with new window image
        
        Args:
            window_image: Full window capture
            highlight_time_sec: How long to keep alert displayed
        
        Returns:
            (changed, should_alert) tuple
        """
        if self.disabled or self.paused:
            return False, False
        
        now = time.time()
        
        # Crop region from window image
        try:
            region_image = ImageProcessor.crop_region(
                window_image, 
                self.config["rect"]
            )
        except Exception as e:
            logger.debug(f"Error cropping region {self.region_id}: {e}")
            return False, False
        
        # Initialize on first run
        if self.previous_image is None:
            self.previous_image = region_image
            return False, False
        
        # Skip if size changed
        if self.previous_image.size != region_image.size:
            self.previous_image = region_image
            return False, False
        
        # Detect change
        threshold = self.config.get("alert_threshold", DEFAULT_ALERT_THRESHOLD)
        has_change = ImageProcessor.detect_change(
            self.previous_image, 
            region_image, 
            threshold
        )
        
        # Update alert state
        should_alert = False
        if has_change:
            last_alert = self.last_alert_time
            if not self.is_alert or (now - last_alert) > highlight_time_sec:
                should_alert = True
                self.last_alert_time = now
            self.is_alert = True
        else:
            # Clear old alerts
            if self.is_alert and (now - self.last_alert_time) >= highlight_time_sec:
                self.is_alert = False
        
        self.previous_image = region_image
        return has_change, should_alert
    
    def toggle_pause(self) -> bool:
        """Toggle pause state"""
        self.paused = not self.paused
        logger.info(f"Region {self.region_id} pause: {self.paused}")
        return self.paused
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable region"""
        self.disabled = not enabled
        if self.disabled:
            self.is_alert = False
        logger.info(f"Region {self.region_id} enabled: {enabled}")
    
    def reset(self) -> None:
        """Reset region state"""
        self.previous_image = None
        self.is_alert = False
        self.last_alert_time = 0


class MonitoringEngine:
    """Manages multiple region monitors"""
    
    def __init__(self):
        """Initialize monitoring engine"""
        self.monitors: Dict[str, RegionMonitor] = {}  # region_id -> RegionMonitor
        self.thumbnail_monitors: Dict[str, List[str]] = {}  # thumbnail_id -> [region_ids]
    
    def add_region(self, region_id: str, thumbnail_id: str, 
                  region_config: Dict) -> RegionMonitor:
        """Register a new region monitor"""
        monitor = RegionMonitor(region_id, thumbnail_id, region_config)
        self.monitors[region_id] = monitor
        
        if thumbnail_id not in self.thumbnail_monitors:
            self.thumbnail_monitors[thumbnail_id] = []
        self.thumbnail_monitors[thumbnail_id].append(region_id)
        
        logger.info(f"Added monitor for region {region_id}")
        return monitor
    
    def remove_region(self, region_id: str) -> bool:
        """Remove region monitor"""
        if region_id not in self.monitors:
            return False
        
        monitor = self.monitors[region_id]
        thumbnail_id = monitor.thumbnail_id
        
        del self.monitors[region_id]
        if thumbnail_id in self.thumbnail_monitors:
            if region_id in self.thumbnail_monitors[thumbnail_id]:
                self.thumbnail_monitors[thumbnail_id].remove(region_id)
        
        logger.info(f"Removed monitor for region {region_id}")
        return True
    
    def get_monitor(self, region_id: str) -> Optional[RegionMonitor]:
        """Get specific region monitor"""
        return self.monitors.get(region_id)
    
    def get_thumbnail_monitors(self, thumbnail_id: str) -> List[RegionMonitor]:
        """Get all monitors for a thumbnail"""
        region_ids = self.thumbnail_monitors.get(thumbnail_id, [])
        return [self.monitors[rid] for rid in region_ids if rid in self.monitors]
    
    def update_regions(self, thumbnail_id: str, window_image: Image.Image,
                      highlight_time_sec: int = 5) -> List[Tuple[str, bool, bool]]:
        """Update all regions for a thumbnail
        
        Returns:
            List of (region_id, changed, should_alert) tuples
        """
        results = []
        monitors = self.get_thumbnail_monitors(thumbnail_id)
        
        for monitor in monitors:
            changed, should_alert = monitor.update(window_image, highlight_time_sec)
            results.append((monitor.region_id, changed, should_alert))
        
        return results
