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
echo [INFO] Registering 'prime-gate' global CLI command...
python -m pip install -e "%~dp0.." --no-warn-script-location
if %errorlevel% neq 0 (
    echo [WARNING] Could not register global CLI in editable mode. You can still run via scripts\setup-path.bat.
)

echo.
echo [SUCCESS] All dependencies and Prime Gate CLI installed successfully!
echo Tip: Run scripts\setup-path.bat once if 'prime-gate' is not recognized globally.
echo Run scripts\start-all.bat to start the service.
pause
endlocal
