@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo  开启代理: 启动 mihomo + 设系统代理 127.0.0.1:7890
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-on.ps1"
echo.
echo 窗口可以留着, 关掉不影响代理运行 (mihomo 是独立进程)
pause
