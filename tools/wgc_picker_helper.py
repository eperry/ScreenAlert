#!/usr/bin/env python3
"""
WGC picker helper that must be run with Python 3.11 where `winrt` is available.
It launches the Windows Graphics Capture picker and writes the selection to
`wgc_picker_selection.json` in the current working directory.

Usage (from project root):
  # create a Python 3.11 venv and install winrt
  py -3.11 -m venv .venv-wgc
  .\.venv-wgc\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install winrt
  python tools\wgc_picker_helper.py

The calling script can set the `WGC_SELECTION_PATH` env var to change the output path.
"""
import json
import os
import sys

OUT_PATH = os.environ.get('WGC_SELECTION_PATH') or os.path.join(os.getcwd(), 'wgc_picker_selection.json')

def main():
    try:
        from winrt.windows.graphics.capture import GraphicsCapturePicker
    except Exception as e:
        print('ERROR: winrt not available in this interpreter:', e, file=sys.stderr)
        return 2

    picker = GraphicsCapturePicker()
    try:
        item = picker.pick_single_item_async().get()
    except Exception as exc:
        print('ERROR: picker failed:', exc, file=sys.stderr)
        return 3

    if item is None:
        print('No item selected (cancelled)')
        return 0

    try:
        name = item.display_name
    except Exception:
        name = '<unknown>'

    summary = {'display_name': name}
    try:
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print('Wrote selection to', OUT_PATH)
    except Exception as e:
        print('ERROR: failed to write selection:', e, file=sys.stderr)
        return 4

    return 0

if __name__ == '__main__':
    sys.exit(main())
