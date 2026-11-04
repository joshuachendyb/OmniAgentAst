@echo off
chcp 65001 >nul
REM 2026-11-02 小欧 - 前端常驻启动入口: 双击即隐藏窗口后台启动 vite dev, 关掉本窗口不影响前端 (调用 start_frontend.ps1)
cd /d "%~dp0"
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_frontend.ps1" %*
if errorlevel 1 pause
