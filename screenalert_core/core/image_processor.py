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
                     threshold: float = 0.99) -> bool:
        """Detect if there's significant change between images
        
        Args:
            img1: First PIL Image
            img2: Second PIL Image
            threshold: SSIM threshold (lower = more sensitive)
        
        Returns:
            True if change detected (SSIM < threshold)
        """
        similarity = ImageProcessor.calculate_ssim(img1, img2)
        return similarity < threshold
    
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
            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return img
    
    @staticmethod
    def convert_to_display_format(img: Image.Image) -> Image.Image:
        """Convert image to display format (RGB)"""
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img
