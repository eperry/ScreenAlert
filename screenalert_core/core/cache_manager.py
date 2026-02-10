"""Caching system for window captures"""

import time
import logging
from typing import Dict, Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages image cache for window captures"""
    
    def __init__(self, lifetime_seconds: float = 1.0):
        """Initialize cache manager
        
        Args:
            lifetime_seconds: How long to keep cached images
        """
        self.lifetime = lifetime_seconds
        self.cache: Dict[int, Tuple[Image.Image, float]] = {}  # hwnd -> (image, timestamp)
    
    def get(self, hwnd: int) -> Optional[Image.Image]:
        """Get cached image if still valid
        
        Args:
            hwnd: Window handle
        
        Returns:
            PIL Image or None if not cached or expired
        """
        if hwnd not in self.cache:
            return None
        
        img, timestamp = self.cache[hwnd]
        age = time.time() - timestamp
        
        if age > self.lifetime:
            del self.cache[hwnd]
            return None
        
        return img
    
    def set(self, hwnd: int, image: Image.Image) -> None:
        """Cache an image
        
        Args:
            hwnd: Window handle
            image: PIL Image to cache
        """
        self.cache[hwnd] = (image, time.time())
    
    def invalidate(self, hwnd: int) -> None:
        """Remove specific cache entry"""
        if hwnd in self.cache:
            del self.cache[hwnd]
    
    def invalidate_all(self) -> None:
        """Clear all cache"""
        self.cache.clear()
    
    def cleanup(self) -> None:
        """Remove expired entries"""
        now = time.time()
        expired = [hwnd for hwnd, (_, ts) in self.cache.items() 
                  if now - ts > self.lifetime]
        for hwnd in expired:
            del self.cache[hwnd]
        
        if expired:
            logger.debug(f"Cache cleanup: removed {len(expired)} expired entries")
