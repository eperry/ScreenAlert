@echo off
rem This script is invoked BY THE SCHEDULED TASK ONLY (it runs elevated).
rem It reads the pending command from admin-command.txt, executes it,
rem captures output to admin-output.log, and writes an exit code +
rem completion marker to admin-status.txt for admin-run.bat to poll.
cd /d "%~dp0"

set "CMD_FILE=%~dp0admin-command.txt"
set "LOG_FILE=%~dp0admin-output.log"
set "STATUS_FILE=%~dp0admin-status.txt"

if not exist "%CMD_FILE%" (
    echo NO_COMMAND> "%STATUS_FILE%"
    exit /b 1
)

set /p ADMIN_CMD=<"%CMD_FILE%"

echo === Running: %ADMIN_CMD% > "%LOG_FILE%"
echo ===================================== >> "%LOG_FILE%"
cmd /c "%ADMIN_CMD%" >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%errorlevel%"

echo DONE %EXIT_CODE%> "%STATUS_FILE%"
exit /b %EXIT_CODE%
