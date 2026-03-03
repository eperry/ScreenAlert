@echo off
cd /d "%~dp0"
if not exist "screenalert.py" exit /b 1

set "LOG_DIR=%APPDATA%\ScreenAlert\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "STDOUT_LOG=%LOG_DIR%\screenalert-launcher.log"
set "STDERR_LOG=%LOG_DIR%\screenalert-launcher.err.log"

if exist ".venv\Scripts\python.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '.\\.venv\\Scripts\\python.exe' -WorkingDirectory '%~dp0' -ArgumentList 'screenalert.py' -WindowStyle Hidden -RedirectStandardOutput '%STDOUT_LOG%' -RedirectStandardError '%STDERR_LOG%'"
    exit /b 0
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -WorkingDirectory '%~dp0' -ArgumentList 'screenalert.py' -WindowStyle Hidden -RedirectStandardOutput '%STDOUT_LOG%' -RedirectStandardError '%STDERR_LOG%'"
    exit /b 0
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'py' -WorkingDirectory '%~dp0' -ArgumentList 'screenalert.py' -WindowStyle Hidden -RedirectStandardOutput '%STDOUT_LOG%' -RedirectStandardError '%STDERR_LOG%'"
    exit /b 0
)

exit /b 1
