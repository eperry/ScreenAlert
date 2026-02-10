#!/usr/bin/env python3
"""Comprehensive test for thumbnail rendering - debug each step"""

import sys
import os
import time
import threading
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import queue

# Add to path
sys.path.insert(0, '.')

from screenalert_core.core.window_manager import WindowManager
from screenalert_core.rendering.thumbnail_renderer import ThumbnailRenderer

def test_window_capture():
    """Test 1: Can we capture a window?"""
    print("\n=== TEST 1: Window Capture ===")
    
    wm = WindowManager()
    windows = wm.get_window_list()
    
    if not windows:
        print("ERROR: No windows found!")
        return None
    
    print(f"Found {len(windows)} windows")
    for w in windows[:3]:
        print(f"  - {w['title']}")
    
    # Try to capture first window
    test_window = windows[0]
    hwnd = test_window['hwnd']
    title = test_window['title']
    
    print(f"\nCapturing: {title} (hwnd={hwnd})")
    image = wm.capture_window(hwnd)
    
    if image:
        print(f"✓ Captured successfully: {image.size}")
        return hwnd, image
    else:
        print("✗ Capture failed")
        return None

def test_renderer_creation():
    """Test 2: Can we create the renderer and window?"""
    print("\n=== TEST 2: Renderer & Window Creation ===")
    
    renderer = ThumbnailRenderer()
    print("✓ Renderer created")
    
    config = {
        "position": {"x": 100, "y": 100, "monitor": 0},
        "size": {"width": 400, "height": 300},
        "window_title": "Test Thumbnail",
        "opacity": 0.9,
        "show_border": True,
        "enabled": True
    }
    
    success = renderer.add_thumbnail("test_thumbnail", config)
    if success:
        print("✓ Thumbnail window created")
        return renderer
    else:
        print("✗ Failed to create thumbnail")
        return None

def test_image_update():
    """Test 3: Can we update the image?"""
    print("\n=== TEST 3: Image Update ===")
    
    # Capture a real window
    result = test_window_capture()
    if not result:
        return False
    
    hwnd, captured_image = result
    
    # Create renderer
    renderer = test_renderer_creation()
    if not renderer:
        return False
    
    # Start renderer
    renderer.start()
    print("✓ Renderer started")
    time.sleep(0.5)
    
    # Update with captured image
    print(f"Updating thumbnail with captured image ({captured_image.size})...")
    renderer.update_thumbnail_image("test_thumbnail", captured_image)
    
    # Wait for queue to process
    print("Waiting for image queue to process...")
    for i in range(50):  # Wait up to 2.5 seconds
        time.sleep(0.05)
        thumbnail = renderer.get_thumbnail("test_thumbnail")
        if thumbnail and thumbnail.photo_image:
            print("✓ Image processed and displayed!")
            return True
    
    print("✗ Image did not appear after 2.5 seconds")
    
    # Check queue state
    thumbnail = renderer.get_thumbnail("test_thumbnail")
    if thumbnail:
        print(f"  Queue size: {thumbnail.image_queue.qsize()}")
        print(f"  Photo image: {thumbnail.photo_image}")
        print(f"  Window: {thumbnail.window}")
        print(f"  Label: {thumbnail.label if hasattr(thumbnail, 'label') else 'NO LABEL'}")
    
    return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("THUMBNAIL RENDERING TEST SUITE")
    print("=" * 60)
    
    try:
        # Test 1: Capture
        result = test_window_capture()
        if not result:
            print("\n✗ FAILED: Cannot capture windows")
            return
        
        hwnd, test_image = result
        
        # Test 2: Renderer creation
        renderer = test_renderer_creation()
        if not renderer:
            print("\n✗ FAILED: Cannot create renderer/window")
            return
        
        # Test 3: Full integration
        renderer.stop()  # Stop from previous test
        
        print("\n=== TEST 3: Full Integration - Update Loop ===")
        
        renderer = ThumbnailRenderer()
        config = {
            "position": {"x": 100, "y": 100, "monitor": 0},
            "size": {"width": 400, "height": 300},
            "window_title": "Live Window Capture",
            "opacity": 0.9,
            "show_border": True,
            "enabled": True
        }
        
        renderer.add_thumbnail("live_test", config)
        print("✓ Thumbnail window created")
        
        # Start renderer loop
        renderer.start()
        print("✓ Renderer started")
        
        # Capture window and update in loop
        wm = WindowManager()
        windows = wm.get_window_list()
        if windows:
            hwnd = windows[0]['hwnd']
            print(f"Capturing: {windows[0]['title']}")
            
            # Update 5 times with 1 second delay
            for i in range(5):
                image = wm.capture_window(hwnd)
                if image:
                    print(f"  [{i+1}] Captured and sending to overlay...")
                    renderer.update_thumbnail_image("live_test", image)
                    time.sleep(1)
            
            print("\n✓ Test complete - check overlay window for live updates")
            print("  Window should show live captures of the selected application")
            
            # Keep running for user to see
            input("\nPress Enter to close...")
        
        renderer.stop()
        print("✓ Renderer stopped")
        
    except Exception as e:
        print(f"\n✗ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
