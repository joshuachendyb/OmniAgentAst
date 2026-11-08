@echo off
REM start backend service (dev hot reload) - XiaoOu 2026-11-02
REM no arg  -> uvicorn --reload (default)
REM watch   -> watchfiles standalone reloader
REM both reloaders have hang history on Windows, see AGENTS.md; switch when one stalls
cd /d "%~dp0"

echo Starting backend service... mode: %~1
echo Log directory: %~dp0logs\

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1" %*

pause
