# ScreenAlert MSI Installer Creator
# Simple one-click MSI installer creation

Write-Host "🚀 ScreenAlert MSI Installer Creator" -ForegroundColor Cyan
Write-Host "=" * 50

# Check if ScreenAlert.exe exists
$exePath = "dist-nuitka\ScreenAlert.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "❌ ScreenAlert.exe not found. Building it first..." -ForegroundColor Red
    
    Write-Host "Building ScreenAlert executable..." -ForegroundColor Yellow
    & C:/Users/Ed/OneDrive/Documents/Development/ScreenAlert/.venv/Scripts/python.exe build_nuitka.py
    
    if (-not (Test-Path $exePath)) {
        Write-Host "❌ Build failed or executable not created" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Found ScreenAlert.exe" -ForegroundColor Green

# Run the installer creator
Write-Host "Creating MSI installer..." -ForegroundColor Yellow
& C:/Users/Ed/OneDrive/Documents/Development/ScreenAlert/.venv/Scripts/python.exe create_installer.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n🎉 MSI Installer created successfully!" -ForegroundColor Green
    Write-Host "✅ Features:" -ForegroundColor Cyan
    Write-Host "  • User selectable installation directory" -ForegroundColor White
    Write-Host "  • Optional desktop shortcut" -ForegroundColor White
    Write-Host "  • Optional taskbar pinning" -ForegroundColor White
    Write-Host "  • Professional Windows integration" -ForegroundColor White
    
    # Show created MSI files
    Get-ChildItem -Filter "*.msi" | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 1)
        Write-Host "`n📦 Created: $($_.Name) ($size MB)" -ForegroundColor Green
        Write-Host "To install: Double-click $($_.Name)" -ForegroundColor White
    }
} else {
    Write-Host "❌ Installer creation failed" -ForegroundColor Red
}
