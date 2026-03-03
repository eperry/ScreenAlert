"""ScreenAlert with Dear PyGui - GPU-accelerated, flicker-free UI"""

import logging
import sys
from pathlib import Path

# Setup logging
log_dir = Path.home() / "AppData" / "Roaming" / "ScreenAlert"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "screenalert.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    try:
        logger.info("=" * 80)
        logger.info("ScreenAlert v2.0 - Starting with Dear PyGui (GPU-accelerated)")
        logger.info("=" * 80)
        
        from screenalert_core.screening_engine import ScreenAlertEngine
        from screenalert_core.ui.main_window_dpg_complete import ScreenAlertMainWindowDPG
        
        # Create engine
        engine = ScreenAlertEngine()
        logger.info("Engine initialized")
        
        # Create and run UI
        window = ScreenAlertMainWindowDPG(engine)
        logger.info("Main window created - starting GPU-accelerated UI")
        window.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("ScreenAlert shutdown complete")

if __name__ == "__main__":
    main()
