"""Modular change detection framework.

Each detector implements a common interface so the monitoring system can
swap detection strategies at runtime.  Detectors optionally support
persisting their learned state to disk so warmup can be skipped on
restart.

Available detectors:
    ssim                  – Structural Similarity (scikit-image)
    phash                 – Perceptual hash (average hash)
    edge_only             – Canny edge diff (bilateral-filtered)
    background_subtraction – OpenCV MOG2 background subtractor
"""

from __future__ import annotations

import abc
import logging
import os
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ChangeDetector(abc.ABC):
    """Base class for all change detectors."""

    # Human-readable name shown in UI / logs
    name: str = "base"

    def __init__(self, **kwargs):
        """Subclasses accept arbitrary config via **kwargs."""
        self.last_detect_info: dict = {}  # populated by detect() with method-specific metrics

    # -- core API ----------------------------------------------------------

    @abc.abstractmethod
    def detect(self, prev: Image.Image, curr: Image.Image) -> bool:
        """Return *True* if a meaningful change occurred between frames."""

    def reset(self) -> None:
        """Reset internal state (e.g. learned background)."""

    # -- state persistence -------------------------------------------------

    def save_state(self, path: str) -> None:
        """Persist learned state to *path* (file or directory)."""

    def load_state(self, path: str) -> bool:
        """Restore learned state from *path*.  Return True on success."""
        return False

    # -- lifecycle ---------------------------------------------------------

    def on_region_removed(self) -> None:
        """Called when the owning region is removed.  Clean up resources."""


# ---------------------------------------------------------------------------
# SSIM detector
# ---------------------------------------------------------------------------

class SSIMDetector(ChangeDetector):
    """Structural Similarity change detection."""

    name = "ssim"

    def __init__(self, *, threshold: float = 0.99, **kwargs):
        super().__init__(**kwargs)
        self.threshold = threshold

    def detect(self, prev: Image.Image, curr: Image.Image) -> bool:
        from skimage.metrics import structural_similarity as ssim
        if prev.size != curr.size:
            return True
        g1 = np.array(prev.convert("L"))
        g2 = np.array(curr.convert("L"))
        score = ssim(g1, g2)
        changed = score < self.threshold
        self.last_detect_info = {
            "similarity": round(score, 4),
            "threshold": self.threshold,
        }
        if changed:
            logger.debug("SSIM=%.4f < threshold=%.4f -> CHANGED", score, self.threshold)
        return changed


# ---------------------------------------------------------------------------
# pHash detector
# ---------------------------------------------------------------------------

class PHashDetector(ChangeDetector):
    """Perceptual hash (average hash) change detection."""

    name = "phash"

    def __init__(self, *, threshold: float = 0.99, hash_size: int = 8, **kwargs):
        super().__init__(**kwargs)
        self.threshold = threshold
        self.hash_size = hash_size

    def detect(self, prev: Image.Image, curr: Image.Image) -> bool:
        h1 = self._avg_hash(prev)
        h2 = self._avg_hash(curr)
        hamming = np.count_nonzero(h1 != h2)
        similarity = 1.0 - hamming / max(1, h1.size)
        changed = similarity < self.threshold
        self.last_detect_info = {
            "similarity": round(similarity, 4),
            "threshold": self.threshold,
        }
        if changed:
            logger.debug("pHash similarity=%.4f < threshold=%.4f -> CHANGED", similarity, self.threshold)
        return changed

    def _avg_hash(self, img: Image.Image) -> np.ndarray:
        gray = img.convert("L").resize(
            (self.hash_size, self.hash_size), Image.Resampling.LANCZOS
        )
        arr = np.array(gray, dtype=np.float32)
        return arr > arr.mean()


# ---------------------------------------------------------------------------
# Canny edge detector
# ---------------------------------------------------------------------------

class EdgeDetector(ChangeDetector):
    """Canny edge-diff change detection with bilateral pre-filter."""

    name = "edge_only"

    def __init__(self, *,
                 min_edge_fraction: float = 0.003,
                 canny_low: int = 40,
                 canny_high: int = 120,
                 binarize: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.min_edge_fraction = min_edge_fraction
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.binarize = binarize

    def detect(self, prev: Image.Image, curr: Image.Image) -> bool:
        g1 = np.array(prev.convert("L"), dtype=np.uint8)
        g2 = np.array(curr.convert("L"), dtype=np.uint8)
        edges1 = self._canny(g1)
        edges2 = self._canny(g2)
        changed_px = int(np.count_nonzero(edges1 != edges2))
        total_px = g1.size
        fraction = changed_px / max(1, total_px)
        self.last_detect_info = {
            "edge_change_pct": round(fraction * 100, 3),
            "min_edge_pct": round(self.min_edge_fraction * 100, 3),
        }
        logger.debug(
            "edge-diff: %d/%d px (%.3f%%) min=%.3f%%",
            changed_px, total_px, fraction * 100, self.min_edge_fraction * 100,
        )
        return fraction >= self.min_edge_fraction

    def _canny(self, gray: np.ndarray) -> np.ndarray:
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        if self.binarize:
            gray = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11, C=2,
            )
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        return cv2.Canny(blurred, threshold1=self.canny_low, threshold2=self.canny_high)


# ---------------------------------------------------------------------------
# MOG2 Background Subtraction detector
# ---------------------------------------------------------------------------

class MOG2Detector(ChangeDetector):
    """OpenCV MOG2 background subtraction.

    Learns the background over time and flags *sudden* foreground changes.
    Gradual animated backgrounds (e.g. game scenes) are absorbed into the
    background model and ignored.

    Warmup
    ------
    The first *warmup_frames* calls to ``detect()`` always return False so
    the model can learn the baseline.  To skip warmup on restart, call
    ``load_state(path)`` which replays a previously saved background frame.

    State persistence
    -----------------
    ``save_state(path)``  – writes the current background image to an .npz
    ``load_state(path)``  – reads it back and feeds it to the model
    """

    name = "background_subtraction"

    def __init__(self, *,
                 history: int = 500,
                 var_threshold: float = 16.0,
                 learning_rate: float = -1.0,
                 warmup_frames: int = 30,
                 min_fg_fraction: float = 0.003,
                 **kwargs):
        super().__init__(**kwargs)
        self.history = history
        self.var_threshold = var_threshold
        self.learning_rate = learning_rate
        self.warmup_frames = warmup_frames
        self.min_fg_fraction = min_fg_fraction

        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.var_threshold,
            detectShadows=False,
        )
        self._frame_count: int = 0
        self._warmed_up: bool = False

    # -- core --------------------------------------------------------------

    def detect(self, prev: Image.Image, curr: Image.Image) -> bool:
        # MOG2 is stateful — it only needs the *current* frame.
        # ``prev`` is ignored (kept for interface compatibility).
        gray = np.array(curr.convert("L"), dtype=np.uint8)

        lr = self.learning_rate if self.learning_rate >= 0 else -1
        fg_mask = self._subtractor.apply(gray, learningRate=lr)

        self._frame_count += 1

        if not self._warmed_up:
            if self._frame_count < self.warmup_frames:
                logger.debug(
                    "MOG2 warmup %d/%d", self._frame_count, self.warmup_frames
                )
                return False
            self._warmed_up = True
            logger.info("MOG2 warmup complete after %d frames", self._frame_count)

        # Fraction of foreground pixels
        fg_pixels = int(np.count_nonzero(fg_mask > 128))
        total = max(1, gray.size)
        fraction = fg_pixels / total

        self.last_detect_info = {
            "fg_pct": round(fraction * 100, 3),
            "min_fg_pct": round(self.min_fg_fraction * 100, 3),
            "fg_pixels": fg_pixels,
            "total_pixels": total,
            "frame_count": self._frame_count,
            "warmed_up": self._warmed_up,
        }
        logger.debug(
            "MOG2: fg=%d/%d (%.3f%%) min=%.3f%%",
            fg_pixels, total, fraction * 100, self.min_fg_fraction * 100,
        )
        return fraction >= self.min_fg_fraction

    def reset(self) -> None:
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.var_threshold,
            detectShadows=False,
        )
        self._frame_count = 0
        self._warmed_up = False

    # -- state persistence -------------------------------------------------

    def save_state(self, path: str) -> None:
        """Save the current background image so warmup can be skipped."""
        try:
            bg = self._subtractor.getBackgroundImage()
            if bg is None:
                logger.debug("MOG2: no background image to save yet")
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            np.savez_compressed(path, bg=bg, frame_count=self._frame_count)
            logger.debug("MOG2 state saved to %s", path)
        except Exception as exc:
            logger.warning("MOG2 save_state failed: %s", exc)

    def load_state(self, path: str) -> bool:
        """Replay saved background to skip warmup."""
        npz_path = path if path.endswith(".npz") else path + ".npz"
        if not os.path.exists(npz_path):
            return False
        try:
            data = np.load(npz_path)
            bg = data["bg"]
            saved_count = int(data.get("frame_count", self.warmup_frames))

            # Feed the saved background to the model repeatedly to build up
            # internal statistics quickly.
            replay_count = min(self.warmup_frames, 30)
            # Convert to grayscale if the saved image is color
            if len(bg.shape) == 3:
                bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
            else:
                bg_gray = bg

            for _ in range(replay_count):
                self._subtractor.apply(bg_gray, learningRate=0.5)

            self._frame_count = saved_count
            self._warmed_up = True
            logger.info(
                "MOG2 state loaded from %s (replayed %d frames, skipping warmup)",
                npz_path, replay_count,
            )
            return True
        except Exception as exc:
            logger.warning("MOG2 load_state failed: %s", exc)
            return False

    def on_region_removed(self) -> None:
        self.reset()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Registry maps config string → detector class
DETECTOR_REGISTRY: Dict[str, type] = {
    "ssim": SSIMDetector,
    "phash": PHashDetector,
    "edge_only": EdgeDetector,
    "background_subtraction": MOG2Detector,
}

# All valid method names (used by config validation)
VALID_METHODS = tuple(DETECTOR_REGISTRY.keys())


def create_detector(method: str, **kwargs) -> ChangeDetector:
    """Create a detector instance by method name.

    Unknown methods fall back to SSIM.
    """
    cls = DETECTOR_REGISTRY.get(method, SSIMDetector)
    return cls(**kwargs)
