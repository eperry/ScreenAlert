#!/usr/bin/env python3
"""
Nuitka Build Script for ScreenAlert
Alternative to PyInstaller with better antivirus compatibility
"""

import subprocess
import sys
import os
from pathlib import Path

def install_nuitka():
    """Install Nuitka if not present"""
    try:
        import nuitka
        print("Nuitka is already installed")
        return True
    except ImportError:
        print("Installing Nuitka...")
        subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
        return True

def build_with_nuitka():
    """Build ScreenAlert using Nuitka compiler"""
    
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Create output directory
    output_dir = script_dir / "dist-nuitka"
    output_dir.mkdir(exist_ok=True)
    
    print("Building ScreenAlert with Nuitka...")
    
    # Nuitka build command
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--standalone", 
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--enable-plugin=numpy",
        "--windows-console-mode=disable",
        "--product-name=ScreenAlert",
        "--file-description=Screen monitoring and alert system",
        "--product-version=1.0.0",
        "--file-version=1.0.0.0",
        "--copyright=© 2025 ScreenAlert",
        f"--output-dir={output_dir}",
        "--output-filename=ScreenAlert.exe",
        "--include-data-files=screenalert_config.json=screenalert_config.json",
        "--remove-output",
        "--report=compilation-report.xml",
        "screenalert.py"
    ]
    
    # Add icon if it exists
    icon_path = script_dir / "screenalert_icon.ico"
    if icon_path.exists():
        nuitka_cmd.insert(-1, f"--windows-icon-from-ico={icon_path}")
    
    print("Command:", " ".join(nuitka_cmd))
    print()
    
    try:
        result = subprocess.run(nuitka_cmd, check=True, capture_output=False)
        
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"\nBuild completed successfully!")
            print(f"Executable created: {exe_path}")
            print(f"File size: {file_size:.1f} MB")
            
            # Show file info
            print(f"\nFile details:")
            print(f"Path: {exe_path}")
            print(f"Size: {exe_path.stat().st_size:,} bytes")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"Build failed with error: {e}")
        return False

if __name__ == "__main__":
    print("ScreenAlert - Nuitka Builder")
    print("=" * 40)
    print("Nuitka produces native executables with better antivirus compatibility")
    print()
    
    if install_nuitka():
        success = build_with_nuitka()
        sys.exit(0 if success else 1)
