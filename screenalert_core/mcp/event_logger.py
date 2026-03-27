"""
ScreenAlert MCP Event Logger

Appends structured events to a JSONL file (one JSON object per line).
In-memory ring buffer flushes to disk every 5 seconds or every 50 events.
Rotation trims oldest entries when max_rows is exceeded.
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Flush triggers
_FLUSH_INTERVAL_SECONDS = 5
_FLUSH_BATCH_SIZE = 50


class EventLogger:
    """
    Thread-safe JSONL event logger.

    Usage:
        el = EventLogger(path, max_rows=5000, enabled=True)
        el.start()
        el.log("alert", "region_alert", "engine",
                window_id="abc", window_name="EVE", region_id="def",
                previous_state="ok", new_state="alert")
        el.stop()
    """

    def __init__(self, log_path: str, max_rows: int = 5000, enabled: bool = True):
        self._path = log_path
        self._max_rows = max_rows
        self._enabled = enabled

        self._buffer: List[Dict] = []
        self._lock = threading.Lock()
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background flush thread."""
        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="EventLogger-flush"
        )
        self._flush_thread.start()
        logger.debug("EventLogger started: path=%s max_rows=%s", self._path, self._max_rows)

    def stop(self) -> None:
        """Flush remaining buffer and stop the background thread."""
        self._stop_event.set()
        self._flush_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=10)
        self._flush_to_disk()
        logger.debug("EventLogger stopped")

    # ── Public API ────────────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_max_rows(self, max_rows: int) -> None:
        self._max_rows = max(100, int(max_rows))

    def log(self, category: str, event: str, source: str, **kwargs: Any) -> Optional[str]:
        """
        Append an event to the log.

        Required: category, event, source.
        All additional kwargs become top-level fields in the event object.
        Returns the event id, or None if logging is disabled.
        """
        if not self._enabled:
            return None

        event_id = str(uuid.uuid4())
        entry = {
            "id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "event": event,
            "source": source,
            **kwargs,
        }

        with self._lock:
            self._buffer.append(entry)
            should_flush = len(self._buffer) >= _FLUSH_BATCH_SIZE

        if should_flush:
            self._flush_event.set()

        return event_id

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        after_id: Optional[str] = None,
        since: Optional[str] = None,
        category: Optional[str] = None,
        window_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> Dict:
        """
        Query the event log. Flushes the in-memory buffer first so results
        include all recent events.

        Returns {"events": [...], "total": int, "has_more": bool}
        """
        self._flush_to_disk()
        events = self._read_all()

        # Filter
        if since:
            events = [e for e in events if e.get("timestamp", "") >= since]
        if category:
            events = [e for e in events if e.get("category") == category]
        if window_id:
            events = [e for e in events if e.get("window_id") == window_id]
        if region_id:
            events = [e for e in events if e.get("region_id") == region_id]

        # Cursor: skip everything up to and including after_id
        if after_id:
            idx = next((i for i, e in enumerate(events) if e.get("id") == after_id), None)
            if idx is not None:
                events = events[idx + 1:]

        total = len(events)

        # Offset + limit
        page = events[offset: offset + limit]

        return {
            "events": page,
            "total": total,
            "has_more": (offset + limit) < total,
        }

    def summary(self, since: Optional[str] = None) -> Dict:
        """
        Return aggregated counts by category, event name, and window.
        """
        self._flush_to_disk()
        events = self._read_all()

        if since:
            events = [e for e in events if e.get("timestamp", "") >= since]

        counts_by_category: Dict[str, int] = {}
        counts_by_event: Dict[str, int] = {}
        counts_by_window: Dict[str, int] = {}
        alerts_with_captures = 0

        for e in events:
            cat = e.get("category", "unknown")
            evt = e.get("event", "unknown")
            wname = e.get("window_name")

            counts_by_category[cat] = counts_by_category.get(cat, 0) + 1
            counts_by_event[evt] = counts_by_event.get(evt, 0) + 1
            if wname:
                counts_by_window[wname] = counts_by_window.get(wname, 0) + 1
            if cat == "alert" and evt == "region_alert" and e.get("capture_file"):
                alerts_with_captures += 1

        return {
            "total": len(events),
            "counts_by_category": counts_by_category,
            "counts_by_event": counts_by_event,
            "counts_by_window": counts_by_window,
            "alerts_with_captures": alerts_with_captures,
        }

    def clear(self, category: Optional[str] = None) -> int:
        """
        Clear all events or only a specific category.
        Returns the number of entries deleted.
        The clear action is logged BEFORE deletion.
        """
        self._flush_to_disk()
        events = self._read_all()

        if category:
            kept = [e for e in events if e.get("category") != category]
            deleted = len(events) - len(kept)
        else:
            kept = []
            deleted = len(events)

        # Log the clear before writing (so the action itself is in the new log)
        clear_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": "system",
            "event": "event_log_cleared",
            "source": "user",
            "category_cleared": category,
            "entries_deleted": deleted,
        }
        kept.append(clear_entry)

        self._write_all(kept)
        return deleted

    # ── Internal ──────────────────────────────────────────────────────────────

    def _flush_loop(self) -> None:
        """Background thread: flush on interval or when signalled."""
        while not self._stop_event.is_set():
            self._flush_event.wait(timeout=_FLUSH_INTERVAL_SECONDS)
            self._flush_event.clear()
            try:
                self._flush_to_disk()
            except Exception as exc:
                logger.error("EventLogger flush error: %s", exc, exc_info=True)

    def _flush_to_disk(self) -> None:
        """Write buffered events to the JSONL file and trim if needed."""
        with self._lock:
            if not self._buffer:
                return
            to_write = list(self._buffer)
            self._buffer.clear()

        if not to_write:
            return

        os.makedirs(os.path.dirname(self._path), exist_ok=True)

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                for entry in to_write:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("EventLogger write error: %s", exc, exc_info=True)
            # Put events back in buffer so they aren't lost
            with self._lock:
                self._buffer = to_write + self._buffer
            return

        self._trim_if_needed()

    def _trim_if_needed(self) -> None:
        """Trim oldest entries if file exceeds max_rows. Runs on background thread."""
        try:
            events = self._read_all()
            if len(events) <= self._max_rows:
                return
            trimmed = events[-self._max_rows:]
            self._write_all(trimmed)
            logger.debug(
                "EventLogger trimmed %d entries (kept %d)",
                len(events) - len(trimmed), len(trimmed)
            )
        except Exception as exc:
            logger.error("EventLogger trim error: %s", exc, exc_info=True)

    def _read_all(self) -> List[Dict]:
        """Read and parse all events from the JSONL file."""
        if not os.path.exists(self._path):
            return []
        events = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("EventLogger: skipping malformed line")
        except Exception as exc:
            logger.error("EventLogger read error: %s", exc, exc_info=True)
        return events

    def _write_all(self, events: List[Dict]) -> None:
        """Overwrite the JSONL file with the given events list."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                for entry in events:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("EventLogger write_all error: %s", exc, exc_info=True)
