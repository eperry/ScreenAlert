@echo off
echo ScreenAlert Build Script
echo ========================
echo Building native executable with Nuitka...
echo.

python build_nuitka.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build completed successfully!
    echo Executable created at: dist-nuitka\ScreenAlert.exe
    pause
) else (
    echo.
    echo Build failed. Please check the error messages above.
    pause
)
