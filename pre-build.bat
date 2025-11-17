@echo off
REM Pre-build script to update version and prepare for build
REM Run this before creating a release or building the application

echo ==========================================
echo ScreenAlert Pre-Build Script
echo ==========================================
echo.

REM Update fallback version from git tag
echo [1/2] Updating fallback version...
python update-version.py
if errorlevel 1 (
    echo Warning: Version update had issues, continuing anyway...
)
echo.

REM Verify versions match
echo [2/2] Verifying version consistency...
python check-version.py
if errorlevel 1 (
    echo Warning: Version mismatch detected
)
echo.

echo ==========================================
echo Pre-build complete
echo ==========================================
pause
