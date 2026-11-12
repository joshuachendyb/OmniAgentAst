@echo off
chcp 936 >nul
cd /d "%~dp0.."
echo ============================================
echo  rebuild node pool: 9 steps (~15 min)
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0rebuild-pool.ps1"
echo.
pause
