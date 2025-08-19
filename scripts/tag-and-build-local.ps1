#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Local Version Tag and Build Script
    
.DESCRIPTION
    Build, tag, and create release locally without GitHub Actions
    
.PARAMETER Version
    Version to tag (e.g., "1.5.2" - will be prefixed with "v")
    
.PARAMETER PushTag
    Push the tag to GitHub after creating it
    
.EXAMPLE
    .\tag-and-build-local.ps1 -Version "1.5.2"
    .\tag-and-build-local.ps1 -Version "1.5.2" -PushTag
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [switch]$PushTag
)

$ErrorActionPreference = "Stop"
$FullVersion = "v$Version"

Write-Host "🏷️  ScreenAlert - Local Tag and Build" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Version: $FullVersion" -ForegroundColor Yellow
Write-Host ""

# Ensure we're in the root directory
Set-Location $PSScriptRoot\..

# Check if working directory is clean
$GitStatus = git status --porcelain
if ($GitStatus) {
    Write-Host "⚠️  Warning: Working directory has uncommitted changes:" -ForegroundColor Yellow
    git status --short
    $Continue = Read-Host "Continue anyway? (y/N)"
    if ($Continue -ne 'y' -and $Continue -ne 'Y') {
        Write-Host "Aborted." -ForegroundColor Red
        exit 1
    }
}

# Update version in screenalert.py if needed
Write-Host "📝 Checking version in code..." -ForegroundColor Green
$Content = Get-Content "screenalert.py" -Raw
if ($Content -match 'APP_VERSION = "([^"]+)"') {
    $CurrentVersion = $Matches[1]
    if ($CurrentVersion -ne $Version) {
        Write-Host "Updating APP_VERSION from $CurrentVersion to $Version" -ForegroundColor Yellow
        $Content = $Content -replace 'APP_VERSION = "[^"]+"', "APP_VERSION = `"$Version`""
        Set-Content "screenalert.py" -Value $Content
        git add screenalert.py
        git commit -m "🔖 Update version to $Version"
    } else {
        Write-Host "✅ Version already up to date: $Version" -ForegroundColor Green
    }
}

# Build the application
Write-Host ""
Write-Host "🚀 Building ScreenAlert $FullVersion..." -ForegroundColor Green
& ".\scripts\local-github-actions.ps1" -Version $FullVersion

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}

# Create and push tag
Write-Host ""
Write-Host "🏷️  Creating tag $FullVersion..." -ForegroundColor Green
git tag -a $FullVersion -m "ScreenAlert $FullVersion - Local Build

✨ Features and improvements in this release
🛡️ Built with Nuitka for zero antivirus false positives
📦 Professional directory structure
🔧 Enhanced build system

Built locally without GitHub Actions dependency."

Write-Host "✅ Tag created: $FullVersion" -ForegroundColor Green

if ($PushTag) {
    Write-Host ""
    Write-Host "⬆️  Pushing tag to GitHub..." -ForegroundColor Green
    git push origin $FullVersion
    Write-Host "✅ Tag pushed to GitHub" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 You can now create a release manually at:" -ForegroundColor Yellow
    Write-Host "   https://github.com/eperry/ScreenAlert/releases/new?tag=$FullVersion" -ForegroundColor White
}

Write-Host ""
Write-Host "✅ Local tag and build completed!" -ForegroundColor Green
Write-Host "   📁 Files ready in: ScreenAlert-$FullVersion.zip" -ForegroundColor White
Write-Host "   🏷️  Tag: $FullVersion" -ForegroundColor White
if (-not $PushTag) {
    Write-Host "   💡 Use -PushTag to push tag to GitHub" -ForegroundColor Gray
}
