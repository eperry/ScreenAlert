#!/usr/bin/env python3
"""Test tkinter overlay windows"""

import sys
import os

# Force unbuffered output and stderr
sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode='w', buffering=1)

print("TEST: Starting overlay window test...", file=sys.stderr, flush=True)

import tkinter as tk
from PIL import Image, ImageDraw
import time

# Add current directory to path
sys.path.insert(0, '.')

print("TEST: Importing ThumbnailRenderer...", file=sys.stderr, flush=True)
from screenalert_core.rendering.thumbnail_renderer import ThumbnailRenderer

print("TEST: Imports successful", file=sys.stderr, flush=True)

def create_test_image(width, height, color=(100, 150, 200)):
    """Create a test PIL image"""
    img = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Test Overlay", fill=(255, 255, 255))
    return img

def main():
    """Test overlay windows"""
    print("TEST: Starting overlay window test...", file=sys.stderr, flush=True)
    
    # Create root window (not visible but needed for tkinter)
    print("TEST: Creating root window...", file=sys.stderr, flush=True)
    root = tk.Tk()
    root.withdraw()  # Hide root window
    
    try:
        # Create renderer
        print("TEST: Creating renderer...", file=sys.stderr, flush=True)
        renderer = ThumbnailRenderer()
        
        # Add three test thumbnails
        config1 = {
            "position": {"x": 100, "y": 100, "monitor": 0},
            "size": {"width": 320, "height": 240},
            "window_title": "Test 1",
            "opacity": 0.9,
            "show_border": True,
            "enabled": True
        }
        
        config2 = {
            "position": {"x": 500, "y": 100, "monitor": 0},
            "size": {"width": 320, "height": 240},
            "window_title": "Test 2",
            "opacity": 0.9,
            "show_border": True,
            "enabled": True
        }
        
        config3 = {
            "position": {"x": 300, "y": 400, "monitor": 0},
            "size": {"width": 320, "height": 240},
            "window_title": "Test 3",
            "opacity": 0.9,
            "show_border": True,
            "enabled": True
        }
        
        print("TEST: Adding thumbnails...", file=sys.stderr, flush=True)
        renderer.add_thumbnail("test1", config1)
        renderer.add_thumbnail("test2", config2)
        renderer.add_thumbnail("test3", config3)
        
        print("TEST: Starting render loop...", file=sys.stderr, flush=True)
        renderer.start()
        
        # Set images
        print("TEST: Creating test images...", file=sys.stderr, flush=True)
        img1 = create_test_image(320, 240, (200, 100, 100))
        img2 = create_test_image(320, 240, (100, 200, 100))
        img3 = create_test_image(320, 240, (100, 100, 200))
        
        print("TEST: Setting images...", file=sys.stderr, flush=True)
        renderer.update_thumbnail_image("test1", img1)
        renderer.update_thumbnail_image("test2", img2)
        renderer.update_thumbnail_image("test3", img3)
        
        print("\n=== OVERLAY WINDOWS SHOULD NOW BE VISIBLE ===", file=sys.stderr, flush=True)
        print("You should see 3 semi-transparent windows with colored backgrounds.", file=sys.stderr, flush=True)
        print("Running for 5 seconds then shutting down...", file=sys.stderr, flush=True)
        
        # Run for 5 seconds
        for i in range(50):
            try:
                root.update()
                time.sleep(0.1)
            except:
                break
        
        # Cleanup
        print("TEST: Stopping renderer...", file=sys.stderr, flush=True)
        renderer.stop()
        root.destroy()
        print("TEST: Test completed successfully!", file=sys.stderr, flush=True)
        
    except Exception as e:
        print(f"TEST ERROR: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    main()

