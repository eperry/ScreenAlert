"""
MCP image tools — retrieve alert capture images and diagnostic images as base64 PNG.
"""

import base64
import io
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WIDTH = 1920


def _encode_image(path: str, max_width: int) -> Optional[str]:
    """
    Load an image file, optionally resize to max_width, and return base64-encoded PNG.
    Returns None on error.
    """
    try:
        from PIL import Image
        img = Image.open(path)
        w, h = img.size
        if max_width and w > max_width:
            ratio = max_width / w
            img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:
        logger.error("Failed to encode image %s: %s", path, exc)
        return None


def _find_capture_for_event(event_logger, event_id: str) -> Optional[str]:
    """Find the capture_file field of a specific event by id."""
    if not event_logger:
        return None
    result = event_logger.query(limit=1, after_id=None, since=None)
    # Fast path: query all and find by id (EventLogger doesn't have get_by_id)
    all_events = event_logger.query(limit=100000)
    for ev in all_events.get("events", []):
        if ev.get("id") == event_id:
            return ev.get("capture_file")
    return None


def _find_latest_capture(event_logger, window_id: str, region_id: str) -> Optional[str]:
    """Find the most recent capture_file for a given window+region."""
    if not event_logger:
        return None
    result = event_logger.query(
        limit=100000,
        category="alert",
        window_id=window_id,
        region_id=region_id,
    )
    # Events are in ascending order; iterate reversed for most recent
    for ev in reversed(result.get("events", [])):
        cf = ev.get("capture_file")
        if cf and os.path.isfile(cf):
            return cf
    return None


def register(mcp, engine, config, event_logger) -> None:
    """Register image retrieval MCP tools."""

    # ── get_alert_image ───────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Return an alert capture screenshot as a base64-encoded PNG. "
            "Pass event_id for a specific alert event, or window_id + region_id for "
            "the most recent capture of that region. "
            "max_width resizes before encoding (default 1920, 0 = original size)."
        )
    )
    def get_alert_image(
        event_id: str = "",
        window_id: str = "",
        region_id: str = "",
        max_width: int = _DEFAULT_MAX_WIDTH,
    ) -> dict:
        if not event_logger:
            return {"error": "Event logging is not enabled", "code": 503}

        max_width = max(0, int(max_width))

        capture_file = None

        if event_id:
            capture_file = _find_capture_for_event(event_logger, event_id)
            if not capture_file:
                return {"error": f"Event '{event_id}' not found or has no capture_file", "code": 404}
        elif window_id or region_id:
            if not (window_id and region_id):
                return {"error": "Both window_id and region_id are required when event_id is omitted",
                        "code": 400, "field": "window_id"}
            capture_file = _find_latest_capture(event_logger, window_id, region_id)
            if not capture_file:
                return {"error": "No capture found for that window/region combination", "code": 404}
        else:
            return {"error": "Provide event_id, or window_id + region_id", "code": 400}

        if not os.path.isfile(capture_file):
            return {"error": f"Capture file not found on disk: {capture_file}", "code": 404}

        encoded = _encode_image(capture_file, max_width)
        if encoded is None:
            return {"error": "Failed to encode image", "code": 500}

        return {
            "image": encoded,
            "format": "png",
            "encoding": "base64",
            "file": os.path.basename(capture_file),
        }

    # ── get_alert_diagnostic_images ───────────────────────────────────────────

    @mcp.tool(
        description=(
            "Return all diagnostic images for a specific alert event as base64-encoded PNGs. "
            "Diagnostic images include diff maps, edge maps, and masks saved when "
            "save_alert_diagnostics is enabled. Returns a list of {filename, image} objects."
        )
    )
    def get_alert_diagnostic_images(event_id: str) -> List[dict]:
        if not event_id:
            return [{"error": "event_id is required", "code": 400}]

        if not event_logger:
            return [{"error": "Event logging is not enabled", "code": 503}]

        capture_file = _find_capture_for_event(event_logger, event_id)
        if not capture_file:
            return [{"error": f"Event '{event_id}' not found or has no capture_file", "code": 404}]

        if not os.path.isfile(capture_file):
            return [{"error": f"Capture file not found on disk: {capture_file}", "code": 404}]

        # Diagnostic images are saved alongside the capture with the same base name
        capture_dir = os.path.dirname(capture_file)
        base_name = os.path.splitext(os.path.basename(capture_file))[0]

        result = []
        try:
            for fname in sorted(os.listdir(capture_dir)):
                if fname.startswith(base_name) and fname != os.path.basename(capture_file):
                    full = os.path.join(capture_dir, fname)
                    if os.path.isfile(full):
                        encoded = _encode_image(full, 0)
                        if encoded:
                            result.append({
                                "filename": fname,
                                "image": encoded,
                                "format": "png",
                                "encoding": "base64",
                            })
        except Exception as exc:
            logger.error("Error listing diagnostic images: %s", exc)
            return [{"error": f"Failed to list diagnostic images: {exc}", "code": 500}]

        if not result:
            return [{"note": "No diagnostic images found for this event"}]

        return result
