#!/usr/bin/env python3
"""
Robust Nuitka Build Script for ScreenAlert
Tests module availability and creates a stable build configuration
"""

import sys
import subprocess
import os
from pathlib import Path

def check_module_availability():
    """Check which optional modules are available"""
    available_modules = []
    
    # Test modules and their Nuitka include flags
    test_modules = {
        'win32com.client': '--include-module=win32com --include-module=win32com.client',
        'pyttsx3': '--include-module=pyttsx3',
        'winsound': '--include-module=winsound',
        'psutil': '--include-module=psutil'
    }
    
    print("[BUILD] Checking module availability...")
    
    for module_name, nuitka_flag in test_modules.items():
        try:
            __import__(module_name)
            available_modules.extend(nuitka_flag.split())
            print(f"  ✅ {module_name} - available")
        except ImportError:
            print(f"  ❌ {module_name} - not available")
    
    return available_modules

def build_screenalert():
    """Build ScreenAlert with Nuitka using only available modules"""
    
    print("=" * 60)
    print("ScreenAlert Robust Build Process")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path('screenalert.py').exists():
        print("[ERROR] screenalert.py not found. Please run from the project directory.")
        return False
    
    # Get available modules
    available_modules = check_module_availability()
    
    # Create output directory
    output_dir = Path("dist-nuitka")
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Create config file if it doesn't exist
    config_file = Path("screenalert_config.json")
    if not config_file.exists():
        import json
        default_config = {
            "regions": [],
            "interval": 1000,
            "highlight_time": 5,
            "default_sound": "",
            "default_tts": "Alert detected",
            "alert_threshold": 0.98
        }
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        print("[BUILD] Created default config file")
    
    # Build the Nuitka command with only core requirements
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--onefile',
        '--assume-yes-for-downloads',
        '--enable-plugin=tk-inter',
        '--windows-console-mode=disable',
        '--product-name=ScreenAlert',
        '--file-description=Screen monitoring and alert system',
        '--product-version=1.4.2.1',
        '--file-version=1.4.2.1',
        '--copyright=(C) 2025 ScreenAlert',
        '--company-name=ScreenAlert',
        f'--output-dir={output_dir.absolute()}',
        '--output-filename=ScreenAlert.exe',
        '--include-data-files=screenalert_config.json=screenalert_config.json',
        '--jobs=4',
        '--lto=no',
        '--no-prefer-source-code',
        '--python-flag=no_docstrings',
        '--python-flag=no_asserts',
        '--show-progress',
        '--show-memory',
        '--remove-output'
    ]
    
    # Add available modules
    cmd.extend(available_modules)
    
    # Add source file
    cmd.append('screenalert.py')
    
    print(f"\n[BUILD] Nuitka command:")
    print(" ".join(cmd))
    print()
    
    try:
        print("[BUILD] Starting compilation...")
        result = subprocess.run(cmd, check=True)
        
        # Check if executable was created
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n[SUCCESS] Build completed!")
            print(f"[SUCCESS] Executable: {exe_path}")
            print(f"[SUCCESS] Size: {size_mb:.1f} MB")
            return True
        else:
            print("[ERROR] Build completed but executable not found")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed with exit code: {e.returncode}")
        return False
    except Exception as e:
        print(f"[ERROR] Build failed: {e}")
        return False

if __name__ == "__main__":
    success = build_screenalert()
    sys.exit(0 if success else 1)
