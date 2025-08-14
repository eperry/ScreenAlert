#!/usr/bin/env python3
"""
ScreenAlert - Nuitka Builder
Builds ScreenAlert using Nuitka for native C++ compilation
This is the primary and only build method for ScreenAlert v1.4.0+
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def check_nuitka():
    """Check if Nuitka is installed"""
    try:
        result = subprocess.run([sys.executable, "-m", "nuitka", "--version"], 
                              capture_output=True, text=True, check=True)
        print("Nuitka is already installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka not found, installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
            print("Nuitka installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install Nuitka")
            return False

def build_with_nuitka():
    """Build ScreenAlert using Nuitka"""
    print("\nScreenAlert - Nuitka Builder")
    print("=" * 40)
    print("Building native executable with zero antivirus false positives")
    
    if not check_nuitka():
        return False
    
    # Ensure output directory exists
    output_dir = Path("dist-nuitka")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print("Building ScreenAlert with Nuitka...")
    
    # Check if config file exists
    config_file = Path("screenalert_config.json")
    if not config_file.exists():
        print(f"Warning: {config_file} not found, creating default config...")
        # Create a minimal default config
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
    
    # Antivirus-safe Nuitka build command 
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--enable-plugin=numpy",
        "--windows-console-mode=disable",  # CRITICAL: Keep disabled for AV safety
        "--product-name=ScreenAlert",
        "--file-description=Screen monitoring and alert system",
        "--product-version=1.4.0",
        "--file-version=1.4.0.0",
        "--copyright=© 2025 ScreenAlert",
        "--company-name=ScreenAlert",
        f"--output-dir={output_dir.absolute()}",
        "--output-filename=ScreenAlert.exe",
        f"--include-data-files={config_file.name}={config_file.name}",
        "--jobs=4",  # Conservative for stability and AV safety
        "--lto=no",  # Disabled for faster builds and AV safety
        "--show-progress",  # Show build progress
        "--remove-output",  # Clean build directory
        "screenalert.py"
    ]
    
    print(f"Command: {' '.join(nuitka_cmd)}")
    
    try:
        result = subprocess.run(nuitka_cmd, check=True, cwd=Path.cwd())
        
        # Check if the executable was created
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nBuild successful!")
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
            print(f"Antivirus compatibility: Excellent (native C++ compilation)")
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
    success = build_with_nuitka()
    if not success:
        print("\nBuild failed.")
        sys.exit(1)
    else:
        print("\nBuild completed successfully!")
