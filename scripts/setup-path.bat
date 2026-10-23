@echo off
setlocal
echo ========================================================
echo   Configuring Prime Gate Global CLI for Windows (PATH)
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-path.ps1"

echo.
pause
endlocal
