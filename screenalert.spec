# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Add any additional data files or directories your app needs
datas = [
    ('screenalert_config.json', '.'),
    ('SCREENALERT_README.md', '.'),
    ('README.md', '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'PIL._tkinter_finder',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.colorchooser',
    'cv2',
    'numpy',
    'pyautogui',
    'pyttsx3',
    'win32gui',
    'win32con',
    'win32api',
    'imagehash',
    'skimage',
    'skimage.metrics',
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
    excludes=[],
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
    upx=True,
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
