# Self-Hosted GitHub Actions Runner Setup

## Overview
A self-hosted runner gives you **perfect 1:1 parity** with GitHub Actions because it runs the exact same workflow, just on your local Windows machine instead of GitHub's servers.

## Benefits
✅ **True Windows environment** - Runs natively on your Windows machine
✅ **Exact same workflow** - Uses your existing `.github/workflows/build-release.yml`
✅ **Perfect parity** - Identical to GitHub Actions (because it IS GitHub Actions)
✅ **Windows-specific packages** - `pywin32`, GUI libraries, etc. work perfectly
✅ **Local development** - Test before pushing to GitHub
✅ **Fast feedback** - No waiting for GitHub's queue

## Setup Steps

### 1. Create Runner Token
1. Go to your GitHub repository: https://github.com/eperry/ScreenAlert
2. Navigate to **Settings** → **Actions** → **Runners**
3. Click **New self-hosted runner**
4. Select **Windows** and **x64**
5. Copy the download and configuration commands

### 2. Install Runner
```powershell
# Create a folder for the runner
mkdir actions-runner; cd actions-runner

# Download the latest runner package
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-win-x64-2.319.1.zip -OutFile actions-runner-win-x64-2.319.1.zip

# Extract the installer
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD\actions-runner-win-x64-2.319.1.zip", "$PWD")

# Configure the runner (use your generated token)
.\config.cmd --url https://github.com/eperry/ScreenAlert --token YOUR_TOKEN_HERE
```

### 3. Run Your Workflows
```powershell
# Start the runner
.\run.cmd

# Or install as Windows service for always-on
.\svc.cmd install
.\svc.cmd start
```

### 4. Trigger Builds
- Push to your repository
- Or manually trigger via GitHub web interface
- Or use GitHub CLI: `gh workflow run build-release.yml`

## Local Testing
Your workflows will run on your local machine but be triggered from GitHub, giving you:
- Local build artifacts
- Local caching 
- Windows-native execution
- Perfect debugging capabilities
