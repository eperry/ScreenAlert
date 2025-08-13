# ScreenAlert - Auto-py-to-exe Builder
# GUI-based approach to building executables

import subprocess
import sys
import os

def install_auto_py_to_exe():
    """Install auto-py-to-exe if not present"""
    try:
        subprocess.run([sys.executable, "-c", "import auto_py_to_exe"], check=True, capture_output=True)
        print("✅ Auto-py-to-exe is already installed")
        return True
    except subprocess.CalledProcessError:
        print("📦 Installing auto-py-to-exe...")
        subprocess.run([sys.executable, "-m", "pip", "install", "auto-py-to-exe"], check=True)
        return True

def launch_auto_py_to_exe():
    """Launch the auto-py-to-exe GUI"""
    print("🚀 Launching auto-py-to-exe GUI...")
    print("📝 In the GUI, configure:")
    print("   - Script Location: screenalert.py")
    print("   - One File: Yes")
    print("   - Console Window: No (Window Based)")
    print("   - Additional Files: screenalert_config.json, default_config.json")
    print("   - Output Directory: dist")
    
    subprocess.run([sys.executable, "-m", "auto_py_to_exe"])

if __name__ == "__main__":
    print("🚀 ScreenAlert - Auto-py-to-exe Builder")
    print("=" * 45)
    
    if install_auto_py_to_exe():
        launch_auto_py_to_exe()
