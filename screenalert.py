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
from typing import Optional

if os.name == "nt":
    import ctypes

# Add workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from screenalert_core.utils.constants import (
    APP_NAME, APP_VERSION, LOGS_DIR, EVENT_LOG_FILE,
)
from screenalert_core.utils.log_setup import setup_logging, set_runtime_log_level  # noqa: F401
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


# setup_logging and set_runtime_log_level are imported from log_setup above.


def parse_args():
    """Parse CLI arguments for diagnostics/headless/config override."""
    parser = argparse.ArgumentParser(description="ScreenAlert")
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON")
    parser.add_argument("--headless", action="store_true", help="Run monitoring without UI")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable DEBUG logging (shorthand for --log-level DEBUG)")
    parser.add_argument("--log-level", type=str, default=None,
                        choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
                        metavar="LEVEL",
                        help="Log level: TRACE/DEBUG/INFO/WARNING/ERROR (overrides saved setting)")
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

    # Determine log level: CLI flag > --verbose/--diagnostics shorthand > config file
    # We need to load config first to read the saved log level, but logging
    # must be set up before the engine so early messages are captured.
    # Solution: do a lightweight config peek, then init properly after engine loads.
    cli_level = None  # type: Optional[str]
    if args.log_level:
        cli_level = args.log_level.upper()
    elif args.verbose or args.diagnostics:
        cli_level = "DEBUG"

    # Bootstrap logging at the CLI-requested level (or ERROR if not specified).
    # The real saved level will be applied once the engine/config is loaded.
    bootstrap_level = cli_level or "ERROR"
    logger = setup_logging(log_level_str=bootstrap_level, log_dir=LOGS_DIR)

    try:
        # Create engine
        logger.info("Initializing ScreenAlert Engine...")
        engine = ScreenAlertEngine(config_path=args.config)

        # Apply final log level: CLI overrides config, otherwise use saved value
        final_level = cli_level or engine.config.get_log_level()
        if final_level != bootstrap_level:
            set_runtime_log_level(final_level)
        logger.info("%s v%s starting (log_level=%s)", APP_NAME, APP_VERSION, final_level)

        if args.diagnostics:
            engine.config.set_diagnostics_enabled(True)
            engine.config.set_log_level("DEBUG")
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
        
        # Start event logger
        from screenalert_core.mcp.event_logger import EventLogger
        event_logger = EventLogger(
            log_path=EVENT_LOG_FILE,
            max_rows=engine.config.get_event_log_max_rows(),
            enabled=engine.config.get_event_log_enabled(),
        )
        event_logger.start()
        event_logger.log("system", "app_started", "screenalert",
                         version=APP_VERSION)
        engine.event_logger = event_logger

        # Start MCP server
        from screenalert_core.mcp.server import MCPServer
        mcp_server = MCPServer(engine=engine, config=engine.config,
                               event_logger=event_logger)
        mcp_server.start()

        # Create and run UI
        logger.info("Creating main window...")
        app = ScreenAlertMainWindow(engine)
        app.set_mcp_server(mcp_server)

        logger.info("Running main window...")
        app.run()

        # Cleanup
        logger.info("Shutting down...")
        mcp_server.stop()
        event_logger.log("system", "app_stopped", "screenalert")
        event_logger.stop()
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
