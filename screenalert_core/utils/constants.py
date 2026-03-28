"""Application constants and configuration"""

import os
import platform

# Application Information
APP_NAME = "ScreenAlert"
APP_VERSION = "2.0.2"
APP_AUTHOR = "Ed Perry"
APP_REPO_URL = "https://github.com/eperry/ScreenAlert"
APP_RELEASE_API_URL = "https://api.github.com/repos/eperry/ScreenAlert/releases/latest"

# Paths
if platform.system() == "Windows":
    APPDATA = os.environ.get('APPDATA', os.path.expanduser('~'))
    CONFIG_DIR = os.path.join(APPDATA, 'ScreenAlert')
    LOGS_DIR = os.path.join(CONFIG_DIR, 'logs')
else:
    CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config', 'ScreenAlert')
    LOGS_DIR = os.path.join(CONFIG_DIR, 'logs')

CONFIG_FILE = os.path.join(CONFIG_DIR, "screenalert_config.json")
WINDOW_REGION_CONFIG_FILE = os.path.join(CONFIG_DIR, "screenalert_windows_regions.json")
MCP_CONFIG_FILE = os.path.join(CONFIG_DIR, "mcp_config.json")
EVENT_LOG_FILE = os.path.join(CONFIG_DIR, "event_log.jsonl")
MCP_CERT_FILE = os.path.join(CONFIG_DIR, "mcp_cert.pem")
MCP_KEY_FILE = os.path.join(CONFIG_DIR, "mcp_key.pem")
TEMP_DIR = os.path.join(CONFIG_DIR, "temp")
BG_MODELS_DIR = os.path.join(CONFIG_DIR, "bg_models")

# Create directories if they don't exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(BG_MODELS_DIR, exist_ok=True)

# Default Settings
DEFAULT_REFRESH_RATE_MS = 1000
DEFAULT_OPACITY = 0.8
DEFAULT_ALERT_THRESHOLD = 0.99
DEFAULT_HIGHLIGHT_TIME = 5

# Thumbnail Constraints
THUMBNAIL_MIN_WIDTH = 100
THUMBNAIL_MAX_WIDTH = 1280
THUMBNAIL_MIN_HEIGHT = 80
THUMBNAIL_MAX_HEIGHT = 800
THUMBNAIL_DEFAULT_WIDTH = 320
THUMBNAIL_DEFAULT_HEIGHT = 240

# DWM Overlay Update Rate
DEFAULT_OVERLAY_UPDATE_RATE_HZ = 30
OVERLAY_UPDATE_RATE_MIN_HZ = 10
OVERLAY_UPDATE_RATE_MAX_HZ = 60

# Overlay Scaling Modes
SCALING_MODE_FIT = "fit"              # Aspect-locked resize (overlay shape matches source)
SCALING_MODE_STRETCH = "stretch"      # Free-form resize, fills overlay (may distort)
SCALING_MODE_LETTERBOX = "letterbox"  # Free-form resize, aspect-preserved with bars
SCALING_MODES = [SCALING_MODE_FIT, SCALING_MODE_STRETCH, SCALING_MODE_LETTERBOX]

# Auto-Discovery
DEFAULT_AUTO_DISCOVERY_INTERVAL_SEC = 60
AUTO_DISCOVERY_INTERVAL_MIN_SEC = 10
AUTO_DISCOVERY_INTERVAL_MAX_SEC = 300

# Visual Theme
COLOR_BG_DARK = "#0a0a0a"
COLOR_BG_MEDIUM = "#1a1a1a"
COLOR_BG_LIGHT = "#2a2a2a"
COLOR_ORANGE = "#ff9500"
COLOR_BLUE = "#00d4ff"
COLOR_AMBER = "#ffb347"
COLOR_RED = "#ff4444"
COLOR_GREEN = "#44ff44"
COLOR_TEXT_LIGHT = "#cccccc"
COLOR_TEXT_DARK = "#888888"
COLOR_BORDER = "#444444"

# Alert Status Colors
STATUS_COLORS = {
    "green": COLOR_GREEN,
    "paused": COLOR_BLUE,
    "alert": COLOR_RED,
    "disabled": COLOR_ORANGE,
    "unavailable": "#666666"
}

# Logging
TRACE = 5  # Custom level below DEBUG (10)
LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"]
DEFAULT_LOG_LEVEL = "ERROR"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
