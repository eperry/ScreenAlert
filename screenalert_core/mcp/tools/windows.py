"""
MCP window tools — list, add, remove, reconnect, inspect, and configure monitored windows.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Keys valid for set_window_setting
_WINDOW_SETTING_META = {
    "name": {
        "type": "str",
        "description": "Display name / window title used for matching",
    },
    "overlay_visible": {
        "type": "bool",
        "description": "Whether the overlay thumbnail is currently visible",
    },
    "opacity": {
        "type": "float",
        "description": "Overlay opacity (0.2–1.0)",
        "valid_range": [0.2, 1.0],
    },
    "always_on_top": {
        "type": "bool",
        "description": "Overlay window stays above other windows",
    },
    "show_border": {
        "type": "bool",
        "description": "Draw a border around the overlay",
    },
    "window_slot": {
        "type": "int|null",
        "description": "Assigned slot number (null to unassign)",
    },
    "enabled": {
        "type": "bool",
        "description": "Whether this window is actively monitored",
    },
}


def _resolve_window(config, engine, window_id: Optional[str], window_name: Optional[str]) -> Any:
    """
    Return (thumbnail_config, error_dict).
    Resolves by window_id first, then by case-insensitive partial name match.
    On ambiguous name match returns error with 409.
    """
    if window_id:
        tc = config.get_thumbnail(window_id)
        if not tc:
            return None, {"error": f"Window not found: {window_id}", "code": 404}
        return tc, None

    if not window_name:
        return None, {"error": "window_id or window_name is required", "code": 400, "field": "window_id"}

    needle = window_name.lower()
    matches = [
        t for t in config.get_all_thumbnails()
        if needle in t.get("window_title", "").lower()
    ]
    if not matches:
        return None, {"error": f"No window matching '{window_name}'", "code": 404}
    if len(matches) > 1:
        return None, {
            "error": f"Ambiguous name '{window_name}' — {len(matches)} matches",
            "code": 409,
            "matches": [{"id": m["id"], "name": m.get("window_title")} for m in matches],
        }
    return matches[0], None


def _find_region_owner(config, region_id: str) -> Optional[Dict]:
    """Return the thumbnail that owns region_id, or None."""
    for tc in config.get_all_thumbnails():
        for r in tc.get("monitored_regions", []):
            if r.get("id") == region_id:
                return tc
    return None


def register(mcp, engine, config, event_logger) -> None:
    """Register all window-related MCP tools onto the FastMCP instance."""

    # ── list_windows ──────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "List all monitored windows with their current connection status. "
            "status values: 'connected', 'disconnected'. "
            "Optional filter matches against window name (case-insensitive substring)."
        )
    )
    def list_windows(filter: str = "") -> list:
        thumbnails = config.get_all_thumbnails()
        result = []
        for tc in thumbnails:
            tid = tc["id"]
            name = tc.get("window_title", "")
            if filter and filter.lower() not in name.lower():
                continue
            connected = engine.is_thumbnail_connected(tid)
            result.append({
                "id": tid,
                "name": name,
                "status": "connected" if connected else "disconnected",
                "overlay_visible": tc.get("overlay_visible", tc.get("overview_visible", True)),
                "hwnd": tc.get("window_hwnd"),
                "slot": tc.get("window_slot"),
                "enabled": tc.get("enabled", True),
                "region_count": len(tc.get("monitored_regions", [])),
            })
        return result

    # ── find_desktop_windows ──────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Enumerate open desktop windows available to add to monitoring. "
            "filter matches against window title (case-insensitive substring). "
            "limit caps results (1–200, default 50)."
        )
    )
    def find_desktop_windows(filter: str = "", limit: int = 50) -> list:
        limit = max(1, min(200, int(limit)))
        windows = engine.window_manager.get_window_list(use_cache=False)
        already_monitored = {tc.get("window_hwnd") for tc in config.get_all_thumbnails()}

        result = []
        for w in windows:
            title = w.get("title", "")
            if filter and filter.lower() not in title.lower():
                continue
            hwnd = w.get("hwnd")
            size = w.get("size")
            result.append({
                "hwnd": hwnd,
                "title": title,
                "class": w.get("class", ""),
                "size": {"width": size[0], "height": size[1]} if size else None,
                "already_monitored": hwnd in already_monitored,
            })
            if len(result) >= limit:
                break
        return result

    # ── add_window ────────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Add a desktop window to ScreenAlert monitoring. "
            "Provide the window title; hwnd is optional (used directly if given, "
            "otherwise ScreenAlert searches the desktop for a matching title). "
            "Returns the new window id."
        )
    )
    def add_window(title: str, hwnd: Optional[int] = None) -> Dict:
        if not title or not title.strip():
            return {"error": "title is required", "code": 400, "field": "title"}

        # Reject duplicates
        for tc in config.get_all_thumbnails():
            if tc.get("window_title", "").strip().lower() == title.strip().lower():
                return {
                    "error": f"A window named '{title}' is already monitored",
                    "code": 409,
                    "existing_id": tc["id"],
                }

        if hwnd is None:
            win = engine.window_manager.find_window_by_title(title)
            if not win:
                return {"error": f"No desktop window found matching '{title}'", "code": 404}
            hwnd = win.get("hwnd")
            if not hwnd:
                return {"error": f"Could not resolve hwnd for '{title}'", "code": 404}

        thumbnail_id = engine.add_thumbnail(title.strip(), hwnd)
        if not thumbnail_id:
            return {"error": "Failed to add window — possible duplicate or engine error", "code": 500}

        if event_logger:
            event_logger.log("window", "window_added", "mcp",
                             window_id=thumbnail_id, window_name=title.strip(), hwnd=hwnd)

        return {"id": thumbnail_id, "name": title.strip()}

    # ── remove_window ─────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Remove a monitored window and all its regions. "
            "DESTRUCTIVE — irreversible. "
            "Pass confirm=false (default) for a dry-run preview showing what would be deleted. "
            "Pass confirm=true to execute the deletion."
        )
    )
    def remove_window(
        window_id: str = "",
        window_name: str = "",
        confirm: bool = False,
    ) -> Dict:
        tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
        if err:
            return err

        region_count = len(tc.get("monitored_regions", []))
        if not confirm:
            return {
                "dry_run": True,
                "id": tc["id"],
                "name": tc.get("window_title", ""),
                "regions_count": region_count,
                "message": (
                    f"Would delete window '{tc.get('window_title')}' "
                    f"and {region_count} region(s). Pass confirm=true to execute."
                ),
            }

        wname = tc.get("window_title", "")
        wid = tc["id"]
        ok = engine.remove_thumbnail(wid)
        if not ok:
            return {"error": "Failed to remove window", "code": 500}

        if event_logger:
            event_logger.log("window", "window_removed", "mcp",
                             window_id=wid, window_name=wname,
                             regions_deleted=region_count)

        return {"ok": True, "regions_deleted": region_count}

    # ── reconnect_window ──────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Force ScreenAlert to attempt reconnection to a specific monitored window. "
            "result values: 'already_valid', 'reconnected', 'failed', 'missing'."
        )
    )
    def reconnect_window(window_id: str = "", window_name: str = "") -> Dict:
        tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
        if err:
            return err

        result = engine.reconnect_window(tc["id"])
        return {"result": result, "window_id": tc["id"], "name": tc.get("window_title")}

    # ── reconnect_all_windows ─────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Force ScreenAlert to attempt reconnection to all disconnected windows. "
            "Returns summary counts: total, reconnected, failed, already_valid."
        )
    )
    def reconnect_all_windows() -> Dict:
        summary = engine.reconnect_all_windows()
        return summary

    # ── get_window_settings ───────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Get all configurable settings for a specific monitored window. "
            "Returns each setting key with its current value, type, and description."
        )
    )
    def get_window_settings(window_id: str = "", window_name: str = "") -> Dict:
        tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
        if err:
            return err

        result = {}
        for key, meta in _WINDOW_SETTING_META.items():
            entry = dict(meta)
            if key == "name":
                entry["value"] = tc.get("window_title", "")
            elif key == "overlay_visible":
                entry["value"] = tc.get("overlay_visible", tc.get("overview_visible", True))
            elif key == "opacity":
                entry["value"] = tc.get("opacity", config.get_opacity())
            elif key == "always_on_top":
                entry["value"] = tc.get("always_on_top", config.get_always_on_top())
            elif key == "show_border":
                entry["value"] = tc.get("show_border", config.get_show_borders())
            elif key == "window_slot":
                entry["value"] = tc.get("window_slot")
            elif key == "enabled":
                entry["value"] = tc.get("enabled", True)
            result[key] = entry
        return result

    # ── set_window_setting ────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Set a single configurable setting for a monitored window. "
            "Valid keys: name, overlay_visible, opacity, always_on_top, show_border, window_slot, enabled. "
            "Returns 422 with valid_values if the value is out of range."
        )
    )
    def set_window_setting(
        window_id: str = "",
        window_name: str = "",
        key: str = "",
        value: Any = None,
    ) -> Dict:
        tc, err = _resolve_window(config, engine, window_id or None, window_name or None)
        if err:
            return err

        if key not in _WINDOW_SETTING_META:
            return {
                "error": f"Unknown setting key '{key}'",
                "code": 400,
                "field": "key",
                "valid_keys": list(_WINDOW_SETTING_META.keys()),
            }

        wid = tc["id"]
        wname = tc.get("window_title", "")
        updates: Dict[str, Any] = {}

        if key == "name":
            if not value or not str(value).strip():
                return {"error": "name must be a non-empty string", "code": 422, "field": "value"}
            updates["window_title"] = str(value).strip()

        elif key == "overlay_visible":
            v = bool(value)
            updates["overlay_visible"] = v
            # Also update live renderer state
            try:
                engine.renderer.set_thumbnail_user_visibility(wid, v)
            except Exception:
                pass

        elif key == "opacity":
            try:
                v = float(value)
            except (TypeError, ValueError):
                return {"error": "opacity must be a float", "code": 422, "field": "value"}
            if not (0.2 <= v <= 1.0):
                return {"error": "opacity must be between 0.2 and 1.0", "code": 422,
                        "field": "value", "valid_range": [0.2, 1.0]}
            updates["opacity"] = v
            try:
                engine.renderer.set_thumbnail_opacity(wid, v)
            except Exception:
                pass

        elif key == "always_on_top":
            updates["always_on_top"] = bool(value)

        elif key == "show_border":
            updates["show_border"] = bool(value)

        elif key == "window_slot":
            if value is None:
                updates["window_slot"] = None
            else:
                try:
                    updates["window_slot"] = int(value)
                except (TypeError, ValueError):
                    return {"error": "window_slot must be an integer or null", "code": 422, "field": "value"}

        elif key == "enabled":
            updates["enabled"] = bool(value)

        ok = config.update_thumbnail(wid, updates)
        if not ok:
            return {"error": "Failed to update window setting", "code": 500}
        config.save()

        if event_logger:
            event_logger.log("settings", "window_setting_changed", "mcp",
                             window_id=wid, window_name=wname, key=key, value=value)

        return {"ok": True}
