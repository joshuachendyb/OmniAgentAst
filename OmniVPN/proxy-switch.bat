@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  换出口桶: 撞 429 配额用完时双击
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-switch.ps1"
echo.
echo [bonus] quick pool check: reverify pool + revive deadpool (~1-2 min)...
powershell -ExecutionPolicy Bypass -File "%~dp0update-pool-quick.ps1"
echo.
pause
