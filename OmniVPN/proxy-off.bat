@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-off.ps1" -Stop
echo.
echo 已恢复直连
pause
