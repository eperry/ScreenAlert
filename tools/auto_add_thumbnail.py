"""Auto test: create engine, set tkinter root, add thumbnail by hwnd, run briefly, then stop.

Usage:
    python tools/auto_add_thumbnail.py --hwnd 0x003a0c02 --title "Untitled - Notepad" --duration 15
"""
import argparse
import time
import tkinter as tk

from screenalert_core.screening_engine import ScreenAlertEngine


def parse_hwnd(s: str) -> int:
    if s.startswith('0x') or s.startswith('0X'):
        return int(s, 16)
    return int(s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hwnd', required=True, help='HWND integer or hex')
    parser.add_argument('--title', required=True, help='Window title')
    parser.add_argument('--duration', type=int, default=15, help='Seconds to run')
    args = parser.parse_args()

    hwnd = parse_hwnd(args.hwnd)
    title = args.title

    # Create headless-ish tkinter root
    root = tk.Tk()
    root.withdraw()

    engine = ScreenAlertEngine()
    engine.set_tkinter_root(root)

    # Start engine
    ok = engine.start()
    if not ok:
        print('Failed to start engine')
        return

    # Add thumbnail
    tid = engine.add_thumbnail(title, hwnd)
    print('Added thumbnail id:', tid)

    try:
        print('Running engine for', args.duration, 'seconds...')
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        engine.stop()
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == '__main__':
    main()
