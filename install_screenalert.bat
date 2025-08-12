@echo off
echo ================================================================
echo                     ScreenAlert Installer
echo                 Antivirus-Safe Installation Method
echo ================================================================
echo.
echo This installer will set up ScreenAlert to run from Python source
echo code to avoid false positive antivirus detections.
echo.
pause

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/4] Creating ScreenAlert directory...
if not exist "%USERPROFILE%\ScreenAlert" mkdir "%USERPROFILE%\ScreenAlert"
cd /d "%USERPROFILE%\ScreenAlert"

echo [2/4] Downloading ScreenAlert source code...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/eperry/ScreenAlert/archive/refs/heads/main.zip' -OutFile 'screenalert.zip'"

if not exist "screenalert.zip" (
    echo ERROR: Failed to download ScreenAlert source
    echo Please check your internet connection
    pause
    exit /b 1
)

echo [3/4] Extracting files...
powershell -Command "Expand-Archive -Path 'screenalert.zip' -DestinationPath '.' -Force"

REM Move files from subdirectory to main directory
if exist "ScreenAlert-main" (
    move "ScreenAlert-main\*" "."
    rmdir "ScreenAlert-main"
)

echo [4/4] Installing Python dependencies...
python -m pip install -r screenalert_requirements.txt --quiet

echo.
echo ================================================================
echo                    Installation Complete!
echo ================================================================
echo.
echo ScreenAlert has been installed to: %USERPROFILE%\ScreenAlert
echo.
echo To run ScreenAlert, use one of these methods:
echo   1. Double-click 'run_screenalert.bat' in the installation folder
echo   2. Run: python "%USERPROFILE%\ScreenAlert\screenalert.py"
echo.
echo Creating desktop shortcut...

REM Create a run script
echo @echo off > run_screenalert.bat
echo cd /d "%%~dp0" >> run_screenalert.bat
echo python screenalert.py >> run_screenalert.bat
echo pause >> run_screenalert.bat

REM Create desktop shortcut
set SHORTCUT="%USERPROFILE%\Desktop\ScreenAlert.lnk"
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = '%USERPROFILE%\ScreenAlert\run_screenalert.bat'; $Shortcut.WorkingDirectory = '%USERPROFILE%\ScreenAlert'; $Shortcut.Description = 'ScreenAlert - Advanced Screen Monitoring'; $Shortcut.Save()"

echo.
echo Desktop shortcut created: ScreenAlert
echo.
echo Would you like to run ScreenAlert now? (Y/N)
set /p choice=
if /i "%choice%"=="Y" (
    echo Starting ScreenAlert...
    start "" run_screenalert.bat
)

echo.
echo Installation complete! ScreenAlert is ready to use.
pause
