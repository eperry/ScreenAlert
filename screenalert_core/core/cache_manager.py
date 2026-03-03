"""Caching system for window captures"""

import time
import logging
import os
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

    def cleanup_temp_files(self, temp_dir: str, max_age_seconds: int = 86400) -> int:
        """Remove stale temporary files from runtime temp directory.

        Returns:
            Number of files removed.
        """
        removed = 0
        if not temp_dir or not os.path.isdir(temp_dir):
            return removed

        cutoff = time.time() - max_age_seconds
        try:
            for name in os.listdir(temp_dir):
                path = os.path.join(temp_dir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    if os.path.getmtime(path) <= cutoff:
                        os.remove(path)
                        removed += 1
                except Exception as file_error:
                    logger.debug(f"Skipping temp cleanup for {path}: {file_error}")
        except Exception as error:
            logger.warning(f"Error cleaning temp directory '{temp_dir}': {error}")

        if removed:
            logger.info(f"Removed {removed} stale runtime temp file(s)")
        return removed
