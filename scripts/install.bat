@echo off
setlocal
echo ========================================================
echo   Installing Prime Gate Antigravity Dependencies
echo ========================================================

python -m pip install -r "%~dp0..\requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Gagal menginstall dependencies Python.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Semua dependencies terinstall dengan sukses!
echo Silakan jalankan scripts\start-all.bat untuk memulai.
pause
endlocal
