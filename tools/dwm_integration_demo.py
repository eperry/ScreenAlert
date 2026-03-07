#!/usr/bin/env python3
"""
Demo: create a ThumbnailWindow from the project's renderer using DWM thumbnail.
Usage: python tools/dwm_integration_demo.py --title "Window Title"
"""
import argparse
import sys
import tkinter as tk
import os
import sys
# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Also ensure current working directory (project root when run from repo) is present
sys.path.insert(0, os.path.abspath(os.getcwd()))
import subprocess
import sys
import os

# This demo now defers to the native native_dwm_demo helper which creates
# a native layered window and registers a DWM thumbnail. The legacy
# ThumbnailWindow has been removed.

parser = argparse.ArgumentParser()
parser.add_argument('--title', required=True)
args = parser.parse_args()

def main():
    # Locate helper script
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    helper = os.path.join(script_dir, 'native_dwm_demo.py')
    if not os.path.exists(helper):
        print('native_dwm_demo.py not found in tools; ensure tools/native_dwm_demo.py exists')
        sys.exit(2)

    cmd = [sys.executable, helper, '--title', args.title, '--width', '600', '--height', '400']
    rc = subprocess.run(cmd).returncode
    sys.exit(rc)

if __name__ == '__main__':
    main()
