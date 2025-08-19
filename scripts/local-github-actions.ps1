#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Local GitHub Actions Build Script for ScreenAlert
    
.DESCRIPTION
    Runs the exact same build process as GitHub Actions but locally.
    Mimics the GitHub Actions workflow without needing to push to GitHub.
    
.PARAMETER Version
    Version tag to use for the build (e.g., "v1.5.2")
    
.PARAMETER SkipSigning
    Skip code signing step (useful for testing)
    
.PARAMETER SkipCache
    Skip using cached dependencies
    
.EXAMPLE
    .\local-github-actions.ps1 -Version "v1.5.2"
    .\local-github-actions.ps1 -Version "v1.5.2" -SkipSigning
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [switch]$SkipSigning,
    [switch]$SkipCache
)

# GitHub Actions Environment Simulation
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Step)
    Write-Host ""
    Write-Host ">>> $Step" -ForegroundColor Green
}

# Ensure we're in the right directory
Set-Location $PSScriptRoot\..

Write-Section "LOCAL GITHUB ACTIONS BUILD - ScreenAlert $Version"

# Step 1: Verify Python Environment
Write-Step "Set up Python Environment"
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "✅ Virtual environment found" -ForegroundColor Green
    $PythonExe = ".\.venv\Scripts\python.exe"
} else {
    Write-Host "❌ Virtual environment not found. Please create one first:" -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  pip install -r screenalert_requirements.txt" -ForegroundColor White
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Step 2: Install Dependencies (mimicking cache behavior)
Write-Step "Install Dependencies"
if (-not $SkipCache -and (Test-Path ".pip-cache-complete")) {
    Write-Host "✅ Using cached dependencies" -ForegroundColor Green
} else {
    Write-Host "Installing fresh dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install --upgrade pip --no-warn-script-location
    & $PythonExe -m pip install -r screenalert_requirements.txt --no-warn-script-location
    
    # Create cache marker
    if (-not $SkipCache) {
        "Dependencies installed $(Get-Date)" | Out-File ".pip-cache-complete"
    }
}

# Step 3: Build with Nuitka
Write-Step "Build with Nuitka (Robust Build Process)"
if ($SkipSigning) {
    $env:SKIP_SIGNING = "true"
}

Write-Host "Building ScreenAlert with robust Nuitka build..." -ForegroundColor Green
Set-Location "build"
try {
    & $PythonExe build_nuitka.py
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE"
    }
} finally {
    Set-Location ".."
}

# Step 4: Create Release Archive
Write-Step "Create Release Archive"
$ReleaseDir = "ScreenAlert-$Version"

# Clean up existing release directory
if (Test-Path $ReleaseDir) {
    Remove-Item $ReleaseDir -Recurse -Force
}

# Create release directory
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

# Copy files
if (Test-Path "dist-nuitka\ScreenAlert.exe") {
    Copy-Item "dist-nuitka\ScreenAlert.exe" "$ReleaseDir\"
    Copy-Item "README.md" "$ReleaseDir\"
    Copy-Item "screenalert_config.json" "$ReleaseDir\"
    
    Write-Host "✅ Release files copied" -ForegroundColor Green
} else {
    Write-Host "❌ Build executable not found!" -ForegroundColor Red
    exit 1
}

# Create ZIP archive
Write-Host "Creating ZIP archive..." -ForegroundColor Yellow
$ZipPath = "$ReleaseDir.zip"
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path $ReleaseDir -DestinationPath $ZipPath

# Step 5: Calculate File Hashes
Write-Step "Calculate File Hashes"
$HashFile = "local-build-hashes.txt"
Get-FileHash $ZipPath -Algorithm SHA256 | Format-Table -AutoSize | Out-File $HashFile
Get-FileHash "dist-nuitka\ScreenAlert.exe" -Algorithm SHA256 | Format-Table -AutoSize | Add-Content $HashFile

# Step 6: Display Results
Write-Section "BUILD COMPLETED SUCCESSFULLY!"
Write-Host ""
Write-Host "📁 Generated Files:" -ForegroundColor Green
Write-Host "  • $ZipPath" -ForegroundColor White
Write-Host "  • dist-nuitka\ScreenAlert.exe" -ForegroundColor White
Write-Host "  • $HashFile" -ForegroundColor White
Write-Host ""

$ExeSize = (Get-Item "dist-nuitka\ScreenAlert.exe").Length / 1MB
$ZipSize = (Get-Item $ZipPath).Length / 1MB

Write-Host "📊 File Sizes:" -ForegroundColor Green
Write-Host "  • Executable: $([math]::Round($ExeSize, 1)) MB" -ForegroundColor White
Write-Host "  • Archive: $([math]::Round($ZipSize, 1)) MB" -ForegroundColor White
Write-Host ""

Write-Host "✅ Local build complete - no GitHub push required!" -ForegroundColor Green
Write-Host "   Ready for local testing and deployment." -ForegroundColor Yellow

# Optional: Open folder with results
$OpenFolder = Read-Host "Open folder with build results? (y/N)"
if ($OpenFolder -eq 'y' -or $OpenFolder -eq 'Y') {
    Start-Process "explorer.exe" -ArgumentList "."
}
