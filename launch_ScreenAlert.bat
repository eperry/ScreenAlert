@echo off
setlocal EnableDelayedExpansion

:: ScreenAlert Launcher
:: Checks for Python availability and launches the application

echo.
echo ================================
echo    ScreenAlert Launcher v1.1
echo ================================
echo.

:: Change to the script directory
cd /d "%~dp0"

:: Check if we're in the right directory (look for screenalert.py)
if not exist "screenalert.py" (
    echo ERROR: screenalert.py not found in current directory!
    echo Make sure this batch file is in the same folder as screenalert.py
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

:: Function to check Python version
set PYTHON_FOUND=0
set PYTHON_CMD=
set VENV_PYTHON=

echo Checking for Python installation...
echo.

:: Check if virtual environment exists and has Python
if exist ".venv\Scripts\python.exe" (
    echo Found virtual environment Python: .venv\Scripts\python.exe
    set VENV_PYTHON=.venv\Scripts\python.exe
    
    :: Test the venv Python
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%i in ('".venv\Scripts\python.exe" --version 2^>^&1') do (
            echo Virtual environment Python version: %%i
            set PYTHON_CMD=.venv\Scripts\python.exe
            set PYTHON_FOUND=1
        )
    ) else (
        echo WARNING: Virtual environment Python is not working properly
    )
    echo.
)

:: If venv Python not found or not working, check system Python
if !PYTHON_FOUND! equ 0 (
    echo Checking for system Python installation...
    
    :: Try python command
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
            echo Found system Python version: %%i
            set PYTHON_CMD=python
            set PYTHON_FOUND=1
        )
    ) else (
        :: Try py launcher (Windows Python Launcher)
        py --version >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=2" %%i in ('py --version 2^>^&1') do (
                echo Found Python via py launcher version: %%i
                set PYTHON_CMD=py
                set PYTHON_FOUND=1
            )
        )
    )
)

:: Check if any Python was found
if !PYTHON_FOUND! equ 0 (
    echo.
    echo ================================
    echo        ERROR: NO PYTHON FOUND
    echo ================================
    echo.
    echo Python is required to run ScreenAlert.
    echo.
    echo Please install Python from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    echo Alternatively, you can create a virtual environment:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r screenalert_requirements.txt
    echo.
    pause
    exit /b 1
)

:: Check if requirements are installed
echo.
echo Checking Python dependencies...

:: Test import of key modules
!PYTHON_CMD! -c "import pyautogui, PIL, tkinter, numpy, cv2; print('✓ All required modules found')" >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo WARNING: Some required Python modules may be missing.
    echo.
    echo If you're using the virtual environment, make sure dependencies are installed:
    echo   .venv\Scripts\activate
    echo   pip install -r screenalert_requirements.txt
    echo.
    echo If you're using system Python, install dependencies with:
    echo   pip install -r screenalert_requirements.txt
    echo.
    set /p CONTINUE="Continue anyway? (y/N): "
    if /i not "!CONTINUE!"=="y" (
        echo Launch cancelled.
        pause
        exit /b 1
    )
) else (
    echo ✓ Python dependencies verified
)

:: Launch ScreenAlert
echo.
echo ================================
echo      Launching ScreenAlert...
echo ================================
echo.
echo Using Python: !PYTHON_CMD!
echo Command: !PYTHON_CMD! screenalert.py
echo.

:: Launch the application
!PYTHON_CMD! screenalert.py

:: Check exit code
if !errorlevel! neq 0 (
    echo.
    echo ================================
    echo     APPLICATION ERROR
    echo ================================
    echo.
    echo ScreenAlert exited with error code: !errorlevel!
    echo.
    echo Check the error messages above for details.
    echo.
    pause
    exit /b !errorlevel!
)

echo.
echo ScreenAlert closed successfully.
echo.
pause
