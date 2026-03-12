@echo off
REM start backend service
cd /d "%~dp0"

echo Starting backend service...
echo Log directory: %~dp0logs\

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause