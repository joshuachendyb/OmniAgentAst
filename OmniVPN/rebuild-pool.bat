@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  rebuild node pool: 11 steps (~20-26 min)
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0rebuild-pool.ps1"
echo.
pause
