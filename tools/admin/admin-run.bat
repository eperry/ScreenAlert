@echo off
rem Runs any command elevated, with no UAC popup, via the Scheduled Task
rem registered by admin-setup.bat (run that once first).
rem
rem Usage:
rem   admin-run.bat "command and args here"
rem Example:
rem   admin-run.bat "ipconfig /all"
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "TASK_NAME=ScreenAlertAdminRunner"
set "CMD_FILE=%~dp0admin-command.txt"
set "LOG_FILE=%~dp0admin-output.log"
set "STATUS_FILE=%~dp0admin-status.txt"

if "%~1"=="" (
    echo Usage: admin-run.bat "command to run"
    exit /b 1
)

schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Scheduled task "%TASK_NAME%" not found.
    echo Run admin-setup.bat as Administrator first ^(one-time setup^).
    exit /b 1
)

if exist "%STATUS_FILE%" del /f /q "%STATUS_FILE%" >nul 2>&1
if exist "%LOG_FILE%" del /f /q "%LOG_FILE%" >nul 2>&1

rem %* preserves the full command line the caller passed in.
echo %*> "%CMD_FILE%"

echo Running elevated: %*
schtasks /run /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to trigger scheduled task.
    exit /b 1
)

rem Poll for completion (up to ~60 seconds).
set "WAITED=0"
:WAIT_LOOP
if exist "%STATUS_FILE%" goto :DONE
timeout /t 1 /nobreak >nul
set /a WAITED+=1
if %WAITED% geq 60 (
    echo WARNING: Timed out waiting for command to finish. Check %LOG_FILE% manually.
    goto :SHOWLOG
)
goto :WAIT_LOOP

:DONE
echo.
echo ----- Output -----

:SHOWLOG
if exist "%LOG_FILE%" type "%LOG_FILE%"
echo -------------------

if exist "%STATUS_FILE%" (
    for /f "tokens=1,2" %%A in (%STATUS_FILE%) do set "RESULT=%%A" & set "CODE=%%B"
    if "!RESULT!"=="DONE" exit /b !CODE!
)
exit /b 1
