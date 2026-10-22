@echo off
setlocal
cd /d "%~dp0.."

echo ========================================================
echo   Updating Prime Gate Antigravity to Latest Release
echo ========================================================
echo.

echo [1/3] Syncing latest code from GitHub (anonymous/clean)...
git -c credential.helper= pull origin main
if %errorlevel% neq 0 (
    echo.
    echo [NOTICE] Standard pull encountered an issue. Retrying with anonymous fallback...
    git -c credential.helper= -c credential.https://github.com.helper= pull origin main
)

echo.
echo [2/3] Checking and updating Python dependencies...
python -m pip install -r requirements.txt --quiet

echo.
echo [3/3] Checking Frontend UI bundle...
if exist "ui\dist\index.html" (
    echo UI bundle is ready.
) else (
    echo Compiling UI bundle...
    where npm >nul 2>&1
    if %errorlevel% equ 0 (
        cd ui
        call npm run build
        cd ..
    )
)

echo.
echo ========================================================
echo   Prime Gate update completed successfully!
echo   You can restart Prime Gate using scripts\start-all.bat
echo ========================================================
echo.
pause
endlocal
