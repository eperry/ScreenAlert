"""
MCP global settings tools — get_global_settings, set_global_setting.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Metadata for every exposed global setting key
_GLOBAL_SETTING_META = {
    "opacity": {
        "type": "float",
        "description": "Default overlay opacity for all windows",
        "valid_range": [0.2, 1.0],
    },
    "always_on_top": {
        "type": "bool",
        "description": "Overlay windows stay above all other windows",
    },
    "show_borders": {
        "type": "bool",
        "description": "Draw a border around overlay windows",
    },
    "overlay_scaling_mode": {
        "type": "str",
        "description": "How the overlay image is scaled inside its window",
        "valid_values": ["fit", "stretch", "letterbox"],
    },
    "refresh_rate_ms": {
        "type": "int",
        "description": "Monitoring loop polling interval in milliseconds",
        "valid_range": [300, 5000],
    },
    "log_level": {
        "type": "str",
        "description": "Active log verbosity level",
        "valid_values": ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
    },
    "show_overlay_when_unavailable": {
        "type": "bool",
        "description": "Show a placeholder overlay when the source window is unavailable",
    },
    "show_overlay_on_connect": {
        "type": "bool",
        "description": "Automatically show the overlay when a window reconnects",
    },
    "alert_hold_seconds": {
        "type": "float",
        "description": "How long (seconds) alert state is held after a trigger",
        "valid_range": [0, 3600],
    },
    "enable_sound": {
        "type": "bool",
        "description": "Global toggle for alert sounds",
    },
    "enable_tts": {
        "type": "bool",
        "description": "Global toggle for text-to-speech alerts",
    },
    "default_tts_message": {
        "type": "str",
        "description": "TTS message template (supports {window} and {region_name})",
    },
    "suppress_fullscreen": {
        "type": "bool",
        "description": "Suppress alerts while a fullscreen app is in the foreground",
    },
    "auto_discover": {
        "type": "bool",
        "description": "Automatically discover and reconnect known disconnected windows",
    },
    "auto_discover_interval_seconds": {
        "type": "int",
        "description": "How often (seconds) to scan for disconnected windows",
        "valid_range": [10, 300],
    },
    "size_tolerance_px": {
        "type": "int",
        "description": "Pixel tolerance for window size matching on reconnect",
        "valid_range": [0, 500],
    },
    "capture_on_alert": {
        "type": "bool",
        "description": "Save a screenshot when an alert fires",
    },
    "save_alert_diagnostics": {
        "type": "bool",
        "description": "Save diagnostic images (diff, mask) alongside alert captures",
    },
    "event_log_enabled": {
        "type": "bool",
        "description": "Enable JSONL event logging to disk",
    },
    "event_log_max_rows": {
        "type": "int",
        "description": "Maximum number of rows kept in the event log before pruning",
        "valid_range": [100, 100000],
    },
    "mcp_max_connections": {
        "type": "int",
        "description": "Maximum concurrent MCP client connections",
        "valid_range": [1, 20],
    },
}


def _read_value(config, key: str) -> Any:
    getters = {
        "opacity": config.get_opacity,
        "always_on_top": config.get_always_on_top,
        "show_borders": config.get_show_borders,
        "overlay_scaling_mode": config.get_overlay_scaling_mode,
        "refresh_rate_ms": config.get_refresh_rate,
        "log_level": config.get_log_level,
        "show_overlay_when_unavailable": config.get_show_overlay_when_unavailable,
        "show_overlay_on_connect": config.get_show_overlay_on_connect,
        "alert_hold_seconds": config.get_alert_hold_seconds,
        "enable_sound": config.get_enable_sound,
        "enable_tts": config.get_enable_tts,
        "default_tts_message": config.get_default_tts_message,
        "suppress_fullscreen": config.get_suppress_fullscreen,
        "auto_discover": config.get_auto_discovery_enabled,
        "auto_discover_interval_seconds": config.get_auto_discovery_interval_sec,
        "size_tolerance_px": config.get_reconnect_size_tolerance,
        "capture_on_alert": config.get_capture_on_alert,
        "save_alert_diagnostics": config.get_save_alert_diagnostics,
        "event_log_enabled": config.get_event_log_enabled,
        "event_log_max_rows": config.get_event_log_max_rows,
        "mcp_max_connections": config.get_mcp_max_connections,
    }
    fn = getters.get(key)
    return fn() if fn else None


def _write_value(config, engine, event_logger, key: str, value: Any) -> Dict:
    """Validate and apply a single global setting. Returns {ok, error?}."""
    meta = _GLOBAL_SETTING_META[key]

    # ── Type validation ────────────────────────────────────────────────────────
    if meta["type"] == "bool":
        value = bool(value)
    elif meta["type"] == "int":
        try:
            value = int(value)
        except (TypeError, ValueError):
            return {"error": f"{key} must be an integer", "code": 422, "field": "value"}
    elif meta["type"] == "float":
        try:
            value = float(value)
        except (TypeError, ValueError):
            return {"error": f"{key} must be a number", "code": 422, "field": "value"}
    elif meta["type"] == "str":
        value = str(value) if value is not None else ""

    # ── Range / choices ────────────────────────────────────────────────────────
    if "valid_range" in meta:
        lo, hi = meta["valid_range"]
        if not (lo <= value <= hi):
            return {"error": f"{key} must be between {lo} and {hi}",
                    "code": 422, "field": "value", "valid_range": [lo, hi]}
    if "valid_values" in meta:
        if value not in meta["valid_values"]:
            return {"error": f"{key} must be one of: {', '.join(meta['valid_values'])}",
                    "code": 422, "field": "value", "valid_values": meta["valid_values"]}

    # ── Apply ──────────────────────────────────────────────────────────────────
    setters = {
        "opacity": lambda v: config.set_opacity(v),
        "always_on_top": lambda v: config.set_always_on_top(v),
        "show_borders": lambda v: config.set_show_borders(v),
        "overlay_scaling_mode": lambda v: config.set_overlay_scaling_mode(v),
        "refresh_rate_ms": lambda v: config.set_refresh_rate(v),
        "log_level": _apply_log_level,
        "show_overlay_when_unavailable": lambda v: config.set_show_overlay_when_unavailable(v),
        "show_overlay_on_connect": lambda v: config.set_show_overlay_on_connect(v),
        "alert_hold_seconds": lambda v: config.set_alert_hold_seconds(v),
        "enable_sound": lambda v: config.set_enable_sound(v),
        "enable_tts": lambda v: config.set_enable_tts(v),
        "default_tts_message": lambda v: config.set_default_tts_message(v),
        "suppress_fullscreen": lambda v: config.set_suppress_fullscreen(v),
        "auto_discover": lambda v: config.set_auto_discovery_enabled(v),
        "auto_discover_interval_seconds": lambda v: config.set_auto_discovery_interval_sec(v),
        "size_tolerance_px": lambda v: config.set_reconnect_size_tolerance(v),
        "capture_on_alert": lambda v: config.set_capture_on_alert(v),
        "save_alert_diagnostics": lambda v: config.set_save_alert_diagnostics(v),
        "event_log_enabled": _apply_event_log_enabled,
        "event_log_max_rows": _apply_event_log_max_rows,
        "mcp_max_connections": lambda v: config.set_mcp_max_connections(v),
    }

    def _apply_log_level(v):
        config.set_log_level(v)
        # Apply immediately via log_setup if available
        try:
            from screenalert_core.utils.log_setup import set_runtime_log_level
            set_runtime_log_level(v)
        except Exception:
            pass

    def _apply_event_log_enabled(v):
        config.set_event_log_enabled(v)
        if event_logger:
            event_logger.set_enabled(v)

    def _apply_event_log_max_rows(v):
        config.set_event_log_max_rows(v)
        if event_logger:
            event_logger.set_max_rows(v)

    fn = setters.get(key)
    if fn:
        try:
            fn(value)
        except Exception as exc:
            logger.error("Error applying global setting %s=%r: %s", key, value, exc)
            return {"error": f"Failed to apply {key}: {exc}", "code": 500}

    return {"ok": True}


def register(mcp, engine, config, event_logger) -> None:
    """Register global settings MCP tools."""

    # ── get_global_settings ───────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Get all configurable global settings with current values, types, "
            "and valid value ranges. Use set_global_setting to change any of them."
        )
    )
    def get_global_settings() -> Dict:
        result = {}
        for key, meta in _GLOBAL_SETTING_META.items():
            entry = dict(meta)
            entry["value"] = _read_value(config, key)
            result[key] = entry
        return result

    # ── set_global_setting ────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Set a global setting by key. Changes take effect immediately at runtime — "
            "no restart required. "
            "Call get_global_settings first to see valid keys and their types."
        )
    )
    def set_global_setting(key: str, value: Any) -> Dict:
        if not key:
            return {"error": "key is required", "code": 400, "field": "key"}
        if key not in _GLOBAL_SETTING_META:
            return {
                "error": f"Unknown setting key '{key}'",
                "code": 400,
                "field": "key",
                "valid_keys": list(_GLOBAL_SETTING_META.keys()),
            }

        result = _write_value(config, engine, event_logger, key, value)
        if result.get("ok"):
            config.save()
            if event_logger:
                event_logger.log("settings", "global_setting_changed", "mcp",
                                 key=key, value=value)
        return result
