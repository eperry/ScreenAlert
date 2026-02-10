#!/usr/bin/env python3
"""Test actual ThumbnailWindow with detailed logging"""

import sys
sys.path.insert(0, '.')

import time
import threading
from PIL import Image, ImageDraw
from screenalert_core.rendering.thumbnail_renderer import ThumbnailWindow

def create_test_image(width=320, height=240, text="Test"):
    """Create test image"""
    img = Image.new('RGB', (width, height), color='green')
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill='yellow')
    draw.rectangle([5, 5, width-5, height-5], outline='red', width=2)
    return img

def main():
    print("\n=== TEST: ThumbnailWindow with Actual Implementation ===\n")
    
    config = {
        "position": {"x": 100, "y": 100, "monitor": 0},
        "size": {"width": 400, "height": 300},
        "window_title": "Test Thumbnail Window",
        "opacity": 0.9,
        "show_border": True,
        "enabled": True
    }
    
    print("Creating ThumbnailWindow...")
    window = ThumbnailWindow("test_1", config)
    print(f"✓ Window created")
    print(f"  window.window = {window.window}")
    print(f"  window.label = {window.label}")
    print(f"  window.image_queue = {window.image_queue}")
    
    # Send 3 images
    print("\nSending images...")
    for i in range(3):
        img = create_test_image(320, 240, f"Image {i+1}")
        print(f"\n  [{i+1}] Created image {img.size}")
        window.set_image(img)
        
        queue_size = window.image_queue.qsize()
        print(f"      Queue size after set_image: {queue_size}")
        
        time.sleep(0.2)
        
        # Check if photo_image was created
        if window.photo_image:
            print(f"      ✓ photo_image created: {window.photo_image}")
        else:
            print(f"      ✗ photo_image is None")
    
    print("\nWaiting for queue processing...")
    # Simulate main thread event loop processing
    for j in range(50):
        try:
            window.window.update()
        except:
            print("✗ Window destroyed or error")
            break
        
        time.sleep(0.05)
        
        if j % 10 == 0:
            print(f"  [{j}] Queue size: {window.image_queue.qsize()}, Photo: {window.photo_image is not None}")
    
    print("\nFinal state:")
    print(f"  Queue size: {window.image_queue.qsize()}")
    print(f"  photo_image: {window.photo_image}")
    print(f"  Window exists: {window.window is not None}")
    
    print("\n✓ Test completed - check overlay window for images")
    
    # Keep window open for 3 seconds
    time.sleep(3)
    
    window.cleanup()
    print("✓ Window cleaned up")

if __name__ == "__main__":
    main()
