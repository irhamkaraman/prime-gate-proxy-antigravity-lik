@echo off
setlocal
cd /d "%~dp0.."

echo ========================================================
echo   Launching Prime Gate Antigravity (API + Web UI)
echo ========================================================

python -m prime_gate.cli daemon start
python -m prime_gate.cli quota

echo.
echo Membuka Web UI di browser...
start http://127.0.0.1:52110

echo.
echo Prime Gate aktif di background!
echo Untuk mematikan, jalankan scripts\stop-all.bat atau prime-gate daemon stop
pause
endlocal
