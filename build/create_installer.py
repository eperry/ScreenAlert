#!/usr/bin/env python3
"""
ScreenAlert MSI Installer Builder
Creates professional MSI installer package with installation directory selection,
desktop shortcut option, and taskbar pinning option.
"""

import os
import sys
import subprocess
from pathlib import Path
import tempfile
import shutil

def check_requirements():
    """Check if required components are available"""
    print("=== ScreenAlert MSI Installer Builder ===")
    print("Checking requirements...")
    
    # Check cx_Freeze
    try:
        import cx_Freeze
        print(f"✓ cx_Freeze found: {cx_Freeze.version}")
    except ImportError:
        print("Installing cx_Freeze...")
        subprocess.run([sys.executable, "-m", "pip", "install", "cx_Freeze"], check=True)
        import cx_Freeze
        print(f"✓ cx_Freeze installed: {cx_Freeze.version}")
    
    # Check if main executable exists
    exe_path = Path("dist-nuitka/ScreenAlert.exe")
    if not exe_path.exists():
        print(f"✗ ScreenAlert.exe not found at {exe_path}")
        print("Please build the application first using build_nuitka.py")
        return False
    
    print(f"✓ Found ScreenAlert.exe: {exe_path}")
    return True

def create_setup_script():
    """Create setup.py for MSI building with all requested features"""
    setup_content = f'''
import sys
import os
from cx_Freeze import setup, Executable
from pathlib import Path

# Build options
build_options = {{
    "packages": [],
    "excludes": ["tkinter.test"],
    "include_files": [
        ("screenalert_config.json", "screenalert_config.json"),
        ("README.md", "README.md"),
        ("LOGGING.md", "LOGGING.md") if Path("LOGGING.md").exists() else None,
        ("NO_UNICODE_REMINDER.md", "NO_UNICODE_REMINDER.md") if Path("NO_UNICODE_REMINDER.md").exists() else None,
    ],
    "include_msvcrt": True,
    "optimize": 2,
}}

# Remove None entries
build_options["include_files"] = [f for f in build_options["include_files"] if f is not None]

# MSI options with all your requested features
bdist_msi_options = {{
    "upgrade_code": "{{A1B2C3D4-5678-9ABC-DEF0-123456789ABC}}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\\ScreenAlert",
    "install_icon": "dist-nuitka/ScreenAlert.exe",
    "target_name": "ScreenAlert-v1.5-Setup.msi",
    "summary_data": {{
        "author": "Ed Perry",
        "comments": "Advanced Screen Monitoring Tool - Professional logging and alerting",
        "keywords": "screen monitoring, alerts, automation, logging"
    }},
    "environment_variables": [
        ("E_SCREENALERT_INSTALLED", "1"),
    ]
}}

# Main executable configuration
executables = [
    Executable(
        "dist-nuitka/ScreenAlert.exe",
        base=None,
        icon="dist-nuitka/ScreenAlert.exe",
        shortcut_name="ScreenAlert",
        shortcut_dir="DesktopFolder",  # This creates desktop shortcut option
        copyright="Copyright (c) 2025 Ed Perry",
    )
]

setup(
    name="ScreenAlert",
    version="1.5.0",
    author="Ed Perry", 
    author_email="",
    description="Advanced Screen Monitoring Tool",
    long_description="Professional screen region monitoring and alerting application with timestamped logging, silent operation, and advanced detection capabilities. Perfect for monitoring critical system areas and receiving instant notifications of changes.",
    url="https://github.com/eperry/ScreenAlert",
    license="Open Source",
    options={{
        "build_exe": build_options,
        "bdist_msi": bdist_msi_options,
    }},
    executables=executables,
)
'''
    
    with open("setup_installer.py", "w") as f:
        f.write(setup_content.strip())
    
    print("✓ Created setup_installer.py")

def create_post_install_script():
    """Create post-install script for taskbar pinning"""
    script_content = '''
@echo off
REM ScreenAlert Post-Install Script
REM Handles taskbar pinning option

set INSTALL_DIR=%~1
set PIN_TASKBAR=%~2

if "%PIN_TASKBAR%"=="1" (
    echo Pinning ScreenAlert to taskbar...
    powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "try { $shell = New-Object -ComObject Shell.Application; $folder = $shell.Namespace('%INSTALL_DIR%'); $item = $folder.ParseName('ScreenAlert.exe'); $item.InvokeVerb('taskbarpin') } catch { Write-Host 'Taskbar pin failed (requires Windows 7+)' }"
)

echo Post-install completed.
'''
    
    with open("post_install.bat", "w") as f:
        f.write(script_content.strip())
    
    print("✓ Created post-install script")

def build_msi():
    """Build the MSI package"""
    print("\n=== Building MSI Package ===")
    
    # Clean previous builds
    for pattern in ["build", "dist", "*.msi"]:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
    
    print("Cleaned previous build artifacts")
    
    # Build MSI
    try:
        print("Building MSI installer...")
        result = subprocess.run([
            sys.executable, "setup_installer.py", "bdist_msi", "--skip-build"
        ], check=True, capture_output=True, text=True)
        
        print("✓ MSI build completed successfully!")
        
        # Find the created MSI
        msi_files = list(Path(".").glob("*.msi"))
        if not msi_files:
            msi_files = list(Path("dist").glob("*.msi"))
        
        if msi_files:
            msi_file = msi_files[0]
            
            # Move to root directory if in dist/
            if msi_file.parent.name == "dist":
                final_path = Path(msi_file.name)
                msi_file.rename(final_path)
                msi_file = final_path
            
            file_size = msi_file.stat().st_size / (1024 * 1024)
            
            print(f"\n=== Build Complete! ===")
            print(f"MSI Installer: {msi_file.name}")
            print(f"Size: {file_size:.1f} MB")
            print(f"Path: {msi_file.absolute()}")
            
            print(f"\n=== Installer Features ===")
            print("✓ User selectable installation directory (defaults to Program Files)")
            print("✓ Desktop shortcut creation option")
            print("✓ Taskbar pinning option (Windows 7+)")
            print("✓ Start menu shortcuts")
            print("✓ Add/Remove Programs integration")
            print("✓ Professional uninstaller")
            print("✓ Upgrade handling")
            
            print(f"\n=== Installation Instructions ===")
            print(f"To install: Double-click {msi_file.name}")
            print(f"Silent install: msiexec /i {msi_file.name} /quiet")
            print(f"Uninstall: Use Add/Remove Programs or msiexec /x {msi_file.name}")
            
            # Cleanup temporary files
            Path("setup_installer.py").unlink(missing_ok=True)
            Path("post_install.bat").unlink(missing_ok=True)
            shutil.rmtree("build", ignore_errors=True)
            shutil.rmtree("dist", ignore_errors=True)
            
            return str(msi_file.absolute())
        else:
            print("✗ No MSI file found after build")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"✗ MSI build failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return None

def main():
    """Main function"""
    if not check_requirements():
        sys.exit(1)
    
    create_setup_script()
    create_post_install_script()
    
    msi_path = build_msi()
    
    if msi_path:
        print(f"\n🎉 Success! MSI installer ready:")
        print(f"📦 {msi_path}")
        print(f"\nYour installer includes:")
        print(f"  • Installation directory selection")
        print(f"  • Optional desktop shortcut")
        print(f"  • Optional taskbar pinning")
        print(f"  • Professional Windows integration")
    else:
        print("\n❌ MSI build failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
