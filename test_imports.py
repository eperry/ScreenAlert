#!/usr/bin/env python3
"""
Test script to check what imports work in Linux environment
"""

import sys
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

modules_to_test = [
    'pyautogui',
    'PIL', 
    'tkinter',
    'numpy',
    'cv2',
    'skimage',
    'imagehash'
]

for module_name in modules_to_test:
    try:
        if module_name == 'PIL':
            from PIL import Image
        elif module_name == 'tkinter':
            import tkinter
        elif module_name == 'cv2':
            import cv2
        elif module_name == 'skimage':
            from skimage.metrics import structural_similarity
        else:
            __import__(module_name)
        print(f"[OK] {module_name}")
    except ImportError as e:
        print(f"[ERROR] {module_name}: {e}")
    except Exception as e:
        print(f"[WARNING] {module_name}: {e}")
