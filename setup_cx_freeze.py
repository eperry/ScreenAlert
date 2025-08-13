#!/usr/bin/env python3
"""
ScreenAlert - cx_Freeze Builder
Builds ScreenAlert using cx_Freeze for distribution
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def check_cx_freeze():
    """Check if cx_Freeze is installed"""
    try:
        import cx_Freeze
        print("cx_Freeze is already installed")
        return True
    except ImportError:
        print("cx_Freeze not found, installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "cx_Freeze"], check=True)
            print("cx_Freeze installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install cx_Freeze")
            return False

def build_with_cx_freeze():
    """Build ScreenAlert using cx_Freeze"""
    print("\nScreenAlert - cx_Freeze Builder")
    print("=" * 40)
    print("cx_Freeze creates distributable Python applications")
    
    if not check_cx_freeze():
        return False
    
    # Ensure output directory exists
    output_dir = Path("dist-cxfreeze")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print("Building ScreenAlert with cx_Freeze...")
    
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
    
    # Create a temporary setup.py file for cx_Freeze
    setup_content = f'''
import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_options = {{
    'packages': ['tkinter', 'PIL', 'numpy', 'cv2', 'pyttsx3', 'playsound', 'pygetwindow', 'pyautogui'],
    'excludes': [],
    'include_files': ['{config_file.name}'],
    'build_exe': '{output_dir.name}'
}}

base = 'Win32GUI' if sys.platform == 'win32' else None

executables = [
    Executable('screenalert.py', base=base, target_name='ScreenAlert.exe')
]

setup(
    name='ScreenAlert',
    version='1.0.0',
    description='Screen monitoring and alert system',
    options={{'build_exe': build_options}},
    executables=executables
)
'''
    
    setup_file = Path("setup_temp_cx.py")
    with open(setup_file, 'w') as f:
        f.write(setup_content)
    
    try:
        # Run cx_Freeze build
        result = subprocess.run([
            sys.executable, "setup_temp_cx.py", "build_exe"
        ], check=True, cwd=Path.cwd())
        
        # Check if the build was successful
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            # Calculate directory size
            total_size = sum(f.stat().st_size for f in output_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            
            print(f"\\n✅ Build successful!")
            print(f"📁 Output: {output_dir}/")
            print(f"📊 Size: {size_mb:.1f} MB (directory)")
            print(f"🚀 Antivirus compatibility: Good (Python runtime)")
            return True
        else:
            print(f"❌ Build completed but executable not found at {exe_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"Build failed with error: {e}")
        return False
    finally:
        # Clean up temporary setup file
        if setup_file.exists():
            setup_file.unlink()

if __name__ == "__main__":
    success = build_with_cx_freeze()
    if not success:
        print("\\nBuild failed.")
        sys.exit(1)
    else:
        print("\\nBuild completed successfully!")
