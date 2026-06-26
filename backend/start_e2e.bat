@echo off
title OmniAgent Backend (E2E)
echo.
echo 正在启动后端服务 (E2E测试专用)...
echo 请勿关闭此窗口，测试完成后按 Ctrl+C 停止。
echo.
set LOG_LEVEL=WARNING
start "OmniAgent Backend (E2E)" cmd /k "cd /d G:\OmniAgentAs-desk\backend && E:\Appsw\python31311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app"
echo 服务已在新的 cmd 窗口中启动。
echo.
pause
