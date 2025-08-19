# ScreenAlert Build Guide

ScreenAlert uses **ACT (local GitHub Actions)** for all builds to ensure consistency, reproducibility, and cross-platform compatibility.

## 🚀 Building ScreenAlert

### Quick Start
```powershell
.\run-github-actions.ps1
```

This command runs the complete build process in a containerized environment using the same workflow that runs in GitHub Actions CI/CD.

## 🏗️ Build System Architecture

### ACT-Only Building
**Direct Windows builds are disabled.** All builds must go through ACT for these reasons:

✅ **Consistency**: Same build environment across Windows, Linux, and macOS  
✅ **Reproducibility**: Containerized builds eliminate "works on my machine" issues  
✅ **Dependency Management**: No local Python/library conflicts  
✅ **CI/CD Parity**: Matches exactly what runs in GitHub Actions  

### Build Process Overview
1. **ACT** launches a Linux container (Ubuntu-based)
2. **Python 3.11.13** is installed with cross-platform dependencies
3. **Nuitka** compiles ScreenAlert to a standalone executable
4. **Artifacts** are generated and cached for future builds

## 📋 Requirements

### System Requirements
- **Docker Desktop** (for ACT containerization)
- **PowerShell 5.1+** (Windows PowerShell or PowerShell Core)
- **ACT** (nektos/act) - automatically installed by run script

### No Manual Dependencies
- ❌ No local Python installation required
- ❌ No pip package management needed  
- ❌ No virtual environment setup required
- ❌ No Nuitka installation needed

Everything is handled automatically in the containerized build environment.

## 🛠️ Build Commands

### Primary Build Command
```powershell
.\run-github-actions.ps1
```

### Build Options
```powershell
# Job-only execution (skips setup checks)
.\run-github-actions.ps1 -JobOnly

# Verbose output for debugging
.\run-github-actions.ps1 -Verbose
```

## 📁 Build Output

### Generated Files
```
dist-nuitka/
  └── ScreenAlert.exe          # Standalone executable
  
ScreenAlert-main.zip           # Distribution package
hashes.txt                     # File integrity hashes
```

### Build Artifacts
- **Executable**: `dist-nuitka/ScreenAlert.exe`
- **Package**: `ScreenAlert-main.zip` 
- **Hashes**: File integrity verification
- **Logs**: Complete build output and debug info

## 🔧 Troubleshooting

### Common Issues

**"Docker not running"**
- Start Docker Desktop
- Ensure Docker daemon is running

**"ACT not found"**
- The script will automatically install ACT
- Manual install: `winget install nektos.act`

**"Build timeout"**
- Large dependencies may take time on first run
- Subsequent builds use cached layers

**"Container pull failed"**  
- Check internet connection
- Verify Docker can pull images

### Debug Mode
```powershell
.\run-github-actions.ps1 -Verbose
```

This provides detailed output for troubleshooting build issues.

## 🚫 Disabled Commands

These scripts now redirect to ACT builds:

- `.\build-direct.ps1` → Use `.\run-github-actions.ps1`
- `.\check-build.ps1` → Use `.\run-github-actions.ps1`
- `python build/build_nuitka.py` → Use ACT workflow

## 🎯 Why ACT-Only?

### Traditional Problems
- **Environment Drift**: Different Python versions, missing libraries
- **Platform Issues**: Windows-specific bugs that don't appear on Linux
- **Dependency Hell**: Conflicting package versions
- **Inconsistent Results**: Builds work locally but fail in CI

### ACT Solutions
- **Hermetic Builds**: Completely isolated, repeatable environment
- **Cross-Platform**: Same container on Windows, macOS, and Linux  
- **Version Locked**: Exact Python and dependency versions
- **CI/CD Identical**: Same process as production deployments

## 📖 Advanced Usage

### Custom Workflows
The build uses `.github/workflows/build-release.yml` which can be modified for:
- Different Python versions
- Additional build targets
- Custom optimization flags
- Extended testing phases

### Cache Management
ACT automatically caches:
- Python packages (pip cache)
- Compiled modules
- Nuitka artifacts  
- Container layers

Cache is stored in Docker volumes for fast subsequent builds.

---

**Summary**: Use `.\run-github-actions.ps1` for all builds. Direct Windows compilation is disabled to ensure consistency and reliability.
