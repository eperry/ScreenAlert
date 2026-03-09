"""Image processing and comparison utilities"""

import logging
import cv2
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
    def _canny_edges(gray_arr: np.ndarray,
                     canny_low: int = 40,
                     canny_high: int = 120,
                     binarize: bool = False) -> np.ndarray:
        """Return a Canny edge map for a uint8 grayscale array.

        A bilateral filter is applied first — it smooths out background
        gradients and colour shifts while preserving sharp edges (text,
        borders, icons).  This prevents animated backgrounds from
        producing spurious edge flicker.

        When *binarize* is True an additional adaptive threshold step
        converts the image to pure black/white before edge detection,
        for maximum gradient rejection.
        """
        # Bilateral filter: smooths gradients, preserves text edges
        gray_arr = cv2.bilateralFilter(gray_arr, 9, 75, 75)
        if binarize:
            gray_arr = cv2.adaptiveThreshold(
                gray_arr, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11, C=2,
            )
        blurred = cv2.GaussianBlur(gray_arr, (3, 3), 0)
        return cv2.Canny(blurred, threshold1=canny_low, threshold2=canny_high)

    @staticmethod
    def detect_change(img1: Image.Image, img2: Image.Image,
                      threshold: float = 0.99,
                      method: str = "ssim",
                      min_edge_fraction: float = 0.003,
                      canny_low: int = 40,
                      canny_high: int = 120,
                      binarize: bool = False) -> bool:
        """Detect if there's a significant structural change between images.

        Uses Canny edge detection on greyscale frames as the primary check.
        Edge maps are invariant to minor colour/brightness shifts and
        anti-aliasing noise, so only real structural changes (new text,
        UI elements appearing, state transitions) trigger an alert.

        Falls back to SSIM / pHash for subtle changes that don't produce
        clear edges (e.g. a uniform block changing colour).

        Args:
            img1: Previous frame (PIL Image).
            img2: Current frame (PIL Image).
            threshold: SSIM/pHash similarity threshold for the fallback
                       check (higher = more sensitive).
            method: Fallback method – ``"ssim"`` or ``"phash"``.
            min_edge_fraction: Fraction of total pixels whose edge state
                               must change to count as a real change
                               (default 0.3 %).  Raise to reduce
                               sensitivity; lower to catch subtler changes.

        Returns:
            True if a change is detected.
        """
        # ── Canny edge-diff ────────────────────────────────────────────
        # Convert to grayscale, extract structural edge maps, and compare
        # them.  Only fire if enough edge pixels changed – this eliminates
        # false positives from rendering jitter, cursor blink, and
        # compression artefacts while still catching real UI changes.
        try:
            g1 = np.array(img1.convert('L'), dtype=np.uint8)
            g2 = np.array(img2.convert('L'), dtype=np.uint8)

            edges1 = ImageProcessor._canny_edges(g1, canny_low, canny_high, binarize=binarize)
            edges2 = ImageProcessor._canny_edges(g2, canny_low, canny_high, binarize=binarize)

            changed_px = int(np.count_nonzero(edges1 != edges2))
            total_px = g1.size
            fraction = changed_px / max(1, total_px)

            logger.debug(
                "edge-diff: %d/%d px changed (%.3f%%) min=%.3f%%",
                changed_px, total_px, fraction * 100, min_edge_fraction * 100,
            )

            if fraction >= min_edge_fraction:
                return True
        except Exception:
            pass  # fall through to soft comparison

        # ── Soft comparison (SSIM / pHash) ─────────────────────────────
        # Catches subtle changes that don't manifest as new edges, e.g.
        # a uniform region changing colour.  Skipped when method is
        # "edge_only" – useful for apps with animated backgrounds.
        if method == "edge_only":
            return False

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
