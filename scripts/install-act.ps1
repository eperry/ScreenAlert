# Install GitHub Act - Local GitHub Actions Runner
# This script installs 'act' which allows running GitHub Actions locally

Write-Host "Installing GitHub 'act' - Local Actions Runner" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Check if Chocolatey is installed
if (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "Installing act via Chocolatey..." -ForegroundColor Yellow
    choco install act-cli
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing act via winget..." -ForegroundColor Yellow
    winget install nektos.act
} elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
    Write-Host "Installing act via Scoop..." -ForegroundColor Yellow
    scoop install act
} else {
    Write-Host "No package manager found. Please install manually:" -ForegroundColor Red
    Write-Host "1. Download from: https://github.com/nektos/act/releases" -ForegroundColor White
    Write-Host "2. Or install Chocolatey first: https://chocolatey.org/install" -ForegroundColor White
    Write-Host "3. Or install Scoop: https://scoop.sh/" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "After installation, you can run GitHub Actions locally with:" -ForegroundColor Green
Write-Host "  act                    # Run all workflows" -ForegroundColor White
Write-Host "  act -j build-windows   # Run specific job" -ForegroundColor White
Write-Host "  act push               # Simulate push event" -ForegroundColor White
Write-Host "  act workflow_dispatch # Simulate manual trigger" -ForegroundColor White
