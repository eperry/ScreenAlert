#!/usr/bin/env python3
"""
Code Signing Integration for ScreenAlert
Integrates code signing into the Nuitka build process
"""

import os
import sys
import subprocess
from pathlib import Path

def find_signtool():
    """Find signtool.exe in Windows SDK"""
    possible_paths = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files (x86)\Microsoft SDKs\Windows\*\bin\signtool.exe",
    ]
    
    import glob
    for pattern in possible_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[-1]  # Return the latest version
    
    return None

def sign_executable(exe_path, cert_path=None, cert_thumbprint=None, password=None):
    """Sign the executable with the certificate"""
    
    signtool = find_signtool()
    if not signtool:
        print("❌ signtool.exe not found. Please install Windows SDK.")
        return False
    
    print(f"🔐 Signing {exe_path}...")
    
    # Build signtool command
    if cert_path and password:
        # Using PFX file
        cmd = [
            signtool, "sign",
            "/f", cert_path,
            "/p", password,
            "/t", "http://timestamp.digicert.com",  # Timestamp server
            "/v",  # Verbose
            exe_path
        ]
    elif cert_thumbprint:
        # Using certificate from store
        cmd = [
            signtool, "sign",
            "/sha1", cert_thumbprint,
            "/t", "http://timestamp.digicert.com",
            "/v",
            exe_path
        ]
    else:
        print("❌ No certificate specified")
        return False
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Executable signed successfully!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Signing failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def main():
    """Main signing function"""
    if len(sys.argv) < 2:
        print("Usage: python sign_executable.py <exe_path> [cert_path] [password]")
        return
    
    exe_path = sys.argv[1]
    cert_path = sys.argv[2] if len(sys.argv) > 2 else None
    password = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Check if exe exists
    if not os.path.exists(exe_path):
        print(f"❌ Executable not found: {exe_path}")
        return
    
    # Try to find certificate automatically
    if not cert_path:
        pfx_path = Path("ScreenAlert-Certificate.pfx")
        if pfx_path.exists():
            cert_path = str(pfx_path)
            password = password or "ScreenAlert2025!"
    
    if cert_path:
        success = sign_executable(exe_path, cert_path=cert_path, password=password)
    else:
        # Try to use certificate from store (look for our self-signed cert)
        print("🔍 Looking for certificate in store...")
        # This is a simplified approach - in practice you'd get the thumbprint
        success = False
        print("ℹ️  Please provide certificate path or install certificate to store")
    
    if success:
        print(f"🎉 {exe_path} has been signed!")
    else:
        print(f"❌ Failed to sign {exe_path}")

if __name__ == "__main__":
    main()
