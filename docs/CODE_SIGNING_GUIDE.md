# 🔐 ScreenAlert Code Signing Guide

## Overview
This guide explains how to set up **free code signing** for ScreenAlert to reduce antivirus false positives and provide better user trust.

## 🆓 Free Code Signing Options

### 1. Self-Signed Certificate (Recommended for Development)

#### Create Certificate Locally
```powershell
# Run the provided script
.\create_self_signed_cert.ps1
```

This creates:
- `ScreenAlert-Certificate.cer` - Public certificate for distribution
- `ScreenAlert-Certificate.pfx` - Private certificate for signing (password: `ScreenAlert2025!`)

#### Manual Certificate Creation
```powershell
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=ScreenAlert Developer" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(3)

# Export for use
Export-PfxCertificate -Cert $cert -FilePath "certificate.pfx" -Password (ConvertTo-SecureString -String "YourPassword" -Force -AsPlainText)
```

### 2. GitHub Actions Integration

#### Setup Secrets
1. Go to GitHub Repository → Settings → Secrets and variables → Actions
2. Add these secrets:
   - `SIGNING_CERTIFICATE`: Base64 encoded PFX file
   - `SIGNING_PASSWORD`: Certificate password

#### Encode Certificate for GitHub
```powershell
# Convert PFX to Base64 for GitHub Secrets
$certBytes = [System.IO.File]::ReadAllBytes("ScreenAlert-Certificate.pfx")
$certBase64 = [System.Convert]::ToBase64String($certBytes)
Write-Host $certBase64
```

## 🔧 How It Works

### Automatic Signing
The build system automatically signs executables when:
1. **Local Development**: Certificate file exists (`ScreenAlert-Certificate.pfx`)
2. **GitHub Actions**: Secrets are configured (`SIGNING_CERTIFICATE` + `SIGNING_PASSWORD`)
3. **Windows SDK**: `signtool.exe` is available

### Build Integration
```python
# build_nuitka.py automatically calls:
sign_result = sign_executable_if_possible(exe_path)
```

### Manual Signing
```python
# Sign manually
python sign_executable.py ScreenAlert.exe ScreenAlert-Certificate.pfx ScreenAlert2025!
```

## 🛡️ Trust Levels

### Self-Signed Certificate
- **Trust Level**: ⭐⭐ (Medium-Low)
- **User Experience**: Windows shows "Unknown Publisher" warning
- **Antivirus**: Some improvement over unsigned
- **Cost**: Free
- **Installation**: Users can install certificate for full trust

### Extended Validation (EV) Certificate
- **Trust Level**: ⭐⭐⭐⭐⭐ (Highest)
- **User Experience**: No warnings, publisher verified
- **Antivirus**: Maximum trust
- **Cost**: $200-500/year
- **Requirements**: Legal business verification

## 💡 Recommended Approach

### For Open Source Distribution
1. **Use self-signed certificate** for development and releases
2. **Provide certificate file** for users to install if desired
3. **Document the process** for user trust
4. **Consider crowd-funding** an EV certificate if project grows

### Certificate Installation for Users
```powershell
# Users can install the certificate for full trust
Import-Certificate -FilePath "ScreenAlert-Certificate.cer" -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher"
```

## 🔍 Verification

### Check if Executable is Signed
```powershell
Get-AuthenticodeSignature "ScreenAlert.exe"
```

### Expected Output (Self-Signed)
```
Status       : Valid
StatusMessage: Signature verified.
SignerCertificate: [Subject]
                     CN=ScreenAlert Developer
```

## 🚀 Implementation Status

### ✅ Implemented
- [x] Self-signed certificate creation script
- [x] Automatic build integration
- [x] GitHub Actions support
- [x] Manual signing utility
- [x] Certificate detection and fallback

### 🔄 Optional Upgrades
- [ ] EV certificate integration (requires business)
- [ ] Certificate renewal automation
- [ ] Timestamping service redundancy
- [ ] Cross-platform signing support

## 📋 Troubleshooting

### Signtool Not Found
```bash
# Install Windows SDK
# Download from: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
```

### Certificate Expired
```powershell
# Check expiration
Get-PfxCertificate "ScreenAlert-Certificate.pfx"

# Renew by running create_self_signed_cert.ps1 again
```

### Timestamp Server Issues
The build uses `http://timestamp.digicert.com` for timestamping. If this fails:
- Executable still gets signed (without timestamp)
- Consider adding backup timestamp servers

## 🎯 Next Steps

1. **Run**: `.\create_self_signed_cert.ps1` to create certificate
2. **Build**: Build process now automatically signs
3. **Test**: Verify signature with `Get-AuthenticodeSignature`
4. **Distribute**: Include certificate file for user installation
5. **Upgrade**: Consider EV certificate for production use

This provides immediate signing benefits while keeping costs at zero! 🎉
