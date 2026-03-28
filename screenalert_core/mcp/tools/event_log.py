"""
MCP event log tools — query, summarise, clear the JSONL event log.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def register(mcp, engine, config, event_logger) -> None:
    """Register event log MCP tools."""

    # ── get_event_log ─────────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Query the ScreenAlert event log. "
            "Use after_id for cursor-based polling (pass the id of the last seen event). "
            "Use offset for page-based browsing. "
            "Filter by since (ISO datetime string), category, window_id, or region_id. "
            "Returns {events, total, has_more}."
        )
    )
    def get_event_log(
        limit: int = 100,
        offset: int = 0,
        after_id: str = "",
        since: str = "",
        category: str = "",
        window_id: str = "",
        region_id: str = "",
    ) -> dict:
        if not event_logger:
            return {"events": [], "total": 0, "has_more": False,
                    "note": "Event logging is not enabled"}

        limit = max(1, min(1000, int(limit)))
        offset = max(0, int(offset))

        return event_logger.query(
            limit=limit,
            offset=offset,
            after_id=after_id or None,
            since=since or None,
            category=category or None,
            window_id=window_id or None,
            region_id=region_id or None,
        )

    # ── get_event_summary ─────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Get aggregated event counts by category, event name, and window. "
            "Optional since parameter limits to events after that ISO datetime. "
            "Includes alerts_with_captures count."
        )
    )
    def get_event_summary(since: str = "") -> dict:
        if not event_logger:
            return {"total": 0, "note": "Event logging is not enabled"}

        return event_logger.summary(since=since or None)

    # ── clear_event_log ───────────────────────────────────────────────────────

    @mcp.tool(
        description=(
            "Clear all events or only events of a specific category from the event log. "
            "The clear action itself is logged as a system event before deletion. "
            "Returns the number of entries deleted."
        )
    )
    def clear_event_log(category: str = "") -> dict:
        if not event_logger:
            return {"entries_deleted": 0, "note": "Event logging is not enabled"}

        deleted = event_logger.clear(category=category or None)
        return {"entries_deleted": deleted}
