#!/usr/bin/env pwsh

Write-Host "Running GitHub Actions locally with ACT..." -ForegroundColor Green

# Find ACT executable
$ActPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\nektos.act_Microsoft.Winget.Source_8wekyb3d8bbwe\act.exe"

if (-not (Test-Path $ActPath)) {
    Write-Host "ACT not found at expected location. Please ensure ACT is installed via winget." -ForegroundColor Red
    exit 1
}

# Run the build workflow with container
& $ActPath -j build --verbose
