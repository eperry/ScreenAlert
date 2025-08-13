#!/usr/bin/env python3
"""
cx_Freeze Build Script for ScreenAlert
Another PyInstaller alternative
"""

import os
import sys
from pathlib import Path
from cx_Freeze import setup, Executable

# Build executable with cx_Freeze
def build_with_cx_freeze():
    """Create cx_Freeze setup and build"""
    
    # Get script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Include files (config, etc.)
    include_files = []
    
    # Add config file if it exists
    config_file = "screenalert_config.json"
    if os.path.exists(config_file):
        include_files.append(config_file)
    
    # Build options
    build_options = {
        "packages": ["tkinter", "PIL", "cv2", "numpy", "scipy", "skimage"],
        "excludes": ["test", "unittest", "email", "html", "http", "urllib", "xml"],
        "include_files": include_files,
        "optimize": 2,
        "build_exe": "dist-cxfreeze"
    }
    
    # Create executable definition
    executable = Executable(
        script="screenalert.py",
        target_name="ScreenAlert.exe",
        base="Win32GUI",  # No console window
        icon=None  # Add icon path here if you have one
    )
    
    # Setup configuration
    setup(
        name="ScreenAlert",
        version="1.0.0",
        description="Screen monitoring and alert system",
        author="ScreenAlert Team",
        options={"build_exe": build_options},
        executables=[executable]
    )

if __name__ == "__main__":
    print("ScreenAlert - cx_Freeze Builder")
    print("=" * 40)
    print("cx_Freeze creates Windows executables with minimal bloat")
    print()
    
    # Set command line arguments for cx_Freeze
    sys.argv = ["setup_cx_freeze.py", "build"]
    
    try:
        build_with_cx_freeze()
        
        # Check if build was successful
        exe_path = Path("dist-cxfreeze") / "ScreenAlert.exe"
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"\ncx_Freeze build completed successfully!")
            print(f"Executable created: {exe_path}")
            print(f"File size: {file_size:.1f} MB")
        else:
            print("Build completed but executable not found")
            
    except Exception as e:
        print(f"cx_Freeze build failed: {e}")
        sys.exit(1)
