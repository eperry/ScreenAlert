#!/usr/bin/env python3
"""
Simple test: launch the Windows Graphics Capture picker and print the chosen item's display name.
Requires the `winrt` package: `pip install winrt`.

Usage:
  python tools/wgc_thumbnail_test.py

Optional flags kept for parity with other tests:
  --title TEXT    (ignored for picker mode)
"""
import argparse
import sys
import os
import subprocess

parser = argparse.ArgumentParser(description='Windows Graphics Capture picker test')
parser.add_argument('--title', help='(ignored) window title to target; run without to use picker', default=None)
args = parser.parse_args()

try:
    from winrt.windows.graphics.capture import GraphicsCapturePicker
except Exception as exc:
    # If `winrt` isn't available, try to call the external Python 3.11 helper
    GraphicsCapturePicker = None
    print('WARNING: winrt.windows.graphics.capture not available in this interpreter.', file=sys.stderr)
    print('Exception:', exc, file=sys.stderr)
    # Try to invoke the helper script using a Python 3.11 interpreter.
    helper = os.path.join(os.getcwd(), 'tools', 'wgc_picker_helper.py')
    if os.path.exists(helper):
        # candidate interpreter commands
        candidates = []
        env_python = os.environ.get('WGC_HELPER_PYTHON')
        if env_python:
            candidates.append([env_python, helper])
        # try the py launcher for 3.11
        candidates.append(['py', '-3.11', helper])
        candidates.append(['python3.11', helper])
        candidates.append(['python3', helper])
        candidates.append(['python', helper])

        ran = False
        for cmd in candidates:
            try:
                print('Trying helper with:', ' '.join(cmd))
                proc = subprocess.run(cmd, check=False)
                ran = True
                # if helper produced the selection file, continue; otherwise try next
                sel_path = os.path.join(os.getcwd(), 'wgc_picker_selection.json')
                if os.path.exists(sel_path):
                    print('Selection written by helper:', sel_path)
                    break
            except FileNotFoundError:
                continue
            except Exception as e:
                print('Helper invocation failed:', e, file=sys.stderr)
                continue
        if not ran:
            print('No suitable helper interpreter found. Install Python 3.11 and winrt or set WGC_HELPER_PYTHON.', file=sys.stderr)
    else:
        print('Helper script not found at', helper, file=sys.stderr)

print('Launching Windows Graphics Capture picker...')

if GraphicsCapturePicker is not None:
    picker = GraphicsCapturePicker()
    # pick_single_item_async returns an IAsyncOperation — call get() to wait for result
    item = picker.pick_single_item_async().get()

    if item is None:
        print('No item selected (picker cancelled).')
        sys.exit(0)

    # Print some basic details about the chosen item
    try:
        name = item.display_name
    except Exception:
        name = '<unknown>'

    print('Selected item display name:', name)
    try:
        size = item.size
        print('Item size: {}x{}'.format(size.width, size.height))
    except Exception:
        pass

    # Optionally, write a small JSON summary for other tools to consume
    import json, os
    summary = {'display_name': name}
    out_path = os.path.join(os.getcwd(), 'wgc_picker_selection.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print('Wrote selection summary to', out_path)

    print('Done.')
else:
    # Fallback: enumerate top-level visible windows via pywin32 and prompt the user
    try:
        import win32gui
    except Exception:
        print('ERROR: pywin32 is required for fallback picker but is not available.', file=sys.stderr)
        sys.exit(3)

    windows = []

    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.strip():
                windows.append((hwnd, title))

    win32gui.EnumWindows(_enum, None)

    if not windows:
        print('No visible windows found to pick.')
        sys.exit(0)

    print('Choose a window from the list:')
    for i, (_hwnd, title) in enumerate(windows, start=1):
        try:
            safe_title = title.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        except Exception:
            safe_title = title
        print(f'{i}: {safe_title}')

    sel = None
    try:
        sel = int(input('Enter selection number (or 0 to cancel): ').strip())
    except Exception:
        print('Invalid selection; exiting.')
        sys.exit(0)

    if sel <= 0 or sel > len(windows):
        print('Cancelled.')
        sys.exit(0)

    chosen = windows[sel - 1][1]
    try:
        safe_chosen = chosen.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
    except Exception:
        safe_chosen = chosen
    print('Selected:', safe_chosen)

    # Write selection summary for downstream tools
    import json, os, subprocess
    summary = {'display_name': chosen}
    out_path = os.path.join(os.getcwd(), 'wgc_picker_selection.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print('Wrote selection summary to', out_path)

    # Launch the DWM thumbnail test with the chosen title so user can see a thumbnail
    python_exe = sys.executable
    script = os.path.join(os.getcwd(), 'tools', 'dwm_thumbnail_test.py')
    print('Launching DWM thumbnail test for the chosen window...')
    subprocess.run([python_exe, script, '--title', chosen])
