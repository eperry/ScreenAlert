# ScreenAlert - Embedded Python Distribution Builder
# Creates a portable distribution using Python's embedded version

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path

def download_embedded_python():
    """Download Python embedded distribution"""
    python_version = "3.11.9"  # Stable version
    arch = "amd64" if sys.maxsize > 2**32 else "win32"
    url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-embed-{arch}.zip"
    
    print(f"📦 Downloading Python {python_version} embedded ({arch})...")
    
    embedded_dir = Path("dist/ScreenAlert-Embedded")
    embedded_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = embedded_dir / "python-embedded.zip"
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        
        # Extract embedded Python
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(embedded_dir)
        
        zip_path.unlink()  # Remove zip file
        print("✅ Python embedded downloaded and extracted")
        return embedded_dir
    except Exception as e:
        print(f"❌ Failed to download embedded Python: {e}")
        return None

def create_embedded_distribution():
    """Create embedded distribution"""
    print("🔨 Creating embedded distribution...")
    
    # Download embedded Python
    embedded_dir = download_embedded_python()
    if not embedded_dir:
        return False
    
    # Copy ScreenAlert files
    files_to_copy = [
        "screenalert.py",
        "screenalert_config.json",
        "default_config.json"
    ]
    
    for file in files_to_copy:
        if os.path.exists(file):
            shutil.copy2(file, embedded_dir)
            print(f"📄 Copied {file}")
    
    # Install requirements using embedded pip
    pth_file = embedded_dir / "python311._pth"
    if pth_file.exists():
        # Enable site-packages
        content = pth_file.read_text()
        if "import site" not in content:
            pth_file.write_text(content + "\nimport site\n")
    
    # Get pip for embedded Python
    get_pip_path = embedded_dir / "get-pip.py"
    urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_path)
    
    # Install pip
    python_exe = embedded_dir / "python.exe"
    subprocess.run([str(python_exe), str(get_pip_path)], cwd=embedded_dir)
    
    # Install requirements
    if os.path.exists("screenalert_requirements.txt"):
        subprocess.run([
            str(python_exe), "-m", "pip", "install", 
            "-r", "../../../screenalert_requirements.txt", "--no-warn-script-location"
        ], cwd=embedded_dir)
    
    # Create launcher batch file
    launcher_content = f"""@echo off
cd /d "%~dp0"
python.exe screenalert.py %*
"""
    
    launcher_path = embedded_dir / "ScreenAlert.bat"
    launcher_path.write_text(launcher_content)
    
    print("✅ Embedded distribution created successfully!")
    print(f"📁 Location: {embedded_dir}")
    print("🚀 Run ScreenAlert.bat to start the application")
    
    return True

if __name__ == "__main__":
    print("🚀 ScreenAlert - Embedded Python Builder")
    print("=" * 45)
    create_embedded_distribution()
