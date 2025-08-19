#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Direct Build Prevention Script - Redirects to ACT
    
.DESCRIPTION
    Prevents direct Windows builds and redirects users to use ACT (local GitHub Actions)
    for consistent, reproducible builds across all environments.
    
.EXAMPLE
    .\build-direct.ps1
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
Write-Host "Benefits of using ACT:" -ForegroundColor White
Write-Host "  - Consistent builds across Windows, Linux, and macOS" -ForegroundColor Gray
Write-Host "  - Containerized environment prevents dependency conflicts" -ForegroundColor Gray
Write-Host "  - Matches exactly what runs in GitHub Actions CI/CD" -ForegroundColor Gray
Write-Host "  - No local Python/dependency management required" -ForegroundColor Gray
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Red
Write-Host ""

# Exit with error code to prevent continuation
exit 1
