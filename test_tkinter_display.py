#!/usr/bin/env python3
"""Simple tkinter image display test - isolate the display issue"""

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import threading
import time
import sys

def create_test_image(width=400, height=300, text="Test Image"):
    """Create a simple test image with visible content"""
    img = Image.new('RGB', (width, height), color='blue')
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill='white')
    draw.rectangle([10, 10, width-10, height-10], outline='yellow', width=3)
    return img

def test_simple_display():
    """Test 1: Simple image display (no threading)"""
    print("\n=== TEST 1: Simple Image Display ===")
    
    root = tk.Tk()
    root.geometry("400x300+100+100")
    root.title("Simple Display Test")
    
    # Create label
    label = tk.Label(root, bg='black')
    label.pack(fill=tk.BOTH, expand=True)
    
    # Create and display image
    img = create_test_image(400, 300, "Simple Display Test")
    photo = ImageTk.PhotoImage(img)
    label.config(image=photo)
    label.image = photo  # Keep reference
    
    print("✓ Image displayed - window should show blue image with yellow border")
    
    # Process events for a moment then close
    for _ in range(30):
        root.update()
        time.sleep(0.1)
    
    root.destroy()
    print("✓ Window closed")

def test_queue_based_display():
    """Test 2: Queue-based display (threaded update)"""
    print("\n=== TEST 2: Queue-Based Display (with threading) ===")
    
    import queue
    
    root = tk.Tk()
    root.geometry("400x300+500+100")
    root.title("Queue-Based Display Test")
    
    # Create label
    label = tk.Label(root, bg='black')
    label.pack(fill=tk.BOTH, expand=True)
    
    # Create queue
    img_queue = queue.Queue(maxsize=1)
    photo_ref = [None]  # Mutable container to hold photo reference
    
    update_count = [0]
    
    def update_from_queue():
        """Update label from queue (main thread via after)"""
        try:
            img = img_queue.get_nowait()
            photo = ImageTk.PhotoImage(img)
            label.config(image=photo)
            photo_ref[0] = photo  # Keep reference
            update_count[0] += 1
            print(f"  ✓ Updated image from queue (count: {update_count[0]})")
        except queue.Empty:
            pass
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        # Schedule next check if window still exists
        try:
            root.after(50, update_from_queue)
        except:
            pass
    
    def send_images():
        """Background thread that sends images to queue"""
        for i in range(5):
            time.sleep(0.5)
            try:
                img = create_test_image(400, 300, f"Queue Test - Image {i+1}")
                img_queue.put_nowait(img)
                print(f"  Sent image {i+1}")
            except queue.Full:
                print(f"  Queue full, dropping old image")
                try:
                    img_queue.get_nowait()
                    img_queue.put_nowait(img)
                except:
                    pass
    
    # Start background thread
    thread = threading.Thread(target=send_images, daemon=True)
    thread.start()
    
    # Start queue processing
    update_from_queue()
    
    print("✓ Background thread sending images to queue")
    print("  Window should update with new images every 0.5 seconds")
    
    # Run for 5 seconds
    for _ in range(100):
        try:
            root.update()
            time.sleep(0.05)
        except:
            break
    
    try:
        root.destroy()
    except:
        pass
    print(f"✓ Window closed (received {update_count[0]} updates)")

def main():
    print("=" * 60)
    print("TKINTER IMAGE DISPLAY TESTS")
    print("=" * 60)
    
    try:
        test_simple_display()
        time.sleep(0.5)
        
        test_queue_based_display()
        time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

