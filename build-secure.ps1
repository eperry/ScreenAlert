# Build ScreenAlert with optimized settings for antivirus compatibility
param(
    [string]$Version = "1.3.3"
)

Write-Host "🔧 Building ScreenAlert v$Version with AV-optimized settings..." -ForegroundColor Cyan

# Clean previous builds
Write-Host "🧹 Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Install dependencies if needed
Write-Host "📦 Checking dependencies..." -ForegroundColor Yellow
pip install -r screenalert_requirements.txt

# Create version info file
Write-Host "📝 Creating version information..." -ForegroundColor Yellow
$versionParts = $Version.Split('.')
while ($versionParts.Length -lt 4) { $versionParts += "0" }

# Build with PyInstaller
Write-Host "🏗️ Building executable with PyInstaller..." -ForegroundColor Green
python -m PyInstaller screenalert.spec --clean --noconfirm --log-level WARN

# Verify build
if (Test-Path "dist\ScreenAlert.exe") {
    $size = (Get-Item "dist\ScreenAlert.exe").Length / 1MB
    Write-Host "✅ Build successful!" -ForegroundColor Green
    Write-Host "📊 Executable size: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
    
    # Calculate file hash for verification
    $hash = Get-FileHash "dist\ScreenAlert.exe" -Algorithm SHA256
    Write-Host "🔐 SHA256 Hash: $($hash.Hash)" -ForegroundColor Magenta
    
    # Save hash to file
    $hash.Hash | Out-File "dist\ScreenAlert.exe.sha256" -Encoding ASCII
    
    Write-Host ""
    Write-Host "🛡️ Security Notes:" -ForegroundColor Yellow
    Write-Host "- Executable is unsigned (may trigger AV warnings)" -ForegroundColor White
    Write-Host "- Add to antivirus exclusions if needed" -ForegroundColor White
    Write-Host "- Verify SHA256 hash: $($hash.Hash)" -ForegroundColor White
    Write-Host "- See SECURITY.md for more information" -ForegroundColor White
    
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Build complete! Executable available at: dist\ScreenAlert.exe" -ForegroundColor Green
