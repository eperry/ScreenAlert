"""Engine event handling mixin for ScreenAlertMainWindow.

Decouples alert / region-change / window-lost event processing from the
main window class.  Expects the host class to provide:
  self._event_lock              – threading.Lock
  self._pending_alert_events    – dict
  self._pending_region_change_events – dict
  self._pending_window_lost_events   – dict
  self._ui_event_flush_scheduled – bool
  self.root                     – tk.Tk
  self.config                   – ConfigManager
  self.status_var               – tk.StringVar
  self._mark_dirty(tid, rid, status, thumbnail)
  self._activate_alert_focus_window()
"""

import logging
import threading

logger = logging.getLogger(__name__)


class EngineEventMixin:
    """Coalesced engine → UI event delivery."""

    def _enqueue_engine_event(self, event_type: str, *args) -> None:
        """Coalesce high-frequency engine events and flush once on the UI thread."""
        with self._event_lock:
            if event_type == "alert":
                thumbnail_id, region_id, region_name = args
                self._pending_alert_events[(thumbnail_id, region_id)] = region_name
            elif event_type == "change":
                thumbnail_id, region_id, state = args
                self._pending_region_change_events[(thumbnail_id, region_id)] = state
            elif event_type == "window_lost":
                thumbnail_id, window_title = args
                self._pending_window_lost_events[thumbnail_id] = window_title

            if self._ui_event_flush_scheduled:
                return
            self._ui_event_flush_scheduled = True

        try:
            self.root.after(0, self._flush_engine_events)
        except Exception as exc:
            logger.warning("Failed scheduling engine event flush: %s", exc)
            with self._event_lock:
                self._ui_event_flush_scheduled = False

    def _flush_engine_events(self) -> None:
        """Apply all coalesced engine events on the Tk UI thread."""
        with self._event_lock:
            alerts = list(self._pending_alert_events.items())
            changes = list(self._pending_region_change_events.items())
            lost_windows = list(self._pending_window_lost_events.items())
            self._pending_alert_events.clear()
            self._pending_region_change_events.clear()
            self._pending_window_lost_events.clear()
            self._ui_event_flush_scheduled = False

        if self.config.get_diagnostics_enabled():
            logger.debug(
                "[UI EVENT FLUSH] alerts=%d changes=%d window_lost=%d",
                len(alerts), len(changes), len(lost_windows),
            )

        for (thumbnail_id, region_id), region_name in alerts:
            try:
                self._on_alert(thumbnail_id, region_id, region_name)
            except Exception as exc:
                logger.error("Error handling alert event [%s/%s]: %s", thumbnail_id, region_id, exc,
                             exc_info=True)

        for (thumbnail_id, region_id), state in changes:
            try:
                self._on_region_change(thumbnail_id, region_id, state)
            except Exception as exc:
                logger.error("Error handling region change [%s/%s]: %s", thumbnail_id, region_id, exc,
                             exc_info=True)

        for thumbnail_id, window_title in lost_windows:
            try:
                self._on_window_lost(thumbnail_id, window_title)
            except Exception as exc:
                logger.error("Error handling window lost [%s]: %s", thumbnail_id, exc, exc_info=True)

    def _on_alert(self, thumbnail_id: str, region_id: str, region_name: str) -> None:
        """Handle an alert event: activate focus window, update status and dirty flags."""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("alert", thumbnail_id, region_id, region_name)
            return

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return

        title = thumbnail.get("window_title", "Unknown")
        logger.info("[ALERT EVENT] %s - %s (region_id=%s)", title, region_name, region_id)

        self._activate_alert_focus_window()
        self._mark_dirty(thumbnail_id, region_id, status="alert", thumbnail=True)
        self.status_var.set(f"🚨 ALERT: {title} - {region_name}")

    def _on_region_change(self, thumbnail_id: str, region_id: str, state: str = "ok") -> None:
        """Handle a region state change from the monitoring engine."""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("change", thumbnail_id, region_id, state)
            return

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail:
            return

        region_name = "Unknown"
        for region in thumbnail.get("monitored_regions", []):
            if region.get("id") == region_id:
                region_name = region.get("name", "Unknown")
                break

        logger.debug("[STATE EVENT] %s - %s -> %s",
                     thumbnail.get("window_title", "Unknown"), region_name, state)
        self._mark_dirty(thumbnail_id, region_id, status=state, thumbnail=True)

    def _on_window_lost(self, thumbnail_id: str, window_title: str) -> None:
        """Handle a lost window — mark all its regions as unavailable."""
        if threading.current_thread() is not threading.main_thread():
            self._enqueue_engine_event("window_lost", thumbnail_id, window_title)
            return

        logger.warning("Window lost: %s", window_title)
        self.status_var.set(f"Window lost: {window_title}")

        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if thumbnail:
            for region in thumbnail.get("monitored_regions", []):
                region_id = region.get("id", "")
                if region_id:
                    self._mark_dirty(thumbnail_id, region_id, status="unavailable", thumbnail=True)
