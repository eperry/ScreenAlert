"""
Centralised logging configuration for ScreenAlert.

All modules obtain their logger via ``logging.getLogger(__name__)``; this
module is the single place that configures the root handler chain and
registers the custom TRACE level.
"""

import io
import logging
import os
import sys
from typing import Optional

from screenalert_core.utils.constants import LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVELS, TRACE

# ---------------------------------------------------------------------------
# Custom TRACE level
# ---------------------------------------------------------------------------

def _register_trace_level() -> None:
    """Register TRACE (level 5) with Python's logging system once."""
    if hasattr(logging, "TRACE"):
        return

    logging.TRACE = TRACE  # type: ignore[attr-defined]
    logging.addLevelName(TRACE, "TRACE")

    def _trace(self: logging.Logger, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    logging.Logger.trace = _trace  # type: ignore[attr-defined]


_register_trace_level()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _level_name_to_int(level_str: str) -> int:
    """Convert a level name string to a logging int, defaulting to ERROR."""
    level_str = (level_str or "ERROR").upper().strip()
    if level_str == "TRACE":
        return TRACE
    level = getattr(logging, level_str, None)
    if isinstance(level, int):
        return level
    return logging.ERROR


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_logging(log_level_str: str = "ERROR", log_dir: Optional[str] = None) -> logging.Logger:
    """Configure the root logger with file and console handlers.

    Args:
        log_level_str: One of TRACE / DEBUG / INFO / WARNING / ERROR.
        log_dir:       Directory for the log file.  If None, no file handler
                       is created.

    Returns:
        The named ``screenalert`` logger for the entry-point module.
    """
    level = _level_name_to_int(log_level_str)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers if called more than once (e.g. tests).
    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.setLevel(level)

    # File handler
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "screenalert.log")
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root_logger.addHandler(fh)
        except Exception as exc:
            print(f"[ScreenAlert] Could not create log file in {log_dir}: {exc}", file=sys.stderr)

    # Console handler — force UTF-8 to avoid cp1252 encoding errors on Windows
    try:
        utf8_stream = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
        ch = logging.StreamHandler(utf8_stream)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root_logger.addHandler(ch)
    except AttributeError:
        # sys.stdout may not have .buffer in some embedded environments
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root_logger.addHandler(ch)

    app_logger = logging.getLogger("screenalert")
    app_logger.setLevel(level)
    return app_logger


# ---------------------------------------------------------------------------
# Runtime level change (no restart required)
# ---------------------------------------------------------------------------

def set_runtime_log_level(level_str: str) -> None:
    """Update all active handlers and the root logger to a new level.

    Safe to call from any thread; Python's logging module uses its own lock.

    Args:
        level_str: One of TRACE / DEBUG / INFO / WARNING / ERROR.
    """
    level = _level_name_to_int(level_str)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        try:
            handler.setLevel(level)
        except Exception:
            pass
    logging.getLogger("screenalert").setLevel(level)
