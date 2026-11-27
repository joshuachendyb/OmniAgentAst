@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-on-single.ps1"
echo.
echo 窗口可以留着, 关掉不影响代理运行 (mihomo 是独立进程)
pause
