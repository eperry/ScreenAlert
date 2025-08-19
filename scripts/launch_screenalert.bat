@echo off
REM ScreenAlert Launcher
REM This batch file launches ScreenAlert with the correct Python environment

cd /d "%~dp0"
echo Starting ScreenAlert...
echo.

REM Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    ".venv\Scripts\python.exe" screenalert.py
) else (
    echo Virtual environment not found, trying system Python...
    python screenalert.py
)

REM Keep window open if there's an error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error occurred! Press any key to close...
    pause >nul
)
