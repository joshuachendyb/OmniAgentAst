@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-off-single.ps1" -Stop
echo.
pause
