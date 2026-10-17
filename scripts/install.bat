@echo off
setlocal
echo ========================================================
echo   Installing Prime Gate Antigravity Dependencies
echo ========================================================

python -m pip install -r "%~dp0..\requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] All dependencies installed successfully!
echo Run scripts\start-all.bat to start the service.
pause
endlocal
