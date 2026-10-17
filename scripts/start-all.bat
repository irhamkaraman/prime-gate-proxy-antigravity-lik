@echo off
setlocal
cd /d "%~dp0.."

echo ========================================================
echo   Launching Prime Gate Antigravity (API + Web UI)
echo ========================================================

python -m prime_gate.cli daemon start
python -m prime_gate.cli quota

echo.
echo Opening Web UI in browser...
start http://127.0.0.1:52110

echo.
echo Prime Gate is running in the background!
echo To stop the service, run scripts\stop-all.bat or prime-gate daemon stop
pause
endlocal
