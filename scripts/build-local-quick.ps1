#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick Local Build Script for ScreenAlert
    
.DESCRIPTION
    Simple script to build ScreenAlert locally without GitHub Actions complexity
    
.EXAMPLE
    .\build-local-quick.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "🚀 ScreenAlert - Quick Local Build" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Ensure we're in the root directory
Set-Location $PSScriptRoot\..

# Activate virtual environment
Write-Host "Activating Python environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Build
Write-Host "Building with Nuitka..." -ForegroundColor Green
Set-Location "build"
& "..\.venv\Scripts\python.exe" build_nuitka.py
Set-Location ".."

# Check result
if (Test-Path "dist-nuitka\ScreenAlert.exe") {
    $Size = (Get-Item "dist-nuitka\ScreenAlert.exe").Length / 1MB
    Write-Host ""
    Write-Host "✅ Build Successful!" -ForegroundColor Green
    Write-Host "   📁 Location: dist-nuitka\ScreenAlert.exe" -ForegroundColor White
    Write-Host "   📊 Size: $([math]::Round($Size, 1)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "Ready to test locally!" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "❌ Build Failed - executable not found" -ForegroundColor Red
    exit 1
}
