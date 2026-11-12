@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo  quick pool check: reverify pool + revive deadpool (~1-2 min)
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0update-pool-quick.ps1"
echo.
pause
