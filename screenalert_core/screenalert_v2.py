#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ScreenAlert v2.0 - Advanced Multibox Monitor with Thumbnails
Entry point for the application
"""

import sys
import logging
import os
from pathlib import Path

# Add workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

from screenalert_core.utils.constants import (
    APP_NAME, APP_VERSION, LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT
)
from screenalert_core.screening_engine import ScreenAlertEngine
from screenalert_core.ui.main_window import ScreenAlertMainWindow


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('screenalert')
    logger.setLevel(log_level)
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    # File handler
    log_file = os.path.join(LOGS_DIR, "screenalert.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(log_level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"{APP_NAME} v{APP_VERSION} Starting")
    logger.info(f"{'='*60}")
    
    return logger


def main():
    """Main entry point"""
    # Setup logging
    logger = setup_logging(verbose=False)
    
    try:
        # Create engine
        logger.info("Initializing ScreenAlert Engine...")
        engine = ScreenAlertEngine()
        
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


if __name__ == "__main__":
    main()
