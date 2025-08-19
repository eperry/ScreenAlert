#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build Check Prevention Script - Redirects to ACT
    
.DESCRIPTION
    Prevents direct Windows build checks and redirects users to use ACT (local GitHub Actions)
    for consistent, reproducible builds across all environments.
    
.EXAMPLE
    .\check-build.ps1
    This will show an error and direct you to use .\run-github-actions.ps1 instead
#>

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Red
Write-Host "  DIRECT WINDOWS BUILDS ARE DISABLED" -ForegroundColor Red  
Write-Host "==========================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "This project is configured to build ONLY through ACT (local GitHub Actions)" -ForegroundColor Yellow
Write-Host "to ensure consistent, reproducible builds across all environments." -ForegroundColor Yellow
Write-Host ""
Write-Host "To build ScreenAlert, please use:" -ForegroundColor Green
Write-Host "  .\run-github-actions.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will run the complete build process in a containerized environment" -ForegroundColor Yellow
Write-Host "with all proper dependencies and configurations." -ForegroundColor Yellow
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Red
Write-Host ""

# Exit with error code to prevent continuation
exit 1

Write-Host "ScreenAlert - Build Status Check" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if executable exists
if (Test-Path "dist-nuitka\ScreenAlert.exe") {
    $ExeInfo = Get-Item "dist-nuitka\ScreenAlert.exe"
    $Size = $ExeInfo.Length / 1MB
    $Created = $ExeInfo.CreationTime
    
    Write-Host "BUILD STATUS: COMPLETE" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable Details:" -ForegroundColor Yellow
    Write-Host "  Location: $($ExeInfo.FullName)" -ForegroundColor White
    Write-Host "  Size: $([math]::Round($Size, 1)) MB" -ForegroundColor White
    Write-Host "  Created: $Created" -ForegroundColor White
    Write-Host ""
    
    # Calculate hash for verification
    Write-Host "Calculating SHA256 hash..." -ForegroundColor Yellow
    $Hash = Get-FileHash "dist-nuitka\ScreenAlert.exe" -Algorithm SHA256
    Write-Host "  SHA256: $($Hash.Hash)" -ForegroundColor Gray
    
    Write-Host ""
    Write-Host "Ready to test!" -ForegroundColor Green
    
} else {
    Write-Host "BUILD STATUS: NOT COMPLETE" -ForegroundColor Red
    Write-Host ""
    
    # Check if dist-nuitka directory exists
    if (Test-Path "dist-nuitka") {
        Write-Host "Build directory exists but no executable found." -ForegroundColor Yellow
        Write-Host "Build may have failed or still be in progress." -ForegroundColor Yellow
    } else {
        Write-Host "No build directory found." -ForegroundColor Yellow
        Write-Host "Build has not been started." -ForegroundColor Yellow
    }
}

# Show recent files in project directory for context
Write-Host ""
Write-Host "Recent Activity:" -ForegroundColor Cyan
Get-ChildItem | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Format-Table Name, LastWriteTime -AutoSize
