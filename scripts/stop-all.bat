@echo off
setlocal
cd /d "%~dp0.."

echo ========================================================
echo   Stopping Prime Gate Antigravity Daemon
echo ========================================================

python -m prime_gate.cli daemon stop
pause
endlocal
