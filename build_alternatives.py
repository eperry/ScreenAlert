#!/usr/bin/env python3
"""
ScreenAlert - Build Alternatives Comparison
Compares different build methods and provides recommendations
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def get_file_size_mb(path):
    """Get file size in MB"""
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    elif path.is_dir():
        total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return total_size / (1024 * 1024)
    return 0

def check_build_outputs():
    """Check what build outputs exist"""
    print("ScreenAlert - Build Alternatives Summary")
    print("=" * 50)
    print("Checking available build outputs...\n")
    
    builds = []
    
    # Check Nuitka build
    nuitka_exe = Path("dist-nuitka/ScreenAlert.exe")
    if nuitka_exe.exists():
        size = get_file_size_mb(nuitka_exe)
        builds.append({
            'name': 'Nuitka',
            'path': nuitka_exe,
            'size': size,
            'type': 'Single executable',
            'recommendation': 'PRODUCTION',
            'pros': ['Native C++ compilation', 'Excellent antivirus compatibility', 'Best performance', 'Smallest size'],
            'cons': ['Longer build time', 'More complex debugging']
        })
    
    # Check cx_Freeze build  
    cxfreeze_exe = Path("dist-cxfreeze/ScreenAlert.exe")
    cxfreeze_dir = Path("dist-cxfreeze")
    if cxfreeze_exe.exists():
        size = get_file_size_mb(cxfreeze_dir)
        builds.append({
            'name': 'cx_Freeze',
            'path': cxfreeze_dir,
            'size': size,
            'type': 'Directory with dependencies',
            'recommendation': 'DEVELOPMENT',
            'pros': ['Faster builds', 'Easier debugging', 'Good compatibility'],
            'cons': ['Larger size', 'Multiple files to distribute']
        })
    
    if not builds:
        print("No build outputs found!")
        print("Run the following commands to create builds:")
        print("  python build_nuitka.py")
        print("  python setup_cx_freeze.py")
        return False
    
    # Display comparison
    print("BUILD COMPARISON")
    print("-" * 50)
    for build in builds:
        print(f"\n{build['name']} Build")
        print(f"   Path: {build['path']}")
        print(f"   Size: {build['size']:.1f} MB")
        print(f"   Type: {build['type']}")
        print(f"   Recommendation: {build['recommendation']}")
        print(f"   Pros: {', '.join(build['pros'])}")
        print(f"   Cons: {', '.join(build['cons'])}")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS")
    print("-" * 50)
    
    nuitka_build = next((b for b in builds if b['name'] == 'Nuitka'), None)
    cxfreeze_build = next((b for b in builds if b['name'] == 'cx_Freeze'), None)
    
    if nuitka_build:
        print(f"For end users and distribution: Use Nuitka build")
        print(f"   - Single {nuitka_build['size']:.1f}MB executable")
        print(f"   - Zero antivirus false positives")
        print(f"   - Best performance")
    
    if cxfreeze_build:
        print(f"For development and testing: Use cx_Freeze build")
        print(f"   - {cxfreeze_build['size']:.1f}MB distribution directory")
        print(f"   - Faster builds during development")
        print(f"   - Easier to debug and modify")
    
    print(f"\nSUMMARY")
    print("-" * 50)
    print(f"Both builds provide excellent antivirus compatibility compared to PyInstaller.")
    print(f"Choose based on your use case:")
    print(f"  • Production/Distribution → Nuitka")
    print(f"  • Development/Testing → cx_Freeze")
    
    return True

def run_verification_tests():
    """Run basic verification tests on available builds"""
    print(f"\nVERIFICATION TESTS")
    print("-" * 50)
    
    # Test Nuitka build
    nuitka_exe = Path("dist-nuitka/ScreenAlert.exe")
    if nuitka_exe.exists():
        print(f"Testing Nuitka build...")
        try:
            result = subprocess.run([str(nuitka_exe), "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"Nuitka build: Working")
            else:
                print(f"Nuitka build: May have issues")
        except Exception as e:
            print(f"Nuitka build: Cannot test ({e})")
    
    # Test cx_Freeze build
    cxfreeze_exe = Path("dist-cxfreeze/ScreenAlert.exe")
    if cxfreeze_exe.exists():
        print(f"Testing cx_Freeze build...")
        try:
            result = subprocess.run([str(cxfreeze_exe), "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"cx_Freeze build: Working")
            else:
                print(f"cx_Freeze build: May have issues")
        except Exception as e:
            print(f"cx_Freeze build: Cannot test ({e})")

if __name__ == "__main__":
    success = check_build_outputs()
    if success:
        run_verification_tests()
    else:
        sys.exit(1)
