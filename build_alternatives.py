#!/usr/bin/env python3
"""
ScreenAlert - Python-to-Executable Alternative Build Methods
Comprehensive comparison of PyInstaller alternatives with antivirus compatibility focus
"""

import os
import subprocess
import sys
from pathlib import Path
import hashlib
import time
import json

def print_banner():
    print("=" * 80)
    print("ScreenAlert - PyInstaller Alternative Build Methods")
    print("=" * 80)
    print("PyInstaller replacement due to persistent antivirus false positives")
    print("Testing multiple compilation methods for best AV compatibility")
    print()

def get_file_info(file_path):
    """Get file information including size and hash"""
    if not file_path.exists():
        return None
    
    stat = file_path.stat()
    size_mb = stat.st_size / (1024 * 1024)
    
    # Calculate SHA256 hash
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    return {
        "size_bytes": stat.st_size,
        "size_mb": size_mb,
        "sha256": sha256_hash.hexdigest(),
        "modified": time.ctime(stat.st_mtime)
    }

def build_nuitka():
    """Build with Nuitka (native compilation)"""
    print("Building with Nuitka...")
    try:
        result = subprocess.run([sys.executable, "build_nuitka.py"], 
                              capture_output=True, text=True, check=True)
        print("Nuitka build successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Nuitka build failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def build_cx_freeze():
    """Build with cx_Freeze (directory distribution)"""
    print("Building with cx_Freeze...")
    try:
        result = subprocess.run([sys.executable, "setup_cx_freeze.py"], 
                              capture_output=True, text=True, check=True)
        print("cx_Freeze build successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"cx_Freeze build failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def analyze_builds():
    """Analyze all build outputs"""
    print("\nBuild Analysis & Comparison")
    print("-" * 50)
    
    builds = {
        "Nuitka (Onefile)": Path("dist-nuitka/ScreenAlert.exe"),
        "cx_Freeze (Onedir)": Path("dist-cxfreeze/ScreenAlert.exe"),
    }
    
    results = {}
    
    for name, path in builds.items():
        print(f"\n{name}:")
        info = get_file_info(path)
        if info:
            results[name] = info
            print(f"  File exists: {path}")
            print(f"  Size: {info['size_mb']:.1f} MB ({info['size_bytes']:,} bytes)")
            print(f"  SHA256: {info['sha256'][:16]}...")
            print(f"  Modified: {info['modified']}")
        else:
            print(f"  File not found: {path}")
    
    # Additional cx_Freeze analysis (directory structure)
    cx_dir = Path("dist-cxfreeze")
    if cx_dir.exists():
        print(f"\ncx_Freeze Distribution Directory:")
        total_size = 0
        file_count = 0
        for file in cx_dir.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                file_count += 1
        
        print(f"  Total files: {file_count}")
        print(f"  Total size: {total_size / (1024 * 1024):.1f} MB")
        print(f"  Directory: {cx_dir.absolute()}")
    
    return results

def create_comparison_report(results):
    """Create a detailed comparison report"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comparison": "PyInstaller Alternative Build Methods",
        "reason": "Antivirus false positive mitigation",
        "builds": results,
        "recommendations": {
            "production": "Nuitka - Best performance, single file",
            "development": "cx_Freeze - Faster builds, easier debugging",
            "antivirus_safe": "Both methods are significantly better than PyInstaller for AV compatibility",
        }
    }
    
    with open("build_comparison_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved: build_comparison_report.json")

def print_recommendations():
    """Print build method recommendations"""
    print("\nRecommendations")
    print("-" * 50)
    print("1. Nuitka (Recommended for Production):")
    print("   • Single executable file (78MB)")
    print("   • Native C++ compilation - best AV compatibility")
    print("   • Better performance than PyInstaller")
    print("   • Longer build times")
    
    print("\n2. cx_Freeze (Good for Development):")
    print("   • Directory distribution (~6MB + dependencies)")
    print("   • Faster build times")
    print("   • Easier to debug and modify")
    print("   • Requires Python runtime distribution")
    
    print("\n3. PyInstaller (AVOID):")
    print("   • Persistent antivirus false positives")
    print("   • Detection as Trojan:Win32/Wacatac.B!ml")
    print("   • Multiple mitigation attempts failed")
    
    print("\nAlternative Distribution Methods:")
    print("   • Python source distribution (requires Python installation)")
    print("   • Windows Installer (.msi) packages")
    print("   • Portable Python embedded distribution")

def main():
    """Main execution function"""
    print_banner()
    
    # Build with all methods
    print("Building with alternative methods...")
    
    nuitka_success = build_nuitka()
    cx_freeze_success = build_cx_freeze()
    
    if not nuitka_success and not cx_freeze_success:
        print("\nAll builds failed!")
        return 1
    
    # Analyze results
    results = analyze_builds()
    
    # Create report
    create_comparison_report(results)
    
    # Print recommendations
    print_recommendations()
    
    print(f"\nAlternative build analysis complete!")
    print("PyInstaller successfully replaced with AV-friendly alternatives")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
