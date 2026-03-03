"""Helper utilities for ScreenAlert"""

import uuid
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_uuid() -> str:
    """Generate a unique identifier"""
    return str(uuid.uuid4())


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple
    
    Args:
        hex_color: Color in hex format (e.g., "#ff9500")
        
    Returns:
        Tuple of (R, G, B) values
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple) -> str:
    """Convert RGB tuple to hex color
    
    Args:
        rgb: Tuple of (R, G, B) values
        
    Returns:
        Color in hex format (e.g., "#ff9500")
    """
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max"""
    return max(min_val, min(value, max_val))


def pretty_json(obj: Dict[str, Any]) -> str:
    """Return pretty-printed JSON"""
    return json.dumps(obj, indent=2)


def is_valid_hex_color(color: str) -> bool:
    """Check if a string is a valid hex color"""
    if not isinstance(color, str):
        return False
    if not color.startswith('#'):
        return False
    if len(color) != 7:
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False


def safe_get_dict(data: Dict, keys: list, default: Any = None) -> Any:
    """Safely get nested dictionary value
    
    Example:
        safe_get_dict(config, ["app", "refresh_rate_ms"], 1000)
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
