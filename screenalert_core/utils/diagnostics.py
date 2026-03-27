"""Alert diagnostics image saving utilities.

Extracted from ScreenAlertEngine so it can be used and tested independently.
"""

import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional

from PIL import Image

logger = logging.getLogger(__name__)


def _safe_filename(text: str, max_len: int = 64) -> str:
    """Sanitise *text* for use in a file name."""
    text = re.sub(r'[^a-zA-Z0-9._-]+', '_', text or "")
    return (text[:max_len] or "item")


def save_alert_diagnostics(
    capture_dir: str,
    thumbnail_config: Dict,
    region_config: Dict,
    window_image: Image.Image,
    region_monitor,
    prev_window_image: Optional[Image.Image],
    canny_low: int,
    canny_high: int,
    edge_binarize: bool,
) -> None:
    """Save diagnostic images when an alert fires.

    Writes up to seven PNG files into ``<capture_dir>/diagnostics/``:
      - ``*_window_prev.png``   previous full window frame
      - ``*_window_curr.png``   current full window frame
      - ``*_region_prev.png``   cropped region previous frame
      - ``*_region_curr.png``   cropped region current frame
      - ``*_edges_prev.png``    Canny edge map of previous region
      - ``*_edges_curr.png``    Canny edge map of current region
      - ``*_edges_diff.png``    absolute difference of edge maps

    Args:
        capture_dir:       Base capture directory from config.
        thumbnail_config:  Thumbnail config dict (used for window_title, id).
        region_config:     Region config dict (used for region name).
        window_image:      Current full-window PIL image.
        region_monitor:    RegionMonitor instance with ``last_alert_*_image``.
        prev_window_image: Previous full-window PIL image, or None.
        canny_low:         Lower threshold for Canny edge detection.
        canny_high:        Upper threshold for Canny edge detection.
        edge_binarize:     Whether to binarize the edge map.
    """
    try:
        import numpy as np
        from screenalert_core.core.image_processor import ImageProcessor

        diag_dir = os.path.join(capture_dir, "diagnostics")
        os.makedirs(diag_dir, exist_ok=True)

        window_title = thumbnail_config.get("window_title", "window")
        region_name = region_config.get("name", "region")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{timestamp}_{_safe_filename(window_title)}_{_safe_filename(region_name)}_alert"

        # Previous full-window frame
        if prev_window_image is not None:
            prev_window_image.save(
                os.path.join(diag_dir, f"{prefix}_window_prev.png"), format="PNG"
            )

        # Current full-window frame
        window_image.save(
            os.path.join(diag_dir, f"{prefix}_window_curr.png"), format="PNG"
        )

        # Region crops from monitor's stored alert images
        prev_region = getattr(region_monitor, "last_alert_prev_image", None)
        curr_region = getattr(region_monitor, "last_alert_curr_image", None)

        if prev_region is not None:
            prev_region.save(
                os.path.join(diag_dir, f"{prefix}_region_prev.png"), format="PNG"
            )
        if curr_region is not None:
            curr_region.save(
                os.path.join(diag_dir, f"{prefix}_region_curr.png"), format="PNG"
            )

        # Edge detection maps and diff
        if prev_region is not None and curr_region is not None:
            g1 = np.array(prev_region.convert("L"), dtype=np.uint8)
            g2 = np.array(curr_region.convert("L"), dtype=np.uint8)
            edges1 = ImageProcessor._canny_edges(g1, canny_low, canny_high, binarize=edge_binarize)
            edges2 = ImageProcessor._canny_edges(g2, canny_low, canny_high, binarize=edge_binarize)

            Image.fromarray(edges1).save(
                os.path.join(diag_dir, f"{prefix}_edges_prev.png"), format="PNG"
            )
            Image.fromarray(edges2).save(
                os.path.join(diag_dir, f"{prefix}_edges_curr.png"), format="PNG"
            )

            edge_diff = np.abs(
                edges1.astype(np.int16) - edges2.astype(np.int16)
            ).astype(np.uint8)
            Image.fromarray(edge_diff).save(
                os.path.join(diag_dir, f"{prefix}_edges_diff.png"), format="PNG"
            )

        logger.info("Saved alert diagnostics to %s/%s_*", diag_dir, prefix)

    except Exception as exc:
        logger.warning("Failed to save alert diagnostics: %s", exc)
