#!/usr/bin/env python3
"""
ScreenAlert - Fast Development Build
Optimized Nuitka build for development with faster compilation
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def fast_build():
    """Fast development build with minimal optimizations"""
    print("\nScreenAlert - Fast Development Build")
    print("=" * 40)
    print("Building with minimal optimizations for faster iteration...")
    
    # Ensure output directory exists
    output_dir = Path("dist-dev")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Check if config file exists
    config_file = Path("screenalert_config.json")
    if not config_file.exists():
        print(f"Warning: {config_file} not found, creating default config...")
        default_config = {
            "regions": [],
            "interval": 1500,
            "highlight_time": 5,
            "default_sound": "",
            "default_tts": "Alert {name}",
            "alert_threshold": 0.98,
            "capture_directory": "ScreenEvents",
            "alert_only_new_content": True,
            "change_detection_sensitivity": 10,
            "content_analysis_enabled": True
        }
        import json
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    # Fast Nuitka build command (development mode)
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--windows-console-mode=disable",
        f"--output-dir={output_dir.absolute()}",
        "--output-filename=ScreenAlert-dev.exe",
        f"--include-data-files={config_file.name}={config_file.name}",
        "--jobs=4",
        "--lto=no",
        "--debug",  # Keep debug info for development
        "--show-progress",
        "--remove-output",
        "screenalert.py"
    ]
    
    print(f"Fast build command: {' '.join(nuitka_cmd)}")
    
    try:
        result = subprocess.run(nuitka_cmd, check=True, cwd=Path.cwd())
        
        # Check if the executable was created
        exe_path = output_dir / "ScreenAlert-dev.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nFast build successful!")
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB (development build)")
            print(f"Note: This is a development build with debug info")
            return True
        else:
            print(f"Build completed but executable not found at {exe_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"Build failed with error: {e}")
        return False

if __name__ == "__main__":
    success = fast_build()
    if not success:
        print("\nFast build failed.")
        sys.exit(1)
    else:
        print("\nFast build completed successfully!")
        print("Use build_nuitka.py for production builds.")
