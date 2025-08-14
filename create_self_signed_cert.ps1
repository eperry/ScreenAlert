# Create Self-Signed Code Signing Certificate for ScreenAlert
# This creates a certificate that can be used for development/testing

Write-Host "Creating self-signed code signing certificate for ScreenAlert..." -ForegroundColor Green

# Certificate details
$certName = "ScreenAlert Development Certificate"
$publisher = "Ed Perry - ScreenAlert Developer"
$validYears = 3

try {
    # Create the certificate
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=$publisher" `
        -FriendlyName $certName `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears($validYears) `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -Provider "Microsoft Enhanced RSA and AES Cryptographic Provider" `
        -KeyExportPolicy Exportable `
        -KeyUsage DigitalSignature `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")

    Write-Host "✅ Certificate created successfully!" -ForegroundColor Green
    Write-Host "Certificate Thumbprint: $($cert.Thumbprint)" -ForegroundColor Yellow
    Write-Host "Certificate Subject: $($cert.Subject)" -ForegroundColor Yellow
    
    # Export certificate for distribution
    $certPath = ".\ScreenAlert-Certificate.cer"
    Export-Certificate -Cert $cert -FilePath $certPath -Type CERT
    Write-Host "✅ Certificate exported to: $certPath" -ForegroundColor Green
    
    # Also export as PFX for GitHub Actions (with password)
    $pfxPassword = ConvertTo-SecureString -String "ScreenAlert2025!" -Force -AsPlainText
    $pfxPath = ".\ScreenAlert-Certificate.pfx"
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPassword
    Write-Host "✅ PFX certificate exported to: $pfxPath" -ForegroundColor Green
    Write-Host "PFX Password: ScreenAlert2025!" -ForegroundColor Red
    
    Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Install the certificate on target machines for better trust" -ForegroundColor White
    Write-Host "2. Use the certificate to sign your executable" -ForegroundColor White
    Write-Host "3. For GitHub Actions, upload the PFX as a secret" -ForegroundColor White
    
    Write-Host "`n🔧 To sign your executable:" -ForegroundColor Cyan
    Write-Host "signtool sign /f `"$pfxPath`" /p `"ScreenAlert2025!`" /t http://timestamp.digicert.com `"ScreenAlert.exe`"" -ForegroundColor White
    
    return $cert.Thumbprint
}
catch {
    Write-Host "❌ Error creating certificate: $($_.Exception.Message)" -ForegroundColor Red
    return $null
}
