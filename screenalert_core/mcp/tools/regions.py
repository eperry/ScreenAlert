"""
MCP region tools — list, add, remove, copy regions and manage alerts.
"""

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Keys valid for set_region_setting
_REGION_SETTING_META = {
    "name": {
        "type": "str",
        "description": "Region display name",
    },
    "rect": {
        "type": "object",
        "description": "Position/size in window client-area coordinates {x, y, width, height}",
    },
    "enabled": {
        "type": "bool",
        "description": "Whether this region is actively monitored",
    },
    "tts_message": {
        "type": "str",
        "description": "TTS message template spoken on alert (supports {window} and {region_name})",
    },
    "sound_file": {
        "type": "str",
        "description": "Path to sound file played on alert (empty string = use default)",
    },
    "sound_enabled": {
        "type": "bool",
        "description": "Play sound on alert for this region",
    },
    "tts_enabled": {
        "type": "bool",
        "description": "Speak TTS message on alert for this region",
    },
    "alert_threshold": {
        "type": "float",
        "description": "Change detection sensitivity (0.0–1.0; higher = less sensitive)",
        "valid_range": [0.0, 1.0],
    },
    "change_detection_method": {
        "type": "str",
        "description": "Algorithm used for change detection",
        "valid_values": ["ssim", "phash", "edge_only", "background_subtraction"],
    },
}


def _resolve_window(config, engine, window_id: Optional[str], window_name: Optional[str]):
    if window_id:
        tc = config.get_thumbnail(window_id)
        if not tc:
            return None, {"error": f"Window not found: {window_id}", "code": 404}
        return tc, None
    if not window_name:
        return None, {"error": "window_id or window_name is required", "code": 400, "field": "window_id"}
    needle = window_name.lower()
    matches = [t for t in config.get_all_thumbnails()
               if needle in t.get("window_title", "").lower()]
    if not matches:
        return None, {"error": f"No window matching '{window_name}'", "code": 404}
    if len(matches) > 1:
        return None, {
            "error": f"Ambiguous name '{window_name}' — {len(matches)} matches",
            "code": 409,
            "matches": [{"id": m["id"], "name": m.get("window_title")} for m in matches],
        }
    return matches[0], None


def _find_region(config, region_id: str):
    """Return (thumbnail_config, region_config) or (None, None)."""
    for tc in config.get_all_thumbnails():
        for r in tc.get("monitored_regions", []):
            if r.get("id") == region_id:
                return tc, r
    return None, None


def register(mcp, engine, config, event_logger) -> None:
    """Register all region-related MCP tools onto the FastMCP instance."""

    # ── list_regions ──────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "List all monitoring regions, optionally filtered by window. "
            "Each entry includes current state (ok, alert, warning, paused, disabled, unavailable)."
        )
    )
    def list_regions(window_id: str = "", window_name: str = "") -> List[dict]:
        thumbnails = config.get_all_thumbnails()
        # If a window filter is supplied, limit to that window
        if window_id or window_name:
            tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
            if err:
                return [err]
            thumbnails = [tc]

        result = []
        for tc in thumbnails:
            tid = tc["id"]
            wname = tc.get("window_title", "")
            for r in tc.get("monitored_regions", []):
                rid = r.get("id", "")
                monitor = engine.monitoring_engine.get_monitor(rid)
                state = monitor.state if monitor else ("disabled" if not r.get("enabled", True) else "unknown")
                rect = r.get("rect", [0, 0, 0, 0])
                result.append({
                    "id": rid,
                    "window_id": tid,
                    "window_name": wname,
                    "name": r.get("name", ""),
                    "enabled": r.get("enabled", True),
                    "state": state,
                    "rect": (
                        {"x": rect[0], "y": rect[1], "width": rect[2], "height": rect[3]}
                        if isinstance(rect, (list, tuple)) and len(rect) == 4
                        else rect
                    ),
                })
        return result

    # ── add_region ────────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Add a monitoring region to a window. "
            "rect must be window client-area coordinates: {x, y, width, height}. "
            "Returns the new region id."
        )
    )
    def add_region(
        window_id: str = "",
        window_name: str = "",
        name: str = "",
        rect: Optional[dict] = None,
    ) -> dict:
        tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
        if err:
            return err

        if not name or not name.strip():
            return {"error": "name is required", "code": 400, "field": "name"}
        if not rect:
            return {"error": "rect is required", "code": 400, "field": "rect"}
        try:
            rx, ry = int(rect["x"]), int(rect["y"])
            rw, rh = int(rect["width"]), int(rect["height"])
        except (KeyError, TypeError, ValueError):
            return {"error": "rect must have integer keys x, y, width, height",
                    "code": 422, "field": "rect"}
        if rw <= 0 or rh <= 0:
            return {"error": "width and height must be positive", "code": 422, "field": "rect"}

        region_id = engine.add_region(tc["id"], name.strip(), (rx, ry, rw, rh))
        if not region_id:
            return {"error": "Failed to add region", "code": 500}

        if event_logger:
            event_logger.log("region", "region_added", "mcp",
                             window_id=tc["id"], window_name=tc.get("window_title", ""),
                             region_id=region_id, region_name=name.strip(),
                             rect=[rx, ry, rw, rh])

        return {"id": region_id, "name": name.strip()}

    # ── remove_region ─────────────────────────────────────────────────────────

    @mcp.tool(description="Remove a monitoring region permanently.")
    def remove_region(region_id: str) -> dict:
        if not region_id:
            return {"error": "region_id is required", "code": 400, "field": "region_id"}

        tc, r = _find_region(config, region_id)
        if not tc:
            return {"error": f"Region not found: {region_id}", "code": 404}

        rname = r.get("name", "")
        wid = tc["id"]
        wname = tc.get("window_title", "")

        # Remove from monitoring engine first
        engine.monitoring_engine.remove_region(region_id)
        # Remove from config
        config.remove_region(wid, region_id)
        config.save()

        if event_logger:
            event_logger.log("region", "region_removed", "mcp",
                             window_id=wid, window_name=wname,
                             region_id=region_id, region_name=rname)

        return {"ok": True}

    # ── copy_region ───────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Copy a region (with all alert settings) from one window to another. "
            "Useful when two windows have identical layouts. "
            "name defaults to the source region name."
        )
    )
    def copy_region(
        region_id: str,
        target_window_id: str = "",
        target_window_name: str = "",
        name: str = "",
    ) -> dict:
        if not region_id:
            return {"error": "region_id is required", "code": 400, "field": "region_id"}

        src_tc, src_r = _find_region(config, region_id)
        if not src_tc:
            return {"error": f"Source region not found: {region_id}", "code": 404}

        tgt_tc, err = _resolve_window(config, engine, target_window_id or None,
                                      target_window_name or None)
        if err:
            return err

        new_name = name.strip() if name and name.strip() else src_r.get("name", "Copied Region")
        rect = src_r.get("rect", [0, 0, 100, 100])

        import copy as _copy
        new_region = _copy.deepcopy(src_r)
        new_region.pop("id", None)
        new_region["name"] = new_name

        from screenalert_core.utils.helpers import generate_uuid
        new_region["id"] = generate_uuid()

        new_id = config.add_region_to_thumbnail(tgt_tc["id"], new_region)
        if not new_id:
            return {"error": "Failed to add copied region to target window", "code": 500}

        # Register with monitoring engine
        engine.monitoring_engine.add_region(
            new_id, tgt_tc["id"], new_region,
            global_config=engine._get_global_detection_config(),
        )
        config.save()

        if event_logger:
            event_logger.log("region", "region_copied", "mcp",
                             source_region_id=region_id,
                             window_id=tgt_tc["id"], window_name=tgt_tc.get("window_title", ""),
                             region_id=new_id, region_name=new_name)

        return {"id": new_id, "name": new_name}

    # ── list_alerts ───────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "List all currently active (uncleared) alerts across all windows. "
            "Returns region id, window id, names, and when the alert started."
        )
    )
    def list_alerts() -> List[dict]:
        from screenalert_core.monitoring.region_monitor import STATE_ALERT
        result = []
        for tc in config.get_all_thumbnails():
            tid = tc["id"]
            wname = tc.get("window_title", "")
            for r in tc.get("monitored_regions", []):
                rid = r.get("id", "")
                monitor = engine.monitoring_engine.get_monitor(rid)
                if monitor and monitor.is_alert():
                    result.append({
                        "window_id": tid,
                        "window_name": wname,
                        "region_id": rid,
                        "region_name": r.get("name", ""),
                        "since": getattr(monitor, "_alert_start_time", None),
                    })
        return result

    # ── acknowledge_alert ─────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Mark an active alert region as acknowledged. "
            "Clears the alert state and logs an alert_acknowledged event."
        )
    )
    def acknowledge_alert(region_id: str) -> dict:
        if not region_id:
            return {"error": "region_id is required", "code": 400, "field": "region_id"}

        tc, r = _find_region(config, region_id)
        if not tc:
            return {"error": f"Region not found: {region_id}", "code": 404}

        monitor = engine.monitoring_engine.get_monitor(region_id)
        if not monitor:
            return {"error": "Region monitor not found (is monitoring running?)", "code": 404}

        from screenalert_core.monitoring.region_monitor import STATE_OK
        was_alert = monitor.is_alert()
        monitor._state = STATE_OK
        monitor._alert_start_time = None

        if event_logger:
            event_logger.log("alert", "alert_acknowledged", "mcp",
                             window_id=tc["id"], window_name=tc.get("window_title", ""),
                             region_id=region_id, region_name=r.get("name", ""),
                             was_alert=was_alert)

        return {"ok": True, "was_alert": was_alert}

    # ── get_region_settings ───────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Get all configurable settings for a monitoring region. "
            "Returns each key with current value, type, and description."
        )
    )
    def get_region_settings(region_id: str) -> dict:
        if not region_id:
            return {"error": "region_id is required", "code": 400, "field": "region_id"}

        tc, r = _find_region(config, region_id)
        if not tc:
            return {"error": f"Region not found: {region_id}", "code": 404}

        result = {}
        for key, meta in _REGION_SETTING_META.items():
            entry = dict(meta)
            if key == "rect":
                raw = r.get("rect", [0, 0, 0, 0])
                entry["value"] = (
                    {"x": raw[0], "y": raw[1], "width": raw[2], "height": raw[3]}
                    if isinstance(raw, (list, tuple)) and len(raw) == 4
                    else raw
                )
            elif key == "alert_threshold":
                entry["value"] = r.get("alert_threshold", config.get_default_alert_threshold())
            elif key == "change_detection_method":
                entry["value"] = r.get("change_detection_method", config.get_change_detection_method())
            else:
                entry["value"] = r.get(key)
            result[key] = entry
        return result

    # ── set_region_setting ────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Set a single configurable setting for a monitoring region. "
            "Valid keys: name, rect, enabled, tts_message, sound_file, sound_enabled, "
            "tts_enabled, alert_threshold, change_detection_method. "
            "Returns 422 with valid_values if value is out of range."
        )
    )
    def set_region_setting(
        region_id: str,
        key: str,
        value: Any,
    ) -> dict:
        if not region_id:
            return {"error": "region_id is required", "code": 400, "field": "region_id"}
        if not key:
            return {"error": "key is required", "code": 400, "field": "key"}

        tc, r = _find_region(config, region_id)
        if not tc:
            return {"error": f"Region not found: {region_id}", "code": 404}

        if key not in _REGION_SETTING_META:
            return {
                "error": f"Unknown setting key '{key}'",
                "code": 400,
                "field": "key",
                "valid_keys": list(_REGION_SETTING_META.keys()),
            }

        updates: dict[str, Any] = {}

        if key == "name":
            if not value or not str(value).strip():
                return {"error": "name must be a non-empty string", "code": 422, "field": "value"}
            updates["name"] = str(value).strip()

        elif key == "rect":
            if not isinstance(value, dict):
                return {"error": "rect must be an object {x, y, width, height}",
                        "code": 422, "field": "value"}
            try:
                rx, ry = int(value["x"]), int(value["y"])
                rw, rh = int(value["width"]), int(value["height"])
            except (KeyError, TypeError, ValueError):
                return {"error": "rect must have integer keys x, y, width, height",
                        "code": 422, "field": "value"}
            if rw <= 0 or rh <= 0:
                return {"error": "width and height must be positive", "code": 422, "field": "value"}
            updates["rect"] = [rx, ry, rw, rh]

        elif key == "enabled":
            updates["enabled"] = bool(value)

        elif key in ("tts_message", "sound_file"):
            updates[key] = str(value) if value is not None else ""

        elif key in ("sound_enabled", "tts_enabled"):
            updates[key] = bool(value)

        elif key == "alert_threshold":
            try:
                v = float(value)
            except (TypeError, ValueError):
                return {"error": "alert_threshold must be a float", "code": 422, "field": "value"}
            if not (0.0 <= v <= 1.0):
                return {"error": "alert_threshold must be between 0.0 and 1.0",
                        "code": 422, "field": "value", "valid_range": [0.0, 1.0]}
            updates["alert_threshold"] = v

        elif key == "change_detection_method":
            valid = ["ssim", "phash", "edge_only", "background_subtraction"]
            if value not in valid:
                return {"error": f"change_detection_method must be one of: {', '.join(valid)}",
                        "code": 422, "field": "value", "valid_values": valid}
            updates["change_detection_method"] = value
            # Also update the live monitor detector
            monitor = engine.monitoring_engine.get_monitor(region_id)
            if monitor:
                try:
                    monitor.set_detector(value, engine._get_global_detection_config())
                except Exception as exc:
                    logger.warning("Could not update live detector for region %s: %s", region_id, exc)

        ok = config.update_region(tc["id"], region_id, updates)
        if not ok:
            return {"error": "Failed to update region setting", "code": 500}
        config.save()

        if event_logger:
            event_logger.log("settings", "region_setting_changed", "mcp",
                             window_id=tc["id"], window_name=tc.get("window_title", ""),
                             region_id=region_id, region_name=r.get("name", ""),
                             key=key, value=value)

        return {"ok": True}
