# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Add any additional data files or directories your app needs
datas = []

# Add default config file (always included)
if os.path.exists('default_config.json'):
    datas.append(('default_config.json', '.'))

# Add user config file if it exists (optional)
if os.path.exists('screenalert_config.json'):
    datas.append(('screenalert_config.json', '.'))

# Add documentation files if they exist
if os.path.exists('SCREENALERT_README.md'):
    datas.append(('SCREENALERT_README.md', '.'))
if os.path.exists('README.md'):
    datas.append(('README.md', '.'))

# Hidden imports that PyInstaller might miss - minimal set to reduce AV flags
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'cv2',
    'numpy',
    'pyautogui',
    'pyttsx3',
    'win32gui',
    'win32con',
    'win32api',
    'argparse',
    'skimage',
    'skimage.metrics',
    'imagehash',
]

# Exclude modules that might trigger AV detection - minimal exclusions only
excludes = [
    'matplotlib',
]

# Analysis configuration
a = Analysis(
    ['screenalert.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScreenAlert',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression which can trigger AV
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want console window for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have an icon
    version_info={
        'version': (1, 2, 0, 0),
        'file_version': (1, 2, 0, 0),
        'product_version': (1, 2, 0, 0),
        'file_description': 'ScreenAlert - Advanced Screen Monitoring Tool',
        'product_name': 'ScreenAlert',
        'company_name': 'Ed Perry',
        'legal_copyright': '© 2025 Ed Perry. All rights reserved.',
        'internal_name': 'ScreenAlert.exe',
        'original_filename': 'ScreenAlert.exe',
    }
)
