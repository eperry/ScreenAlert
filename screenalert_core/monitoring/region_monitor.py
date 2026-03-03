"""Region monitoring and change detection with state machine.

State machine flow:
    PAUSED / DISABLED  (external overrides)
      |
      v
    OK  ──(change detected)──>  ALERT  ──(no change, hold expired)──>  WARNING  ──(no change, hold expired)──>  OK
      ^                           |  ^                                    |
      |                           |  +--- (change detected, reset timer) |
      |                           +--- (change detected) ────────────────+
      |
      +--- (first image captured)

States:
    ok       - green  - no changes since last probe
    alert    - red    - change detected, held for alert_hold_seconds
    warning  - orange - was alert, no NEW changes, held for alert_hold_seconds
    paused   - blue   - monitoring paused by user
    disabled - blue   - region disabled / no window attached
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.utils.constants import DEFAULT_ALERT_THRESHOLD

logger = logging.getLogger(__name__)

# Valid region states
STATE_OK = "ok"
STATE_ALERT = "alert"
STATE_WARNING = "warning"
STATE_PAUSED = "paused"
STATE_DISABLED = "disabled"


class RegionMonitor:
    """Monitors a specific region in a window for changes.

    Implements a timed state machine:
        OK -> ALERT (on change, play sound)
        ALERT -> ALERT (on change, reset hold timer, no sound)
        ALERT -> WARNING (no change for alert_hold_seconds)
        WARNING -> ALERT (on change, play sound)
        WARNING -> OK (no change for alert_hold_seconds)
    """

    def __init__(self, region_id: str, thumbnail_id: str, region_config: Dict):
        self.region_id = region_id
        self.thumbnail_id = thumbnail_id
        self.config = region_config

        self.previous_image: Optional[Image.Image] = None
        self.paused = False
        self.disabled = region_config.get("enabled", True) is False

        # State machine
        self._state: str = STATE_OK
        self._alert_start_time: float = 0.0
        self._warning_start_time: float = 0.0

    # ── public properties ──────────────────────────────────────────
    @property
    def state(self) -> str:
        """Current region state, accounting for pause/disabled overrides."""
        if self.disabled:
            return STATE_DISABLED
        if self.paused:
            return STATE_PAUSED
        return self._state

    # back-compat alias
    @property
    def is_alert(self) -> bool:
        return self._state == STATE_ALERT

    def get_state_remaining_seconds(self, hold_seconds: float) -> Optional[int]:
        """Return remaining hold time for ALERT/WARNING states.

        Args:
            hold_seconds: configured hold duration in seconds

        Returns:
            Remaining seconds (0+), or None if not in a timed state.
        """
        now = time.time()
        hold = max(1.0, float(hold_seconds))

        if self.state == STATE_ALERT:
            elapsed = max(0.0, now - self._alert_start_time)
            return max(0, int(hold - elapsed + 0.999))

        if self.state == STATE_WARNING:
            elapsed = max(0.0, now - self._warning_start_time)
            return max(0, int(hold - elapsed + 0.999))

        return None

    # ── core update ────────────────────────────────────────────────
    def update(self, window_image: Image.Image,
               alert_hold_seconds: float = 10.0) -> Tuple[str, bool]:
        """Update region state with new window image.

        Args:
            window_image: Full window capture.
            alert_hold_seconds: How long (seconds) to hold Alert/Warning
                                states before transitioning.

        Returns:
            (state, should_play_sound)
                state            - current state after this update
                should_play_sound - True only on first entry into ALERT
        """
        if self.disabled:
            return STATE_DISABLED, False
        if self.paused:
            return STATE_PAUSED, False

        now = time.time()

        # Crop region from window image
        try:
            region_image = ImageProcessor.crop_region(
                window_image,
                self.config["rect"]
            )
        except Exception as e:
            logger.debug(f"Error cropping region {self.region_id}: {e}")
            return self._state, False

        # First frame – initialise baseline
        if self.previous_image is None:
            self.previous_image = region_image
            self._state = STATE_OK
            return STATE_OK, False

        # Size changed – reset baseline
        if self.previous_image.size != region_image.size:
            self.previous_image = region_image
            return self._state, False

        # Detect change
        threshold = self.config.get("alert_threshold", DEFAULT_ALERT_THRESHOLD)
        method = self.config.get("change_detection_method", "ssim")
        has_change = ImageProcessor.detect_change(
            self.previous_image,
            region_image,
            threshold,
            method=method,
        )
        if has_change:
            logger.info(
                "Region %s change DETECTED (method=%s threshold=%.4f state=%s)",
                self.region_id, method, threshold, self._state,
            )
        self.previous_image = region_image

        # ── state machine transitions ──────────────────────────────
        should_play_sound = False
        old_state = self._state

        if self._state == STATE_OK:
            if has_change:
                self._state = STATE_ALERT
                self._alert_start_time = now
                should_play_sound = True

        elif self._state == STATE_ALERT:
            if has_change:
                # Still changing – reset hold timer (no new sound)
                self._alert_start_time = now
            else:
                # No change – check if hold period expired
                if (now - self._alert_start_time) >= alert_hold_seconds:
                    self._state = STATE_WARNING
                    self._warning_start_time = now

        elif self._state == STATE_WARNING:
            if has_change:
                # New change during warning – re-enter alert
                self._state = STATE_ALERT
                self._alert_start_time = now
                should_play_sound = True
            else:
                if (now - self._warning_start_time) >= alert_hold_seconds:
                    self._state = STATE_OK

        if old_state != self._state:
            logger.debug(
                f"Region {self.region_id} state: {old_state} -> {self._state}"
            )

        return self._state, should_play_sound

    # ── control methods ────────────────────────────────────────────
    def toggle_pause(self) -> bool:
        """Toggle pause state."""
        self.paused = not self.paused
        logger.info(f"Region {self.region_id} pause: {self.paused}")
        return self.paused

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable region."""
        self.disabled = not enabled
        if self.disabled:
            self._state = STATE_OK
        logger.info(f"Region {self.region_id} enabled: {enabled}")

    def reset(self) -> None:
        """Reset region state to initial."""
        self.previous_image = None
        self._state = STATE_OK
        self._alert_start_time = 0.0
        self._warning_start_time = 0.0


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
                      alert_hold_seconds: float = 10.0) -> List[Tuple[str, str, bool]]:
        """Update all regions for a thumbnail.

        Returns:
            List of (region_id, state, should_play_sound) tuples.
        """
        results = []
        monitors = self.get_thumbnail_monitors(thumbnail_id)

        for monitor in monitors:
            state, should_play_sound = monitor.update(window_image, alert_hold_seconds)
            results.append((monitor.region_id, state, should_play_sound))

        return results
