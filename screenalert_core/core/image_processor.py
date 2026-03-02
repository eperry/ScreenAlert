"""Image processing and comparison utilities"""

import logging
import numpy as np
from typing import Tuple, Optional
from PIL import Image
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image processing and comparison"""
    
    @staticmethod
    def crop_region(img: Image.Image, rect: Tuple[int, int, int, int]) -> Image.Image:
        """Crop image to region
        
        Args:
            img: PIL Image
            rect: (x, y, width, height)
        
        Returns:
            Cropped image
        """
        x, y, width, height = rect
        return img.crop((x, y, x + width, y + height))
    
    @staticmethod
    def calculate_ssim(img1: Image.Image, img2: Image.Image) -> float:
        """Calculate structural similarity between two images
        
        Args:
            img1: First PIL Image
            img2: Second PIL Image
        
        Returns:
            SSIM score (0.0 to 1.0, higher = more similar)
        """
        try:
            if img1.size != img2.size:
                return 0.0
            
            # Convert to grayscale for faster comparison
            gray1 = img1.convert('L')
            gray2 = img2.convert('L')
            
            # Convert to numpy arrays
            arr1 = np.array(gray1)
            arr2 = np.array(gray2)
            
            # Calculate SSIM
            score = ssim(arr1, arr2)
            return max(0.0, min(score, 1.0))  # Clamp to 0-1
        
        except Exception as e:
            logger.debug(f"Error calculating SSIM: {e}")
            return 0.0
    
    @staticmethod
    def detect_change(img1: Image.Image, img2: Image.Image, 
                     threshold: float = 0.99,
                     method: str = "ssim") -> bool:
        """Detect if there's significant change between images.

        A supplementary raw-pixel check runs first to catch tiny changes
        (e.g. a few characters changing in a large region) that SSIM or
        pHash would miss because their global scores barely move.

        Args:
            img1: First PIL Image
            img2: Second PIL Image
            threshold: Similarity threshold (higher = more sensitive)

        Returns:
            True if change detected
        """
        # ── Fast pixel-diff pre-check ──────────────────────────────────
        # Win32 screenshots are pixel-exact when unchanged, so ANY
        # non-zero pixel difference is a real change.  We use a minimal
        # threshold (>0 intensity, >=1 pixel) to catch even single-
        # character text changes in large regions that SSIM would miss.
        try:
            arr1 = np.array(img1.convert('L'), dtype=np.int16)
            arr2 = np.array(img2.convert('L'), dtype=np.int16)
            diff = np.abs(arr1 - arr2)
            any_diff_px = int(np.count_nonzero(diff > 0))
            if any_diff_px > 0:
                max_diff = int(diff.max())
                logger.debug(
                    "pixel-diff: %d pixels differ (max_intensity_delta=%d)",
                    any_diff_px, max_diff,
                )
                return True
        except Exception:
            pass  # fall through to soft comparison

        # ── Soft comparison (SSIM / pHash) ─────────────────────────────
        if method == "phash":
            similarity = ImageProcessor.calculate_phash_similarity(img1, img2)
        else:
            similarity = ImageProcessor.calculate_ssim(img1, img2)
        changed = similarity < threshold
        if changed:
            logger.debug(
                "soft-compare (%s): similarity=%.6f threshold=%.4f -> CHANGED",
                method, similarity, threshold,
            )
        return changed

    @staticmethod
    def _average_hash(img: Image.Image, hash_size: int = 8) -> np.ndarray:
        """Compute average hash bits for an image."""
        gray = img.convert('L').resize((hash_size, hash_size), Image.Resampling.LANCZOS)
        arr = np.array(gray, dtype=np.float32)
        avg = arr.mean()
        return arr > avg

    @staticmethod
    def calculate_phash_similarity(img1: Image.Image, img2: Image.Image) -> float:
        """Approximate perceptual-hash similarity in [0,1]."""
        try:
            if img1.size != img2.size:
                img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
            h1 = ImageProcessor._average_hash(img1)
            h2 = ImageProcessor._average_hash(img2)
            hamming = np.count_nonzero(h1 != h2)
            total = h1.size
            return max(0.0, min(1.0, 1.0 - (hamming / max(1, total))))
        except Exception as e:
            logger.debug(f"Error calculating pHash similarity: {e}")
            return 0.0
    
    @staticmethod
    def resize_image(img: Image.Image, width: int, height: int, 
                    maintain_aspect: bool = True) -> Image.Image:
        """Resize image
        
        Args:
            img: PIL Image
            width: Target width
            height: Target height
            maintain_aspect: If True, maintains aspect ratio with padding
        
        Returns:
            Resized image
        """
        try:
            # Always work on a copy to avoid mutating the caller's image
            result = img.copy()
            if maintain_aspect:
                result.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                result = result.resize((width, height), Image.Resampling.LANCZOS)
            return result
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return img
    
    @staticmethod
    def convert_to_display_format(img: Image.Image) -> Image.Image:
        """Convert image to display format (RGB)"""
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img
