"""
MCP monitoring control tools — pause, resume, mute, status.
"""

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def register(mcp, engine, config, event_logger) -> None:
    """Register monitoring control tools."""

    # ── pause_monitoring ──────────────────────────────────────────────────────

    @mcp.tool(description="Pause region analysis. Overlays stay visible. Alerts will not fire.")
    def pause_monitoring() -> dict:
        engine.set_paused(True)
        if event_logger:
            event_logger.log("monitoring", "monitoring_paused", "mcp")
        return {"ok": True}

    # ── resume_monitoring ─────────────────────────────────────────────────────

    @mcp.tool(description="Resume region analysis after a pause.")
    def resume_monitoring() -> dict:
        engine.set_paused(False)
        if event_logger:
            event_logger.log("monitoring", "monitoring_resumed", "mcp")
        return {"ok": True}

    # ── mute_alerts ───────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Mute all alert sounds and TTS for the given number of seconds (1–3600). "
            "If already muted, extends the mute rather than resetting it. "
            "Returns the ISO timestamp when mute expires."
        )
    )
    def mute_alerts(seconds: int) -> dict:
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            return {"error": "seconds must be an integer", "code": 422, "field": "seconds"}
        if not (1 <= seconds <= 3600):
            return {"error": "seconds must be between 1 and 3600",
                    "code": 422, "field": "seconds", "valid_range": [1, 3600]}

        now = time.time()
        current_mute = config.get_mute_until_ts()
        # Extend if already muted, otherwise start fresh
        base = max(now, float(current_mute))
        new_mute_ts = int(base + seconds)
        config.set_mute_until_ts(new_mute_ts)
        config.save()

        muted_until = datetime.fromtimestamp(new_mute_ts, tz=timezone.utc).isoformat()
        if event_logger:
            event_logger.log("monitoring", "alerts_muted", "mcp",
                             seconds=seconds, muted_until=muted_until)
        return {"ok": True, "muted_until": muted_until}

    # ── get_monitoring_status ─────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Get the current monitoring state. "
            "state values: 'running', 'paused', 'stopped'. "
            "Includes active window/region counts and mute status."
        )
    )
    def get_monitoring_status() -> dict:
        # Determine state
        if not engine.is_running():
            state = "stopped"
        elif hasattr(engine, "paused") and engine.paused:
            state = "paused"
        else:
            state = "running"

        # Mute status
        now = int(time.time())
        mute_ts = config.get_mute_until_ts()
        muted = mute_ts > now
        mute_remaining = max(0, mute_ts - now) if muted else 0

        # Counts
        thumbnails = config.get_all_thumbnails()
        active_windows = sum(1 for tc in thumbnails if engine.is_thumbnail_connected(tc["id"]))
        active_regions = sum(
            len(tc.get("monitored_regions", []))
            for tc in thumbnails
            if engine.is_thumbnail_connected(tc["id"])
        )

        # Uptime from engine start time
        uptime = 0
        if hasattr(engine, "_start_time") and engine._start_time:
            uptime = int(time.time() - engine._start_time)

        return {
            "state": state,
            "muted": muted,
            "mute_remaining_seconds": mute_remaining,
            "uptime_seconds": uptime,
            "active_windows": active_windows,
            "total_windows": len(thumbnails),
            "active_regions": active_regions,
        }
