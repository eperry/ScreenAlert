# ScreenAlert Portable Distribution Creator
# This creates a portable version that doesn't need PyInstaller

param(
    [string]$Version = "1.3.5"
)

Write-Host "📦 Creating ScreenAlert Portable Distribution v$Version" -ForegroundColor Cyan
Write-Host "=" * 60

# Create portable directory structure
$portableDir = "ScreenAlert-Portable-v$Version"
$portablePath = "dist\$portableDir"

Write-Host "🗂️  Creating directory structure..." -ForegroundColor Yellow
if (Test-Path $portablePath) { Remove-Item -Recurse -Force $portablePath }
New-Item -ItemType Directory -Force -Path $portablePath

# Copy essential files
Write-Host "📁 Copying application files..." -ForegroundColor Yellow
Copy-Item "screenalert.py" -Destination $portablePath
Copy-Item "screenalert_requirements.txt" -Destination $portablePath
Copy-Item "default_config.json" -Destination "$portablePath\screenalert_config.json"
Copy-Item "README.md" -Destination $portablePath -ErrorAction SilentlyContinue
Copy-Item "SCREENALERT_README.md" -Destination $portablePath -ErrorAction SilentlyContinue
Copy-Item "SECURITY.md" -Destination $portablePath -ErrorAction SilentlyContinue
Copy-Item "ANTIVIRUS_README.md" -Destination $portablePath -ErrorAction SilentlyContinue

# Create launcher script
Write-Host "🚀 Creating launcher script..." -ForegroundColor Yellow
@"
@echo off
title ScreenAlert - Portable Version
echo ================================================================
echo                     ScreenAlert v$Version
echo                      Portable Edition
echo ================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo ScreenAlert requires Python 3.7 or later to run.
    echo Please install Python from: https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking Python dependencies...
python -c "import tkinter, cv2, numpy, pyautogui, pyttsx3, PIL, skimage, imagehash" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    python -m pip install -r screenalert_requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo Please check your internet connection and try again
        pause
        exit /b 1
    )
)

echo Starting ScreenAlert...
echo.
python screenalert.py

if errorlevel 1 (
    echo.
    echo ScreenAlert encountered an error.
    echo Check the console output above for details.
    pause
)
"@ | Out-File -Encoding ASCII -FilePath "$portablePath\Launch-ScreenAlert.bat"

# Create installation instructions
Write-Host "📋 Creating documentation..." -ForegroundColor Yellow
@"
# ScreenAlert v$Version - Portable Edition

## 🚀 Quick Start

1. **Double-click** `Launch-ScreenAlert.bat` to start the application
2. On first run, Python dependencies will be automatically installed
3. Configure your monitoring settings in the ScreenAlert interface

## 📋 Requirements

- **Python 3.7 or later** must be installed on your system
- Internet connection (for initial dependency installation only)
- Windows 10 or later

## 🛡️ Antivirus Safety

This portable version runs directly from Python source code, eliminating
false positive antivirus detections that can occur with compiled executables.

## 📁 Files Included

- `screenalert.py` - Main application
- `Launch-ScreenAlert.bat` - Easy launcher
- `screenalert_requirements.txt` - Python dependencies
- `screenalert_config.json` - Default configuration
- Documentation files

## 🔧 Manual Installation (Alternative)

If the launcher doesn't work, install dependencies manually:

```cmd
python -m pip install -r screenalert_requirements.txt
python screenalert.py
```

## 🆘 Troubleshooting

### Python Not Found
- Install Python from https://python.org
- Make sure "Add Python to PATH" is checked during installation
- Restart your computer after Python installation

### Dependencies Fail to Install
- Check internet connection
- Try running as administrator
- Update pip: `python -m pip install --upgrade pip`

### Application Won't Start
- Check that all files are in the same folder
- Verify Python installation: `python --version`
- Check the console output for specific error messages

## 📞 Support

- GitHub Issues: https://github.com/eperry/ScreenAlert/issues
- Documentation: See included README files
- Security Info: See ANTIVIRUS_README.md

## 📊 Version Information

- **Version**: $Version
- **Build Date**: $(Get-Date -Format 'yyyy-MM-dd')
- **Distribution**: Portable (Source-based)
- **Platform**: Windows
- **Python**: 3.7+ Required

---

**Note**: This portable version requires Python to be installed on your system
but avoids antivirus false positives by running from source code instead of
compiled executables.
"@ | Out-File -Encoding UTF8 -FilePath "$portablePath\README-PORTABLE.md"

# Create troubleshooting guide
@"
# 🛡️ Antivirus False Positive Solution

## The Problem

Compiled Python executables (created with PyInstaller) often trigger false
positive detections in antivirus software, particularly Windows Defender.

## The Solution: Portable Source Version

This portable version solves the problem by:

✅ **Running from source code** instead of compiled executable
✅ **No PyInstaller packaging** that triggers heuristic detection
✅ **Transparent operation** - you can see exactly what code is running
✅ **Easy verification** - all source code is readable and auditable

## Why This Works

1. **No Executable Packing**: Antivirus software flags packed executables as suspicious
2. **Direct Python Execution**: Python interpreter runs your code directly
3. **Source Transparency**: You can review every line of code
4. **Standard Dependencies**: Uses only well-known Python packages

## Requirements

- Python 3.7+ installed on your system
- Internet connection for initial dependency download

## First Time Setup

1. Download and extract this portable package
2. Double-click `Launch-ScreenAlert.bat`
3. Dependencies will be installed automatically
4. ScreenAlert will start normally

## Advantages

- ✅ **No antivirus warnings**
- ✅ **Smaller download size**
- ✅ **Easy to verify safety**
- ✅ **Always up-to-date** (uses latest Python packages)
- ✅ **Cross-platform compatible**

## If You Still Prefer an Executable

1. Use the onedir distribution (folder with ScreenAlert.exe)
2. Add the executable to your antivirus exclusions
3. Report false positive to your antivirus vendor
4. Verify SHA256 hash against published values

Choose the method that works best for your environment!
"@ | Out-File -Encoding UTF8 -FilePath "$portablePath\ANTIVIRUS-SOLUTION.md"

# Create ZIP archive
Write-Host "🗜️  Creating ZIP archive..." -ForegroundColor Yellow
$zipPath = "$portablePath.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path $portablePath -DestinationPath $zipPath

# Calculate size
$folderSize = (Get-ChildItem -Recurse $portablePath | Measure-Object -Property Length -Sum).Sum / 1MB
$zipSize = (Get-Item $zipPath).Length / 1MB

Write-Host ""
Write-Host "✅ Portable distribution created successfully!" -ForegroundColor Green
Write-Host "📦 Folder: $portablePath ($([math]::Round($folderSize, 2)) MB)" -ForegroundColor Cyan
Write-Host "🗜️  Archive: $zipPath ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Cyan
Write-Host ""
Write-Host "🛡️  Benefits of this distribution:" -ForegroundColor Yellow
Write-Host "   • No antivirus false positives"
Write-Host "   • Runs from Python source code"
Write-Host "   • Smaller download size"
Write-Host "   • Easy to verify and audit"
Write-Host "   • Always uses latest Python packages"
Write-Host ""
Write-Host "📁 Contents:" -ForegroundColor Yellow
Get-ChildItem $portablePath | ForEach-Object { Write-Host "   • $($_.Name)" }
