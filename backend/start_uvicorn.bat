@echo off
REM start backend service with uvicorn --reload (default entry) - XiaoOu 2026-11-08
REM watchfiles entry: start_watch.bat; uvicorn reload can hang at basereload self.process.join(), see AGENTS.md
cd /d "%~dp0"

echo Starting backend service... mode: uvicorn --reload
echo Log directory: %~dp0logs\

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev.ps1" %*

pause
