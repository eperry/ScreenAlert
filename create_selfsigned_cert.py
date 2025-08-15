#!/usr/bin/env python3
"""
Self-Signed Certificate Generator for ScreenAlert
Creates a self-signed certificate that can be used to sign the executable
This reduces (but doesn't eliminate) Windows Defender warnings
"""

import os
import sys
import subprocess
from pathlib import Path
import tempfile

def create_self_signed_certificate(cert_name="ScreenAlert", output_pfx="ScreenAlert-SelfSigned.pfx", password="ScreenAlert2025!"):
    """Create a self-signed certificate for code signing"""
    
    print(f"[CERT] Creating self-signed certificate: {cert_name}")
    
    try:
        # Create a temporary .inf file for certificate creation
        inf_content = f"""
[Version]
Signature="$Windows NT$"

[NewRequest]
Subject="CN={cert_name},O=ScreenAlert,C=US"
KeyLength=2048
KeyAlgorithm=RSA
ProviderName="Microsoft Enhanced RSA and AES Cryptographic Provider"
KeyUsage=0xa0
MachineKeySet=false
SMIME=false
PrivateKeyArchive=false
UserProtected=false
UseExistingKeySet=false
RequestType=PKCS10
KeySpec=1

[EnhancedKeyUsageExtension]
OID=1.3.6.1.5.5.7.3.3 ; Code Signing
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.inf', delete=False) as f:
            f.write(inf_content)
            inf_file = f.name
        
        try:
            # Step 1: Create certificate request
            csr_file = inf_file.replace('.inf', '.csr')
            cmd1 = [
                'certreq', '-new', inf_file, csr_file
            ]
            
            print("[CERT] Creating certificate request...")
            result1 = subprocess.run(cmd1, capture_output=True, text=True, shell=True)
            
            if result1.returncode != 0:
                print(f"[ERROR] Failed to create certificate request: {result1.stderr}")
                return False
            
            # Step 2: Create self-signed certificate
            cer_file = inf_file.replace('.inf', '.cer')
            cmd2 = [
                'certreq', '-accept', csr_file
            ]
            
            print("[CERT] Creating self-signed certificate...")
            result2 = subprocess.run(cmd2, capture_output=True, text=True, shell=True)
            
            # Alternative approach using PowerShell for more modern systems
            ps_script = f"""
$cert = New-SelfSignedCertificate -Subject "CN={cert_name}" -Type CodeSigning -KeyAlgorithm RSA -KeyLength 2048 -Provider "Microsoft Enhanced RSA and AES Cryptographic Provider" -KeyExportPolicy Exportable -KeyUsage DigitalSignature -NotAfter (Get-Date).AddYears(3) -CertStoreLocation "cert:\\CurrentUser\\My"
$pwd = ConvertTo-SecureString -String "{password}" -Force -AsPlainText
Export-PfxCertificate -cert $cert -FilePath "{output_pfx}" -Password $pwd
Write-Output "Certificate thumbprint: $($cert.Thumbprint)"
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
                f.write(ps_script)
                ps_file = f.name
            
            print("[CERT] Creating certificate with PowerShell...")
            result3 = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file
            ], capture_output=True, text=True)
            
            if result3.returncode == 0:
                print(f"[SUCCESS] Self-signed certificate created: {output_pfx}")
                print(f"[INFO] Certificate thumbprint in output: {result3.stdout.strip()}")
                return True
            else:
                print(f"[ERROR] PowerShell certificate creation failed: {result3.stderr}")
                return False
                
        finally:
            # Clean up temporary files
            for temp_file in [inf_file, csr_file, cer_file, ps_file]:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
                    
    except Exception as e:
        print(f"[ERROR] Certificate creation failed: {e}")
        return False

def sign_with_self_signed(exe_path, pfx_path="ScreenAlert-SelfSigned.pfx", password="ScreenAlert2025!"):
    """Sign executable with self-signed certificate"""
    
    # First, ensure we have a certificate
    if not os.path.exists(pfx_path):
        print(f"[CERT] Certificate not found, creating: {pfx_path}")
        if not create_self_signed_certificate(output_pfx=pfx_path, password=password):
            return False
    
    # Import and use the existing signing function
    from sign_executable import sign_executable
    return sign_executable(exe_path, cert_path=pfx_path, password=password)

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_selfsigned_cert.py create [cert_name] [output.pfx] [password]")
        print("  python create_selfsigned_cert.py sign <exe_path> [pfx_path] [password]")
        return
    
    command = sys.argv[1]
    
    if command == "create":
        cert_name = sys.argv[2] if len(sys.argv) > 2 else "ScreenAlert"
        output_pfx = sys.argv[3] if len(sys.argv) > 3 else "ScreenAlert-SelfSigned.pfx"
        password = sys.argv[4] if len(sys.argv) > 4 else "ScreenAlert2025!"
        
        if create_self_signed_certificate(cert_name, output_pfx, password):
            print(f"[SUCCESS] Certificate created: {output_pfx}")
        else:
            print("[ERROR] Failed to create certificate")
            
    elif command == "sign":
        exe_path = sys.argv[2]
        pfx_path = sys.argv[3] if len(sys.argv) > 3 else "ScreenAlert-SelfSigned.pfx"
        password = sys.argv[4] if len(sys.argv) > 4 else "ScreenAlert2025!"
        
        if sign_with_self_signed(exe_path, pfx_path, password):
            print(f"[SUCCESS] Executable signed: {exe_path}")
        else:
            print("[ERROR] Failed to sign executable")
    else:
        print(f"[ERROR] Unknown command: {command}")

if __name__ == "__main__":
    main()
