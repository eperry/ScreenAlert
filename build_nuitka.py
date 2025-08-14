#!/usr/bin/env python3
"""
ScreenAlert - Nuitka Builder
Builds ScreenAlert using Nuitka for native C++ compilation with pre-compilation optimizations
This is the primary and only build method for ScreenAlert v1.4.1+
"""

import subprocess
import sys
import os
import shutil
import json
import glob
from pathlib import Path

def find_signtool():
    """Find signtool.exe in Windows SDK"""
    if not sys.platform.startswith('win'):
        return None
        
    possible_paths = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files (x86)\Microsoft SDKs\Windows\*\bin\signtool.exe",
    ]
    
    for pattern in possible_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[-1]  # Return the latest version
    
    return None

def sign_executable_if_possible(exe_path):
    """Sign the executable if certificate and signtool are available"""
    
    # Check if we're on Windows
    if not sys.platform.startswith('win'):
        return False
    
    # Find signtool
    signtool = find_signtool()
    if not signtool:
        return False
    
    # Look for certificate files
    cert_files = [
        "ScreenAlert-Certificate.pfx",
        "certificate.pfx",
        "code-signing.pfx"
    ]
    
    cert_path = None
    for cert_file in cert_files:
        if Path(cert_file).exists():
            cert_path = cert_file
            break
    
    # Also check environment variables for GitHub Actions
    if not cert_path:
        cert_base64 = os.environ.get('SIGNING_CERTIFICATE')
        cert_password = os.environ.get('SIGNING_PASSWORD')
        if cert_base64:
            # Decode base64 certificate for GitHub Actions
            import base64
            cert_path = "temp_certificate.pfx"
            with open(cert_path, "wb") as f:
                f.write(base64.b64decode(cert_base64))
    
    if not cert_path:
        return False
    
    # Get password
    password = os.environ.get('SIGNING_PASSWORD', 'ScreenAlert2025!')
    
    # Build signtool command
    cmd = [
        signtool, "sign",
        "/f", cert_path,
        "/p", password,
        "/t", "http://timestamp.digicert.com",  # Timestamp server
        "/v",  # Verbose
        str(exe_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Clean up temporary certificate
        if cert_path == "temp_certificate.pfx":
            os.remove(cert_path)
        
        return True
    except subprocess.CalledProcessError:
        # Clean up temporary certificate on failure too
        if cert_path == "temp_certificate.pfx" and os.path.exists(cert_path):
            os.remove(cert_path)
        return False
    except Exception:
        return False

def check_nuitka():
    """Check if Nuitka is installed"""
    try:
        result = subprocess.run([sys.executable, "-m", "nuitka", "--version"], 
                              capture_output=True, text=True, check=True)
        print("Nuitka is already installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka not found, installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
            print("Nuitka installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install Nuitka")
            return False

def load_optimization_config():
    """Load optimization configuration if available"""
    config_path = Path("nuitka_optimization_config.json")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load optimization config: {e}")
    return None

def ensure_config_exists():
    """Ensure configuration file exists"""
    config_file = Path("screenalert_config.json")
    if not config_file.exists():
        print(f"Warning: {config_file} not found, creating default config...")
        default_config = {
            "regions": [],
            "interval": 1500,
            "highlight_time": 5,
            "default_sound": "",
            "default_tts": "Alert {name}",
            "alert_threshold": 0.98,
            "capture_directory": "ScreenEvents",
            "alert_only_new_content": True,
            "change_detection_sensitivity": 10,
            "content_analysis_enabled": True
        }
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)

def build_with_nuitka():
    """Build ScreenAlert using Nuitka for native compilation (antivirus-safe)."""
    
    print("🚀 Building ScreenAlert with Nuitka (Antivirus-Safe + Pre-compiled Optimizations)")
    print("=" * 80)
    
    if not check_nuitka():
        return False
    
    # Load optimization config if available
    optimization_config = load_optimization_config()
    if optimization_config:
        print("🔧 Using pre-compiled module optimizations...")
    
    # Ensure output directory exists
    output_dir = Path("dist-nuitka")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Ensure config file exists
    ensure_config_exists()
    
    print("Building ScreenAlert with Nuitka...")
    
    # Antivirus-safe Nuitka command with pre-compilation optimizations
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--onefile',
        '--assume-yes-for-downloads',
        '--enable-plugin=tk-inter',
        '--enable-plugin=numpy',
        '--windows-console-mode=disable',  # CRITICAL: Keep disabled for AV safety
        '--product-name=ScreenAlert',
        '--file-description=Screen monitoring and alert system',
        '--product-version=1.4.2',
        '--file-version=1.4.2.0',
        '--copyright=© 2025 ScreenAlert',
        '--company-name=ScreenAlert',
        f'--output-dir={output_dir.absolute()}',
        '--output-filename=ScreenAlert.exe',
        '--include-data-files=screenalert_config.json=screenalert_config.json',
        '--jobs=4',  # Conservative for stability
        '--lto=no',  # Disabled for faster builds and AV safety
        '--no-prefer-source-code',  # Use bytecode for faster compilation
        '--python-flag=no_docstrings',  # Remove docstrings
        '--python-flag=no_asserts',  # Remove assert statements for production
        '--show-progress',
        '--show-memory',
        '--remove-output',  # Clean build directory
        'screenalert.py'
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, cwd=Path.cwd())
        
        # Check if the executable was created
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nBuild successful!")
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
            print(f"Antivirus compatibility: Excellent (native C++ compilation)")
            return True
        else:
            print(f"Build completed but executable not found at {exe_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"Build failed with error: {e}")
        return False
    
    print(f"Command: {' '.join(nuitka_cmd)}")
    
    try:
        result = subprocess.run(nuitka_cmd, check=True, cwd=Path.cwd())
        
        # Check if the executable was created
        exe_path = output_dir / "ScreenAlert.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nBuild successful!")
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
            print(f"Antivirus compatibility: Excellent (native C++ compilation)")
            
            # Attempt code signing if certificate is available
            try:
                sign_result = sign_executable_if_possible(exe_path)
                if sign_result:
                    print(f"✅ Executable signed successfully!")
                else:
                    print(f"ℹ️  Executable not signed (certificate not available)")
            except Exception as e:
                print(f"⚠️  Code signing failed: {e}")
            
            return True
        else:
            print(f"Build completed but executable not found at {exe_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        return False
    except Exception as e:
        print(f"Build failed with error: {e}")
        return False

if __name__ == "__main__":
    success = build_with_nuitka()
    if not success:
        print("\nBuild failed.")
        sys.exit(1)
    else:
        print("\nBuild completed successfully!")
