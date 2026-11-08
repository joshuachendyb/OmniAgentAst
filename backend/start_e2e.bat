@echo off
title OmniAgent Backend (E2E)
echo ========================================
echo  正在启动后端服务 (E2E测试专用)
echo  请勿关闭此窗口，测试完成后按 Ctrl+C 停止
echo ========================================
cd /d "%~dp0"
set LOG_LEVEL=WARNING
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1" watch
echo.
pause
