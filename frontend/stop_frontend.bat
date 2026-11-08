@echo off
REM 2026-11-02 XiaoOu - frontend stop entry: kills the hidden-window vite process tree (calls stop_frontend.ps1)
REM 2026-11-08 XiaoOu - pwsh->powershell (no pwsh on this machine); ASCII-only comments, cmd.exe mispieces UTF-8+CJK batch files - XiaoOu 2026-11-08
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_frontend.ps1" %*
pause
