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
import os
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.core.change_detectors import (
    ChangeDetector, create_detector, VALID_METHODS,
)
from screenalert_core.utils.constants import DEFAULT_ALERT_THRESHOLD, BG_MODELS_DIR

logger = logging.getLogger(__name__)

# Valid region states
STATE_OK = "ok"
STATE_ALERT = "alert"
STATE_WARNING = "warning"
STATE_PAUSED = "paused"
STATE_DISABLED = "disabled"


def _build_detector_kwargs(region_config: Dict, global_config: Optional[Dict] = None) -> Tuple[str, dict]:
    """Extract the detection method and kwargs from region config,
    falling back to global_config when the region doesn't override.

    Returns (method_name, kwargs_dict).
    """
    gcfg = global_config or {}

    # Region-level override wins; otherwise use global
    method = region_config.get("detection_method") or gcfg.get("detection_method", "ssim")
    if method not in VALID_METHODS:
        method = "ssim"

    # Build kwargs appropriate for the chosen method
    kwargs: Dict = {}

    if method in ("ssim", "phash"):
        kwargs["threshold"] = float(
            region_config.get("alert_threshold",
                              gcfg.get("alert_threshold", DEFAULT_ALERT_THRESHOLD))
        )
    elif method == "edge_only":
        kwargs["min_edge_fraction"] = float(
            region_config.get("min_edge_fraction",
                              gcfg.get("min_edge_fraction", 0.003))
        )
        kwargs["canny_low"] = int(
            region_config.get("canny_low", gcfg.get("canny_low", 40))
        )
        kwargs["canny_high"] = int(
            region_config.get("canny_high", gcfg.get("canny_high", 120))
        )
        kwargs["binarize"] = bool(
            region_config.get("edge_binarize", gcfg.get("edge_binarize", False))
        )
    elif method == "background_subtraction":
        kwargs["history"] = int(
            region_config.get("bg_history", gcfg.get("bg_history", 500))
        )
        kwargs["var_threshold"] = float(
            region_config.get("bg_var_threshold", gcfg.get("bg_var_threshold", 16.0))
        )
        kwargs["learning_rate"] = float(
            region_config.get("bg_learning_rate", gcfg.get("bg_learning_rate", -1.0))
        )
        kwargs["warmup_frames"] = int(
            region_config.get("bg_warmup_frames", gcfg.get("bg_warmup_frames", 30))
        )
        kwargs["min_fg_fraction"] = float(
            region_config.get("bg_min_fg_fraction", gcfg.get("bg_min_fg_fraction", 0.003))
        )

    return method, kwargs


class RegionMonitor:
    """Monitors a specific region in a window for changes.

    Implements a timed state machine:
        OK -> ALERT (on change, play sound)
        ALERT -> ALERT (on change, reset hold timer, no sound)
        ALERT -> WARNING (no change for alert_hold_seconds)
        WARNING -> ALERT (on change, play sound)
        WARNING -> OK (no change for alert_hold_seconds)
    """

    def __init__(self, region_id: str, thumbnail_id: str, region_config: Dict,
                 global_config: Optional[Dict] = None):
        self.region_id = region_id
        self.thumbnail_id = thumbnail_id
        self.config = region_config

        self.previous_image: Optional[Image.Image] = None
        self.last_alert_prev_image: Optional[Image.Image] = None
        self.last_alert_curr_image: Optional[Image.Image] = None
        self.paused = False
        self.disabled = region_config.get("enabled", True) is False

        # State machine
        self._state: str = STATE_OK
        self._alert_start_time: float = 0.0
        self._warning_start_time: float = 0.0

        # Create detector from config
        method, kwargs = _build_detector_kwargs(region_config, global_config)
        self._detector: ChangeDetector = create_detector(method, **kwargs)
        self._detector_method: str = method

        # Try to load persisted warmup state
        state_path = self._state_path()
        if state_path:
            self._detector.load_state(state_path)

    def _state_path(self) -> str:
        """Return file path for persisted detector state."""
        return os.path.join(BG_MODELS_DIR, f"{self.thumbnail_id}_{self.region_id}")

    @property
    def detector(self) -> ChangeDetector:
        return self._detector

    @property
    def detector_method(self) -> str:
        return self._detector_method

    def set_detector(self, method: str, global_config: Optional[Dict] = None,
                     **override_kwargs) -> None:
        """Swap the detection method at runtime.

        Saves state of the old detector (if applicable) before replacing it.
        """
        # Save old state
        self.save_detector_state()
        self._detector.on_region_removed()

        # Merge override kwargs into region config temporarily
        cfg = dict(self.config)
        cfg["detection_method"] = method
        cfg.update(override_kwargs)

        m, kwargs = _build_detector_kwargs(cfg, global_config)
        self._detector = create_detector(m, **kwargs)
        self._detector_method = m

        # Reset baseline so the new detector starts fresh
        self.previous_image = None
        self._state = STATE_OK

        # Load persisted state for new detector
        state_path = self._state_path()
        if state_path:
            self._detector.load_state(state_path)

        logger.info("Region %s detector changed to %s", self.region_id, m)

    def save_detector_state(self) -> None:
        """Persist current detector state to disk."""
        state_path = self._state_path()
        if state_path:
            self._detector.save_state(state_path)

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
        """Return remaining hold time for ALERT/WARNING states."""
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
               alert_hold_seconds: float = 10.0,
               # Legacy params kept for back-compat but ignored when
               # the region has its own detector instance.
               **_kwargs) -> Tuple[str, bool]:
        """Update region state with new window image.

        Returns:
            (state, should_play_sound)
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

        # Size changed – reset baseline and detector
        if self.previous_image.size != region_image.size:
            self.previous_image = region_image
            self._detector.reset()
            return self._state, False

        # Detect change using the region's detector
        has_change = self._detector.detect(self.previous_image, region_image)
        if has_change:
            logger.info(
                "Region %s change DETECTED (method=%s state=%s)",
                self.region_id, self._detector_method, self._state,
            )
        pre_update_image = self.previous_image
        self.previous_image = region_image

        # ── state machine transitions ──────────────────────────────
        should_play_sound = False
        old_state = self._state

        if self._state == STATE_OK:
            if has_change:
                self._state = STATE_ALERT
                self._alert_start_time = now
                should_play_sound = True
                self.last_alert_prev_image = pre_update_image
                self.last_alert_curr_image = region_image

        elif self._state == STATE_ALERT:
            if has_change:
                self._alert_start_time = now
            else:
                if (now - self._alert_start_time) >= alert_hold_seconds:
                    self._state = STATE_WARNING
                    self._warning_start_time = now

        elif self._state == STATE_WARNING:
            if has_change:
                self._state = STATE_ALERT
                self._alert_start_time = now
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
        self._detector.reset()


class MonitoringEngine:
    """Manages multiple region monitors"""

    def __init__(self):
        """Initialize monitoring engine"""
        self.monitors: Dict[str, RegionMonitor] = {}  # region_id -> RegionMonitor
        self.thumbnail_monitors: Dict[str, List[str]] = {}  # thumbnail_id -> [region_ids]

    def add_region(self, region_id: str, thumbnail_id: str,
                  region_config: Dict,
                  global_config: Optional[Dict] = None) -> RegionMonitor:
        """Register a new region monitor"""
        monitor = RegionMonitor(region_id, thumbnail_id, region_config,
                                global_config=global_config)
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
        monitor.save_detector_state()
        monitor.detector.on_region_removed()
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
                      alert_hold_seconds: float = 10.0,
                      **kwargs) -> List[Tuple[str, str, bool]]:
        """Update all regions for a thumbnail.

        Detection params are now held per-region on each monitor's detector
        instance, so only alert_hold_seconds is passed through.

        Returns:
            List of (region_id, state, should_play_sound) tuples.
        """
        results = []
        monitors = self.get_thumbnail_monitors(thumbnail_id)

        for monitor in monitors:
            state, should_play_sound = monitor.update(
                window_image, alert_hold_seconds,
            )
            results.append((monitor.region_id, state, should_play_sound))

        return results

    def save_all_detector_states(self) -> None:
        """Persist all detector states (call on shutdown)."""
        for monitor in self.monitors.values():
            try:
                monitor.save_detector_state()
            except Exception as exc:
                logger.warning("Failed to save state for region %s: %s",
                               monitor.region_id, exc)

    def shutdown(self) -> None:
        """Cleanup (no-op, reserved for future use)."""
        pass
