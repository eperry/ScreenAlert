@echo off
setlocal EnableDelayedExpansion

:: Change to the script directory
cd /d "%~dp0"

:: Check if we're in the right directory
if not exist "screenalert.py" exit /b 1

:: Check Python availability
set PYTHON_FOUND=0
set PYTHON_CMD=

:: Check virtual environment first
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=.venv\Scripts\python.exe
        set PYTHON_FOUND=1
    )
)

:: Check system Python if venv not found
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

:: Launch ScreenAlert without showing command window
start /B !PYTHON_CMD! screenalert.py
