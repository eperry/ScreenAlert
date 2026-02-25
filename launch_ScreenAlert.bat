@echo off
setlocal EnableDelayedExpansion

:: Change to the script directory
cd /d "%~dp0"

:: Check if we're in the right directory
if not exist "screenalert.py" exit /b 1

:: Check Python availability (prefer windowed executables to avoid terminal windows)
set PYTHON_FOUND=0
set PYTHON_CMD=

:: Check virtual environment first
if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=.venv\Scripts\pythonw.exe
        set PYTHON_FOUND=1
    )
)

:: Fallback to venv python.exe only if pythonw.exe is not available
if !PYTHON_FOUND! equ 0 if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=.venv\Scripts\python.exe
        set PYTHON_FOUND=1
    )
)

:: Check system Python if venv not found
if !PYTHON_FOUND! equ 0 (
    pythonw --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=pythonw
        set PYTHON_FOUND=1
    ) else (
        pyw --version >nul 2>&1
        if !errorlevel! equ 0 (
            set PYTHON_CMD=pyw
            set PYTHON_FOUND=1
        )
    )
)

:: Fallback to console Python launchers only if no windowed launcher exists
if !PYTHON_FOUND! equ 0 (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=python
        set PYTHON_FOUND=1
    ) else (
        py --version >nul 2>&1
        if !errorlevel! equ 0 (
            set PYTHON_CMD=py
            set PYTHON_FOUND=1
        )
    )
)

:: Exit silently if no Python found
if !PYTHON_FOUND! equ 0 exit /b 1

:: Launch ScreenAlert and immediately close this script window
start "" !PYTHON_CMD! screenalert.py
exit /b 0
