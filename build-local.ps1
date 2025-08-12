# Local build script for ScreenAlert
# Run this to test building the executable locally before pushing to GitHub

Write-Host "🔨 ScreenAlert Local Build Script" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists, create if not
if (!(Test-Path ".venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r screenalert_requirements.txt
pip install pyinstaller

# Clean previous builds
if (Test-Path "build") {
    Write-Host "🧹 Cleaning previous build..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force build
}
if (Test-Path "dist") {
    Write-Host "🧹 Cleaning previous dist..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force dist
}

# Build the executable
Write-Host "🔨 Building executable with PyInstaller..." -ForegroundColor Yellow
pyinstaller screenalert.spec --clean --noconfirm

# Check if build was successful
if (Test-Path "dist\ScreenAlert.exe") {
    $size = (Get-Item "dist\ScreenAlert.exe").Length / 1MB
    Write-Host "✅ Build successful!" -ForegroundColor Green
    Write-Host "📦 Executable: dist\ScreenAlert.exe" -ForegroundColor Green
    Write-Host "📏 Size: $([math]::Round($size, 2)) MB" -ForegroundColor Green
    
    # Test the executable
    Write-Host "🧪 Testing executable..." -ForegroundColor Yellow
    $testResult = Start-Process -FilePath "dist\ScreenAlert.exe" -PassThru -NoNewWindow
    Start-Sleep -Seconds 2
    
    if (!$testResult.HasExited) {
        Write-Host "✅ Executable started successfully!" -ForegroundColor Green
        Stop-Process -Id $testResult.Id -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "⚠️ Executable exited immediately (may be normal)" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "🎉 Build Complete!" -ForegroundColor Green
    Write-Host "You can find your executable at: dist\ScreenAlert.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Test the executable manually" -ForegroundColor White
    Write-Host "2. Create a new tag to trigger GitHub Actions build" -ForegroundColor White
    Write-Host "3. Push the tag to publish a release" -ForegroundColor White
    Write-Host ""
    Write-Host "Example commands for release:" -ForegroundColor Yellow
    Write-Host "git tag -a v1.3 -m 'Release v1.3 with Windows executable'" -ForegroundColor Cyan
    Write-Host "git push origin v1.3" -ForegroundColor Cyan
    
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    Write-Host "Check the output above for errors." -ForegroundColor Red
    exit 1
}
