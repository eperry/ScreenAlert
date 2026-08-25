@echo off
rem One-time setup: registers a Scheduled Task that runs elevated (highest
rem privileges) as the current user. This script itself must be run as
rem Administrator (right-click -> "Run as administrator") -- that is the
rem ONE UAC prompt you will ever see for this. After setup, admin-run.bat
rem can trigger the task on demand without any further UAC popup, because
rem Windows does not re-prompt for consent when starting an already
rem-registered elevated Scheduled Task.
cd /d "%~dp0"

set "TASK_NAME=ScreenAlertAdminRunner"
set "RUNNER=%~dp0admin-runner.bat"

echo Checking for Administrator privileges...
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This setup script must be run as Administrator.
    echo Right-click admin-setup.bat and choose "Run as administrator".
    pause
    exit /b 1
)

echo Registering Scheduled Task "%TASK_NAME%"...
rem /sc ONCE with a start date already in the past means the task never
rem fires on its own -- it only runs when explicitly triggered via
rem "schtasks /run" (see admin-run.bat).
schtasks /create /tn "%TASK_NAME%" /tr "\"%RUNNER%\"" /sc ONCE /sd 01/01/2020 /st 00:00 /rl HIGHEST /f
if %errorlevel% neq 0 (
    echo ERROR: Failed to create scheduled task.
    pause
    exit /b 1
)

echo.
echo Setup complete. You can now use admin-run.bat to run commands
echo elevated without a UAC popup.
echo.
pause
