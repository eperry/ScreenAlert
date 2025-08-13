@echo off
echo Building ScreenAlert with Nuitka...

REM Change to script directory
cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Create output directory
if not exist "dist-nuitka" mkdir "dist-nuitka"

REM Nuitka compilation with Windows-specific optimizations
python -m nuitka ^
    --onefile ^
    --standalone ^
    --assume-yes-for-downloads ^
    --enable-plugin=tk-inter ^
    --enable-plugin=numpy ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=screenalert_icon.ico ^
    --product-name="ScreenAlert" ^
    --file-description="Screen monitoring and alert system" ^
    --product-version="1.0.0" ^
    --file-version="1.0.0.0" ^
    --copyright="© 2025 ScreenAlert" ^
    --output-dir=dist-nuitka ^
    --output-filename=ScreenAlert.exe ^
    --include-data-files=screenalert_config.json=screenalert_config.json ^
    --remove-output ^
    --report=compilation-report.xml ^
    screenalert.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Build completed successfully!
    echo ✓ Executable created: dist-nuitka\ScreenAlert.exe
    echo.
    dir "dist-nuitka\ScreenAlert.exe"
) else (
    echo ✗ Build failed with error code %ERRORLEVEL%
)

pause
