#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ScreenAlert v2.0.2 - Advanced Multibox Monitor with Thumbnails
Entry point for the application
"""

import sys
import logging
import os
import time
import argparse
import faulthandler
from pathlib import Path

if os.name == "nt":
    import ctypes

# Add workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from screenalert_core.utils.constants import (
    APP_NAME, APP_VERSION, LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT
)
from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.main_window import ScreenAlertMainWindow


_SINGLE_INSTANCE_MUTEX = None
_THREAD_DUMP_FILE = None


def acquire_single_instance_guard() -> bool:
    """Acquire Windows named mutex to ensure a single running instance."""
    global _SINGLE_INSTANCE_MUTEX
    if os.name != "nt":
        return True

    try:
        mutex_name = "Global\\ScreenAlert_SingleInstance"
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        already_exists = ctypes.windll.kernel32.GetLastError() == 183
        if already_exists:
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
            return False
        _SINGLE_INSTANCE_MUTEX = handle
        return True
    except Exception:
        return True


def release_single_instance_guard() -> None:
    """Release Windows named mutex handle if held."""
    global _SINGLE_INSTANCE_MUTEX
    if os.name != "nt":
        return
    if _SINGLE_INSTANCE_MUTEX:
        try:
            ctypes.windll.kernel32.CloseHandle(_SINGLE_INSTANCE_MUTEX)
        except Exception:
            pass
        _SINGLE_INSTANCE_MUTEX = None


def setup_thread_diagnostics(interval_sec: int = 0) -> None:
    """Enable Python thread dump diagnostics to help debug hangs/unresponsiveness."""
    global _THREAD_DUMP_FILE
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        dump_path = os.path.join(LOGS_DIR, "thread_dumps.log")
        _THREAD_DUMP_FILE = open(dump_path, "a", encoding="utf-8")
        faulthandler.enable(file=_THREAD_DUMP_FILE, all_threads=True)
        if interval_sec and interval_sec > 0:
            faulthandler.dump_traceback_later(interval_sec, repeat=True, file=_THREAD_DUMP_FILE)
    except Exception:
        pass


def teardown_thread_diagnostics() -> None:
    """Disable and cleanup thread dump diagnostics resources."""
    global _THREAD_DUMP_FILE
    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass
    try:
        faulthandler.disable()
    except Exception:
        pass
    if _THREAD_DUMP_FILE:
        try:
            _THREAD_DUMP_FILE.close()
        except Exception:
            pass
        _THREAD_DUMP_FILE = None


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging"""
    log_level = logging.DEBUG if verbose else logging.WARNING
    
    # Create logs directory
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    # File handler
    log_file = os.path.join(LOGS_DIR, "screenalert.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(log_level)
    fh.setFormatter(formatter)
    
    # Console handler (force UTF-8 to avoid cp1252 encoding errors)
    import sys, io
    utf8_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    ch = logging.StreamHandler(utf8_stream)
    ch.setLevel(log_level)
    ch.setFormatter(formatter)

    # Configure root logger so ALL module loggers (screenalert_core.*)
    # propagate their output to the same handlers.
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(fh)
    root_logger.addHandler(ch)

    # Clamp very chatty modules so normal operation is readable.
    # Keep this independent of --verbose/--diagnostics to avoid multi-MB logs.
    logging.getLogger("screenalert_core.rendering.overlay_manager").setLevel(logging.WARNING)
    logging.getLogger("screenalert_core.rendering.overlay_window").setLevel(logging.WARNING)
    logging.getLogger("screenalert_core.rendering.dwm_backend").setLevel(logging.WARNING)
    logging.getLogger("screenalert_core.core.window_manager").setLevel(logging.INFO)
    logging.getLogger("screenalert_core.ui.main_window").setLevel(logging.INFO)
    
    # Also configure the named logger for screenalert.py itself
    logger = logging.getLogger('screenalert')
    logger.setLevel(log_level)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"{APP_NAME} v{APP_VERSION} Starting")
    logger.info(f"{'='*60}")
    
    return logger


def parse_args():
    """Parse CLI arguments for diagnostics/headless/config override."""
    parser = argparse.ArgumentParser(description="ScreenAlert")
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON")
    parser.add_argument("--headless", action="store_true", help="Run monitoring without UI")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--diagnostics", action="store_true", help="Enable diagnostics mode")
    parser.add_argument("--thread-dump-interval", type=int, default=0,
                        help="Dump all thread stacks every N seconds to logs/thread_dumps.log")
    parser.add_argument("--dump-threads-now", action="store_true",
                        help="Write one immediate thread dump and continue startup")
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    if not acquire_single_instance_guard():
        print("ScreenAlert is already running. Exiting duplicate instance.")
        return

    # Thread diagnostics can be enabled independently or via diagnostics mode.
    dump_interval = args.thread_dump_interval or (30 if args.diagnostics else 0)
    setup_thread_diagnostics(interval_sec=dump_interval)
    if args.dump_threads_now:
        try:
            faulthandler.dump_traceback(file=_THREAD_DUMP_FILE, all_threads=True)
        except Exception:
            pass

    # Setup logging
    logger = setup_logging(verbose=bool(args.verbose or args.diagnostics))
    
    try:
        # Create engine
        logger.info("Initializing ScreenAlert Engine...")
        engine = ScreenAlertEngine(config_path=args.config)

        if args.diagnostics:
            engine.config.set_diagnostics_enabled(True)
            engine.config.set_verbose_logging(True)
            engine.config.save()
            logger.info("Diagnostics mode enabled")

        if args.headless:
            engine.config.set_headless(True)
            engine.config.save()
            logger.info("Starting in headless mode")
            engine.start()
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("Headless mode interrupted by user")
                engine.stop()
            return
        
        # Create and run UI
        logger.info("Creating main window...")
        app = ScreenAlertMainWindow(engine)
        
        logger.info("Running main window...")
        app.run()
        
        # Cleanup
        logger.info("Shutting down...")
        engine.stop()
        
        logger.info(f"{APP_NAME} v{APP_VERSION} Exited successfully")
    
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        teardown_thread_diagnostics()
        release_single_instance_guard()


if __name__ == "__main__":
    main()
