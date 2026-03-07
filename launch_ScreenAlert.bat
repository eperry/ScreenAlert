@echo off
cd /d "%~dp0"
if not exist "screenalert.py" exit /b 1

set "LOG_DIR=%APPDATA%\ScreenAlert\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "STDOUT_LOG=%LOG_DIR%\screenalert-launcher.log"
set "STDERR_LOG=%LOG_DIR%\screenalert-launcher.err.log"

rem Launch guard: do not start if screenalert.py is already running
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match 'screenalert\.py' }); if ($running.Count -gt 0) { exit 9 } else { exit 0 }"
if %errorlevel% equ 9 exit /b 0

if exist "%~dp0.venv\Scripts\python.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0.venv\Scripts\python.exe' -WorkingDirectory '%~dp0' -ArgumentList 'screenalert.py' -WindowStyle Hidden -RedirectStandardOutput '%STDOUT_LOG%' -RedirectStandardError '%STDERR_LOG%'"
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
