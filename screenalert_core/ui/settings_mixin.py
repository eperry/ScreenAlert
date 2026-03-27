"""Runtime settings application mixin for ScreenAlertMainWindow.

Expects the host class to provide:
  self.config               – ConfigManager
  self.engine               – ScreenAlertEngine
  self.root                 – tk.Tk
  self._theme_preset        – str
  self._current_theme       – str
  self._pending_runtime_settings – dict | None
  self._runtime_apply_scheduled  – bool
  self._last_applied_runtime_settings – dict | None
  self.set_theme_preset(name)
  self.set_high_contrast(flag)
"""

import logging
from typing import Dict, Optional

from screenalert_core.utils.log_setup import set_runtime_log_level

logger = logging.getLogger(__name__)


class SettingsMixin:
    """Coalesced runtime settings application for the main window."""

    def _apply_settings_realtime(self, settings: Dict) -> None:
        """Apply settings that can take effect at runtime without restart."""
        if "theme_preset" in settings:
            self.set_theme_preset(str(settings.get("theme_preset", self._theme_preset)))
        elif "high_contrast" in settings:
            self.set_high_contrast(
                bool(settings.get("high_contrast", self._current_theme == "high-contrast"))
            )
        self._schedule_runtime_settings_apply(settings)

    def _schedule_runtime_settings_apply(self, settings: Dict) -> None:
        """Coalesce runtime setting updates to keep the UI responsive during rapid Apply actions."""
        runtime_payload = {
            "opacity": float(settings.get("opacity", self.config.get_opacity())),
            "always_on_top": bool(settings.get("always_on_top", self.config.get_always_on_top())),
            "show_borders": bool(settings.get("show_borders", self.config.get_show_borders())),
            "show_overlay_when_unavailable": bool(
                settings.get(
                    "show_overlay_when_unavailable",
                    self.config.get_show_overlay_when_unavailable(),
                )
            ),
            "overlay_scaling_mode": settings.get(
                "overlay_scaling_mode",
                self.config.get_overlay_scaling_mode(),
            ),
        }
        # Include log_level so it can be applied immediately in _flush
        if "log_level" in settings:
            runtime_payload["log_level"] = settings["log_level"]

        self._pending_runtime_settings = runtime_payload
        if self._runtime_apply_scheduled:
            return
        self._runtime_apply_scheduled = True
        self.root.after_idle(self._flush_runtime_settings_apply)

    def _flush_runtime_settings_apply(self) -> None:
        """Apply the latest queued runtime settings exactly once."""
        self._runtime_apply_scheduled = False
        payload: Optional[Dict] = self._pending_runtime_settings
        self._pending_runtime_settings = None
        if not payload:
            return
        if payload == self._last_applied_runtime_settings:
            return

        try:
            self.engine.apply_runtime_settings(
                opacity=float(payload.get("opacity", self.config.get_opacity())),
                always_on_top=bool(payload.get("always_on_top", self.config.get_always_on_top())),
                show_borders=bool(payload.get("show_borders", self.config.get_show_borders())),
                show_overlay_when_unavailable=bool(
                    payload.get(
                        "show_overlay_when_unavailable",
                        self.config.get_show_overlay_when_unavailable(),
                    )
                ),
                overlay_scaling_mode=payload.get(
                    "overlay_scaling_mode",
                    self.config.get_overlay_scaling_mode(),
                ),
            )

            # Apply log level immediately — no restart needed
            if "log_level" in payload:
                try:
                    set_runtime_log_level(payload["log_level"])
                    logger.info("Log level changed to %s", payload["log_level"])
                except Exception as log_err:
                    logger.warning("Failed to apply log level change: %s", log_err)

            self._last_applied_runtime_settings = dict(payload)

        except Exception as exc:
            logger.error("Error applying runtime settings: %s", exc, exc_info=True)
