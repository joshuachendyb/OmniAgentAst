@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo  换出口桶: 撞 429 配额用完时双击这个
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-switch.ps1"
echo.
pause
