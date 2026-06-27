@echo off
title OmniAgent Backend (E2E)
echo ========================================
echo  正在启动后端服务 (E2E测试专用)
echo  请勿关闭此窗口，测试完成后按 Ctrl+C 停止
echo ========================================
cd /d G:\OmniAgentAs-desk\backend
set LOG_LEVEL=WARNING
E:\Appsw\python31311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
echo.
pause
