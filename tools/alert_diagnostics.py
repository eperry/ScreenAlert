"""Standalone alert diagnostics tool.

Captures two screenshots of a window (with a configurable delay) and runs
the same Canny-edge change detection that ScreenAlert uses internally.
Saves diagnostic images (full window, region crop, edge maps, edge diff)
so you can visually inspect whether alerts are genuine.

Usage:
    python tools/alert_diagnostics.py --hwnd 0x12345 --rect 100,200,300,400 --delay 5
    python tools/alert_diagnostics.py --title "My Window" --rect 100,200,300,400
    python tools/alert_diagnostics.py --list   # list available windows
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image

from screenalert_core.core.image_processor import ImageProcessor
from screenalert_core.core.window_manager import WindowManager


def safe_filename(text: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9._-]+', '_', text or "")
    return text[:64] or "item"


def list_windows():
    """List all visible windows with their handles and titles."""
    wm = WindowManager()
    windows = wm.get_window_list()
    print(f"{'HWND':<12} {'Title'}")
    print("-" * 60)
    for w in windows:
        hwnd = w.get("hwnd", 0)
        title = w.get("title", "(no title)").encode("ascii", "replace").decode()
        print(f"0x{hwnd:08X}   {title}")


def find_hwnd_by_title(title_substring: str) -> int:
    """Find window handle by title substring match."""
    wm = WindowManager()
    windows = wm.get_window_list()
    for w in windows:
        if title_substring.lower() in w.get("title", "").lower():
            return w["hwnd"]
    return 0


def capture_window_image(wm: WindowManager, hwnd: int) -> Image.Image:
    """Capture a window image via PrintWindow."""
    img = wm.capture_window(hwnd)
    if img is None:
        raise RuntimeError(f"Failed to capture window 0x{hwnd:08X}")
    return img


def run_diagnostics(hwnd: int, rect: tuple, delay: float,
                    min_edge_fraction: float, canny_low: int, canny_high: int,
                    output_dir: str, window_title: str):
    """Capture two frames, run change detection, save diagnostic images."""
    wm = WindowManager()
    os.makedirs(output_dir, exist_ok=True)

    print(f"Capturing window 0x{hwnd:08X} ({window_title})")
    print(f"Region: {rect}")
    print(f"Edge params: min_edge_fraction={min_edge_fraction}, canny_low={canny_low}, canny_high={canny_high}")

    # First capture
    print("Capturing frame 1...")
    img1 = capture_window_image(wm, hwnd)

    print(f"Waiting {delay}s for changes...")
    time.sleep(delay)

    # Second capture
    print("Capturing frame 2...")
    img2 = capture_window_image(wm, hwnd)

    # Crop regions
    region1 = ImageProcessor.crop_region(img1, rect)
    region2 = ImageProcessor.crop_region(img2, rect)

    # Run change detection
    has_change = ImageProcessor.detect_change(
        region1, region2,
        min_edge_fraction=min_edge_fraction,
        canny_low=canny_low,
        canny_high=canny_high,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{timestamp}_{safe_filename(window_title)}_diag"

    # Save full window images
    img1.save(os.path.join(output_dir, f"{prefix}_window_prev.png"))
    img2.save(os.path.join(output_dir, f"{prefix}_window_curr.png"))

    # Save region crops
    region1.save(os.path.join(output_dir, f"{prefix}_region_prev.png"))
    region2.save(os.path.join(output_dir, f"{prefix}_region_curr.png"))

    # Generate and save edge maps
    g1 = np.array(region1.convert('L'), dtype=np.uint8)
    g2 = np.array(region2.convert('L'), dtype=np.uint8)
    edges1 = ImageProcessor._canny_edges(g1, canny_low, canny_high)
    edges2 = ImageProcessor._canny_edges(g2, canny_low, canny_high)

    Image.fromarray(edges1).save(os.path.join(output_dir, f"{prefix}_edges_prev.png"))
    Image.fromarray(edges2).save(os.path.join(output_dir, f"{prefix}_edges_curr.png"))

    # Edge diff
    edge_diff = np.abs(edges1.astype(np.int16) - edges2.astype(np.int16)).astype(np.uint8)
    Image.fromarray(edge_diff).save(os.path.join(output_dir, f"{prefix}_edges_diff.png"))

    # Stats
    changed_px = int(np.count_nonzero(edges1 != edges2))
    total_px = g1.size
    fraction = changed_px / max(1, total_px)

    print(f"\nResults:")
    print(f"  Change detected: {has_change}")
    print(f"  Edge pixels changed: {changed_px}/{total_px} ({fraction*100:.3f}%)")
    print(f"  Threshold: {min_edge_fraction*100:.3f}%")
    print(f"  Output: {output_dir}/{prefix}_*")


def main():
    parser = argparse.ArgumentParser(description="ScreenAlert edge detection diagnostics")
    parser.add_argument("--list", action="store_true", help="List available windows")
    parser.add_argument("--hwnd", type=lambda x: int(x, 0), help="Window handle (hex or decimal)")
    parser.add_argument("--title", type=str, help="Window title substring to match")
    parser.add_argument("--rect", type=str, default="0,0,200,200",
                        help="Region as x,y,width,height (default: 0,0,200,200)")
    parser.add_argument("--delay", type=float, default=5.0,
                        help="Seconds between captures (default: 5)")
    parser.add_argument("--min-edge-fraction", type=float, default=0.003,
                        help="Min fraction of changed edge pixels (default: 0.003)")
    parser.add_argument("--canny-low", type=int, default=40, help="Canny low threshold")
    parser.add_argument("--canny-high", type=int, default=120, help="Canny high threshold")
    parser.add_argument("--output", type=str, default="./alert_diagnostics_output",
                        help="Output directory for diagnostic images")

    args = parser.parse_args()

    if args.list:
        list_windows()
        return

    hwnd = args.hwnd
    window_title = "window"

    if not hwnd and args.title:
        hwnd = find_hwnd_by_title(args.title)
        window_title = args.title
        if not hwnd:
            print(f"No window found matching '{args.title}'")
            sys.exit(1)
    elif hwnd:
        window_title = f"hwnd_0x{hwnd:X}"
    else:
        print("Specify --hwnd or --title (or --list to see windows)")
        sys.exit(1)

    rect = tuple(int(v) for v in args.rect.split(","))
    if len(rect) != 4:
        print("--rect must be x,y,width,height")
        sys.exit(1)

    run_diagnostics(
        hwnd=hwnd,
        rect=rect,
        delay=args.delay,
        min_edge_fraction=args.min_edge_fraction,
        canny_low=args.canny_low,
        canny_high=args.canny_high,
        output_dir=args.output,
        window_title=window_title,
    )


if __name__ == "__main__":
    main()
