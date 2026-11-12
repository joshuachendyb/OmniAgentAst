@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo  关闭代理: 取消系统代理 + 停止 mihomo
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-off.ps1" -Stop
echo.
echo 已恢复直连
pause
