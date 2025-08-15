#!/usr/bin/env python3
"""
ScreenAlert - Robust Nuitka Builder
Builds ScreenAlert using Nuitka with robust module detection and error handling
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
        print("[SIGN] signtool not found, attempting self-signed certificate...")
        try:
            # Try to use self-signed certificate approach
            import importlib.util
            spec = importlib.util.spec_from_file_location("create_selfsigned_cert", "create_selfsigned_cert.py")
            cert_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cert_module)
            return cert_module.sign_with_self_signed(exe_path)
        except Exception as e:
            print(f"[SIGN] Self-signed certificate failed: {e}")
            return False
    
    # Look for certificate files
    cert_files = [
        "ScreenAlert-Certificate.pfx",
        "certificate.pfx", 
        "code-signing.pfx",
        "ScreenAlert-SelfSigned.pfx"  # Add self-signed option
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
    
    # If no certificate found, try to create self-signed
    if not cert_path:
        print("[SIGN] No certificate found, creating self-signed certificate...")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("create_selfsigned_cert", "create_selfsigned_cert.py")
            cert_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cert_module)
            
            # Create self-signed certificate
            self_signed_path = "ScreenAlert-SelfSigned.pfx"
            if cert_module.create_self_signed_certificate(output_pfx=self_signed_path):
                cert_path = self_signed_path
            else:
                return False
        except Exception as e:
            print(f"[SIGN] Failed to create self-signed certificate: {e}")
            return False
    
    # Get password
    password = os.environ.get('SIGNING_PASSWORD', 'ScreenAlert2025!')
    
    # Build signtool command
    cmd = [
        signtool, "sign",
        "/f", cert_path,
        "/p", password,
        "/fd", "SHA256",  # File digest algorithm
        "/t", "http://timestamp.digicert.com",  # Timestamp server
        "/v",  # Verbose
        str(exe_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Clean up temporary certificate
        if cert_path == "temp_certificate.pfx":
            os.remove(cert_path)
        
        print(f"[SUCCESS] Executable signed with certificate: {cert_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Signing failed: {e.stderr}")
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
        print("[NUITKA] Already installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[NUITKA] Not found, installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
            print("[NUITKA] Installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("[ERROR] Failed to install Nuitka")
            return False

def ensure_config_exists():
    """Ensure configuration file exists"""
    config_file = Path("screenalert_config.json")
    if not config_file.exists():
        print(f"[CONFIG] Creating default config file...")
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

def build_with_nuitka(sign=True):
    """Build the application using Nuitka with robust module detection."""
    print("[BUILD] Starting robust Nuitka build...")
    
    if not check_nuitka():
        return False
    
    # Ensure config file exists
    ensure_config_exists()
    
    dist_dir = Path("dist-nuitka")
    if dist_dir.exists():
        print(f"[BUILD] Removing existing dist directory: {dist_dir}")
        try:
            shutil.rmtree(dist_dir)
        except PermissionError as e:
            print(f"[WARNING] Could not remove existing dist directory: {e}")
            print("[WARNING] This may be because the executable is still running or locked")
            print("[WARNING] Trying to continue with build anyway...")
            # Try to rename the directory instead
            import tempfile
            backup_dir = Path(tempfile.mktemp(prefix="dist-nuitka-backup-"))
            try:
                dist_dir.rename(backup_dir)
                print(f"[BUILD] Moved existing directory to {backup_dir}")
            except Exception as rename_error:
                print(f"[ERROR] Could not move existing directory: {rename_error}")
                print("[ERROR] Please close any running ScreenAlert instances and try again")
                return None
    
    # Base command with required plugins
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",  # Required for tkinter
        "--warn-implicit-exceptions",
        "--warn-unusual-code",
        "--output-dir=dist-nuitka",
        "--output-filename=ScreenAlert.exe",
        "--include-data-file=screenalert_config.json=screenalert_config.json",
        "screenalert.py"
    ]
    
    # Test and include optional modules with detailed availability checking
    optional_modules = []
    
    # TTS modules
    modules_to_test = [
        # TTS support
        ("pyttsx3", ["--include-module=pyttsx3", "--include-module=pyttsx3.drivers", "--include-module=pyttsx3.drivers.sapi5"]),
        ("win32com.client", ["--include-module=win32com.client", "--include-module=win32com.client.dynamic", "--include-module=win32com.client.gencache"]),
        
        # Core functionality
        ("psutil", ["--include-module=psutil"]),
        ("tkinter", ["--include-module=tkinter"]),
        
        # Image processing
        ("PIL", ["--include-module=PIL", "--include-module=PIL.Image", "--include-module=PIL.ImageTk"]),
        ("cv2", ["--include-module=cv2"]),
        ("numpy", ["--include-module=numpy"]),
        
        # GUI and automation
        ("pyautogui", ["--include-module=pyautogui"]),
        
        # Optional enhancements (commonly missing in CI)
        ("win32gui", ["--include-module=win32gui"]),
        ("win32api", ["--include-module=win32api"]),
        ("winsound", ["--include-module=winsound"]),
    ]
    
    available_count = 0
    total_count = len(modules_to_test)
    
    for module_name, module_flags in modules_to_test:
        try:
            __import__(module_name)
            optional_modules.extend(module_flags)
            print(f"[BUILD] ✓ Including {module_name}")
            available_count += 1
        except ImportError:
            print(f"[BUILD] ✗ Skipping {module_name} (not available)")
    
    print(f"[BUILD] Module availability: {available_count}/{total_count}")
    
    # Add optional modules to command
    cmd.extend(optional_modules)
    
    print(f"[BUILD] Executing Nuitka with {len(optional_modules)} module flags")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("[BUILD] Nuitka build completed successfully!")
        
        exe_path = dist_dir / "ScreenAlert.exe"
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)  # Convert to MB
            print(f"[SUCCESS] Generated executable: {exe_path}")
            print(f"[SUCCESS] File size: {file_size:.1f} MB")
            
            # Sign the executable if requested
            if sign:
                sign_executable_if_possible(exe_path)
            
            return str(exe_path)
        else:
            print("[ERROR] Executable not found after build!")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Nuitka build failed: {e}")
        print(f"[ERROR] STDOUT: {e.stdout}")
        print(f"[ERROR] STDERR: {e.stderr}")
        return None

if __name__ == "__main__":
    result = build_with_nuitka()
    if result:
        print(f"\n[SUCCESS] Build completed successfully!")
        print(f"[SUCCESS] Executable: {result}")
        sys.exit(0)
    else:
        print("\n[ERROR] Build failed.")
        sys.exit(1)
