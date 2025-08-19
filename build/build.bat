@echo off
echo ScreenAlert Build Script
echo ========================
echo.
echo Choose build type:
echo 1. Production Build (optimized, slower)
echo 2. Development Build (fast, debug enabled)
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo Building production executable with Nuitka...
    python build_nuitka.py
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo Production build completed successfully!
        echo Executable created at: dist-nuitka\ScreenAlert.exe
    ) else (
        echo.
        echo Production build failed. Please check the error messages above.
    )
) else if "%choice%"=="2" (
    echo.
    echo Building development executable with Nuitka (fast mode)...
    python build_fast.py
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo Development build completed successfully!
        echo Executable created at: dist-dev\ScreenAlert-dev.exe
    ) else (
        echo.
        echo Development build failed. Please check the error messages above.
    )
) else (
    echo Invalid choice. Please run the script again and choose 1 or 2.
)

echo.
pause
