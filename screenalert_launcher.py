"""
ScreenAlert Launcher - Antivirus-friendly version
This launcher downloads and runs ScreenAlert from source to avoid AV detection
"""

import os
import sys
import subprocess
import tempfile
import urllib.request
import zipfile
import json
from pathlib import Path

class ScreenAlertLauncher:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="screenalert_")
        self.repo_url = "https://github.com/eperry/ScreenAlert/archive/refs/heads/main.zip"
        
    def download_and_extract(self):
        """Download and extract ScreenAlert source"""
        print("📥 Downloading ScreenAlert source...")
        
        zip_path = os.path.join(self.temp_dir, "screenalert.zip")
        urllib.request.urlretrieve(self.repo_url, zip_path)
        
        print("📦 Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
            
        # Find the extracted directory
        extracted_dirs = [d for d in os.listdir(self.temp_dir) if d.startswith("ScreenAlert-")]
        if not extracted_dirs:
            raise Exception("Could not find extracted ScreenAlert directory")
            
        self.source_dir = os.path.join(self.temp_dir, extracted_dirs[0])
        print(f"✅ Source extracted to: {self.source_dir}")
        
    def install_dependencies(self):
        """Install required Python packages"""
        print("📚 Installing dependencies...")
        
        requirements_file = os.path.join(self.source_dir, "screenalert_requirements.txt")
        if os.path.exists(requirements_file):
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", requirements_file, "--quiet"
            ], check=True)
        else:
            # Install core dependencies manually
            packages = [
                "pyautogui", "Pillow", "scikit-image", "numpy", 
                "opencv-python", "imagehash", "pyttsx3", "pywin32"
            ]
            for package in packages:
                subprocess.run([
                    sys.executable, "-m", "pip", "install", package, "--quiet"
                ], check=False)  # Don't fail if one package fails
                
        print("✅ Dependencies installed")
        
    def run_screenalert(self):
        """Run ScreenAlert from source"""
        print("🚀 Starting ScreenAlert...")
        
        script_path = os.path.join(self.source_dir, "screenalert.py")
        if not os.path.exists(script_path):
            raise Exception(f"ScreenAlert script not found at {script_path}")
            
        # Change to source directory and run
        original_cwd = os.getcwd()
        try:
            os.chdir(self.source_dir)
            subprocess.run([sys.executable, "screenalert.py"], check=True)
        finally:
            os.chdir(original_cwd)
            
    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
            
    def launch(self):
        """Main launch sequence"""
        try:
            print("🛡️  ScreenAlert Antivirus-Safe Launcher")
            print("=" * 50)
            print("This launcher runs ScreenAlert from source code to avoid")
            print("false positive antivirus detections with compiled executables.")
            print("")
            
            self.download_and_extract()
            self.install_dependencies()
            self.run_screenalert()
            
        except KeyboardInterrupt:
            print("\n⏹️  Cancelled by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("\nTroubleshooting:")
            print("1. Check your internet connection")
            print("2. Ensure Python and pip are working")
            print("3. Try running as administrator")
            input("\nPress Enter to exit...")
        finally:
            self.cleanup()

if __name__ == "__main__":
    launcher = ScreenAlertLauncher()
    launcher.launch()
