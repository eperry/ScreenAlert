# ScreenAlert - Act Setup and Build Script
# This is the ONLY build method - uses GitHub Actions locally via 'act'

Write-Host "ScreenAlert - Act Local Build Setup" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

# Check if act is already installed
$ActInstalled = Get-Command act -ErrorAction SilentlyContinue
if ($ActInstalled) {
    Write-Host "✅ Act is already installed: $($ActInstalled.Source)" -ForegroundColor Green
} else {
    Write-Host "Installing GitHub 'act' - Local Actions Runner..." -ForegroundColor Yellow
    
    # Check if Chocolatey is installed
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "Installing act via Chocolatey..." -ForegroundColor Yellow
        choco install act-cli -y
    } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing act via winget..." -ForegroundColor Yellow
        winget install nektos.act
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        Write-Host "Installing act via Scoop..." -ForegroundColor Yellow
        scoop install act
    } else {
        Write-Host "❌ No package manager found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install a package manager first:" -ForegroundColor White
        Write-Host "• Chocolatey: https://chocolatey.org/install" -ForegroundColor Gray
        Write-Host "• Scoop: https://scoop.sh/" -ForegroundColor Gray
        Write-Host "• Winget: Built into Windows 10/11" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Or install act manually from: https://github.com/nektos/act/releases" -ForegroundColor White
        exit 1
    }
}

Write-Host ""
Write-Host "🚀 ScreenAlert Build Commands:" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green
Write-Host ""
Write-Host "🔹 Test build (no release):" -ForegroundColor Yellow
Write-Host "   act push" -ForegroundColor White
Write-Host ""
Write-Host "🔹 Build with version (simulates manual trigger):" -ForegroundColor Yellow  
Write-Host "   act workflow_dispatch --input version=v1.5.2" -ForegroundColor White
Write-Host ""
Write-Host "🔹 Run specific job only:" -ForegroundColor Yellow
Write-Host "   act -j build-windows" -ForegroundColor White
Write-Host ""
Write-Host "🔹 List available workflows:" -ForegroundColor Yellow
Write-Host "   act -l" -ForegroundColor White
Write-Host ""
Write-Host "💡 Pro Tips:" -ForegroundColor Cyan
Write-Host "• First run will download Docker images (~2GB)" -ForegroundColor Gray
Write-Host "• Use 'act -P windows-latest=catthehacker/ubuntu:act-latest' for smaller images" -ForegroundColor Gray
Write-Host "• Add secrets with: act --secret-file .secrets" -ForegroundColor Gray
Write-Host ""

# Check if Docker is running (required for act)
try {
    $DockerRunning = docker version *>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Docker is running" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  Docker is not running - act requires Docker Desktop" -ForegroundColor Yellow
    Write-Host "   Please start Docker Desktop before running act commands" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🎯 Ready to build! Use the commands above." -ForegroundColor Green
