@echo off
cd /d "G:\OmniAgentAs-desk\backend"
echo Starting backend from: %cd%
"E:\Appsw\python31311\python.exe" -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
pause
