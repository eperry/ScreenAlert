#!/usr/bin/env python3
"""
ScreenAlert - Universal Build Script
Provides multiple compilation options to avoid antivirus false positives
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

class ScreenAlertBuilder:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.dist_dir = self.base_dir / "dist"
        self.dist_dir.mkdir(exist_ok=True)
    
    def print_banner(self):
        print("🚀 ScreenAlert Universal Builder")
        print("=" * 50)
        print("Choose your compilation method:")
        print("1. Nuitka (Recommended - Native compilation)")
        print("2. cx_Freeze (Alternative compiler)")
        print("3. Auto-py-to-exe (GUI-based)")
        print("4. Embedded Python (Most AV-friendly)")
        print("5. Source Distribution (Zero AV issues)")
        print("=" * 50)
    
    def install_package(self, package_name):
        """Install a package if not present"""
        try:
            __import__(package_name.replace('-', '_'))
            print(f"✅ {package_name} is already installed")
            return True
        except ImportError:
            print(f"📦 Installing {package_name}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package_name], check=True)
            return True
        except Exception as e:
            print(f"❌ Failed to install {package_name}: {e}")
            return False
    
    def build_nuitka(self):
        """Build with Nuitka"""
        print("\n🔨 Building with Nuitka...")
        
        if not self.install_package("nuitka"):
            return False
        
        cmd = [
            sys.executable, "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--windows-disable-console",
            "--enable-plugin=tk-inter",
            "--output-filename=ScreenAlert-Nuitka.exe",
            "--output-dir=dist",
            "screenalert.py"
        ]
        
        try:
            subprocess.run(cmd, check=True, cwd=self.base_dir)
            print("✅ Nuitka build completed!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Nuitka build failed: {e}")
            return False
    
    def build_cxfreeze(self):
        """Build with cx_Freeze"""
        print("\n🔨 Building with cx_Freeze...")
        
        if not self.install_package("cx_Freeze"):
            return False
        
        try:
            subprocess.run([sys.executable, "setup_cxfreeze.py", "build"], 
                         check=True, cwd=self.base_dir)
            print("✅ cx_Freeze build completed!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ cx_Freeze build failed: {e}")
            return False
    
    def build_auto_py_to_exe(self):
        """Launch auto-py-to-exe GUI"""
        print("\n🚀 Launching auto-py-to-exe...")
        
        if not self.install_package("auto-py-to-exe"):
            return False
        
        print("📝 Configure these settings in the GUI:")
        print("   - Script: screenalert.py")
        print("   - One File: Yes")
        print("   - Console: No")
        print("   - Output: dist")
        
        subprocess.run([sys.executable, "-m", "auto_py_to_exe"], cwd=self.base_dir)
        return True
    
    def build_embedded(self):
        """Build embedded Python distribution"""
        print("\n🔨 Building embedded distribution...")
        
        try:
            subprocess.run([sys.executable, "build_embedded.py"], 
                         check=True, cwd=self.base_dir)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Embedded build failed: {e}")
            return False
    
    def build_source_dist(self):
        """Create source distribution"""
        print("\n📦 Creating source distribution...")
        
        import shutil
        
        # Create source distribution directory
        source_dist = self.dist_dir / "ScreenAlert-Source"
        if source_dist.exists():
            shutil.rmtree(source_dist)
        source_dist.mkdir()
        
        # Files to include
        files_to_copy = [
            "screenalert.py",
            "screenalert_requirements.txt", 
            "screenalert_config.json",
            "default_config.json",
            "README.md"
        ]
        
        for file in files_to_copy:
            if (self.base_dir / file).exists():
                shutil.copy2(self.base_dir / file, source_dist)
        
        # Create runner script
        runner_content = """@echo off
echo Installing requirements...
python -m pip install -r screenalert_requirements.txt --quiet
echo Starting ScreenAlert...
python screenalert.py %*
"""
        
        (source_dist / "Run-ScreenAlert.bat").write_text(runner_content)
        
        print("✅ Source distribution created!")
        print(f"📁 Location: {source_dist}")
        return True
    
    def interactive_build(self):
        """Interactive build selection"""
        self.print_banner()
        
        while True:
            try:
                choice = input("\nSelect build method (1-5) or 'q' to quit: ").strip()
                
                if choice.lower() == 'q':
                    break
                
                choice = int(choice)
                
                if choice == 1:
                    self.build_nuitka()
                elif choice == 2:
                    self.build_cxfreeze()
                elif choice == 3:
                    self.build_auto_py_to_exe()
                elif choice == 4:
                    self.build_embedded()
                elif choice == 5:
                    self.build_source_dist()
                else:
                    print("❌ Invalid choice. Please select 1-5.")
                    continue
                
                another = input("\nBuild another version? (y/n): ").strip().lower()
                if another not in ['y', 'yes']:
                    break
                    
            except ValueError:
                print("❌ Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n👋 Build cancelled.")
                break

def main():
    parser = argparse.ArgumentParser(description="ScreenAlert Universal Builder")
    parser.add_argument("--method", choices=["nuitka", "cxfreeze", "auto", "embedded", "source"],
                       help="Build method to use")
    parser.add_argument("--interactive", action="store_true", default=True,
                       help="Interactive mode (default)")
    
    args = parser.parse_args()
    
    builder = ScreenAlertBuilder()
    
    if args.method:
        if args.method == "nuitka":
            builder.build_nuitka()
        elif args.method == "cxfreeze":
            builder.build_cxfreeze()
        elif args.method == "auto":
            builder.build_auto_py_to_exe()
        elif args.method == "embedded":
            builder.build_embedded()
        elif args.method == "source":
            builder.build_source_dist()
    else:
        builder.interactive_build()

if __name__ == "__main__":
    main()
