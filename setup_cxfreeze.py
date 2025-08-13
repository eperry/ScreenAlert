# ScreenAlert - cx_Freeze Setup
# cx_Freeze is another Python-to-executable compiler

from cx_Freeze import setup, Executable
import sys
import os

# Dependencies to include
packages = [
    "tkinter", "PIL", "cv2", "numpy", "json", "time", "threading",
    "datetime", "hashlib", "base64", "argparse", "configparser"
]

# Files to include
include_files = []
if os.path.exists("default_config.json"):
    include_files.append("default_config.json")
if os.path.exists("screenalert_config.json"):
    include_files.append("screenalert_config.json")

# Build options
build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "excludes": ["unittest", "test", "distutils"],
    "zip_include_packages": ["*"],
    "zip_exclude_packages": []
}

# Base for Windows (no console)
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# Executable configuration
executable = Executable(
    "screenalert.py",
    base=base,
    target_name="ScreenAlert-cxFreeze.exe",
    icon="icon.ico" if os.path.exists("icon.ico") else None
)

setup(
    name="ScreenAlert",
    version="1.3.5",
    description="Screen monitoring and alert system",
    options={"build_exe": build_exe_options},
    executables=[executable]
)
