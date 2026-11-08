@echo off
REM start backend service with watchfiles standalone reloader (fallback when uvicorn --reload stalls) - XiaoOu 2026-11-08
REM same entry/port/watch dir as start.bat; kills+wraps the child process instead of CTRL_C_EVENT
cd /d "%~dp0"

echo Starting backend service... mode: watchfiles
echo Log directory: %~dp0logs\

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1" watch

pause
