@echo off
chcp 65001 >nul
REM 2026-11-02 小欧 - 前端停止入口: 结束隐藏窗口中的 vite 整棵进程树 (调用 stop_frontend.ps1)
cd /d "%~dp0"
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_frontend.ps1" %*
pause
