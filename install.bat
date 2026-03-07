@echo off
cd /d "%~dp0"
echo ScreenAlert Installer
echo =====================

rem --- Find Python ---
set "PYTHON="
python --version >nul 2>&1
if %errorlevel% equ 0 set "PYTHON=python"

if not defined PYTHON (
    py --version >nul 2>&1
    if %errorlevel% equ 0 set "PYTHON=py"
)

if not defined PYTHON (
    echo ERROR: Python not found. Please install Python 3.9+ and ensure it is on your PATH.
    pause
    exit /b 1
)

echo Found Python:
%PYTHON% --version

rem --- Check Python version (3.9+) ---
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3.9 or higher is required.
    pause
    exit /b 1
)

rem --- Create virtual environment ---
if exist ".venv\Scripts\python.exe" (
    echo Virtual environment already exists, skipping creation.
) else (
    echo Creating virtual environment...
    %PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
)

rem --- Upgrade pip ---
echo Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo WARNING: pip upgrade failed, continuing with existing pip.
)

rem --- Install dependencies ---
echo Installing dependencies from screenalert_requirements.txt...
.venv\Scripts\pip.exe install -r screenalert_requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo Run launch_ScreenAlert.bat to start the application.
echo.
pause
