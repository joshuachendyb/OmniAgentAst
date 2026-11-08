@echo off
REM 2026-11-02 XiaoOu - frontend service entry: double-click starts vite dev in hidden window, closing this window keeps frontend alive (calls start_frontend.ps1)
REM 2026-11-08 XiaoOu - pwsh->powershell (no pwsh on this machine); ASCII-only comments, cmd.exe mispieces UTF-8+CJK batch files - XiaoOu 2026-11-08
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_frontend.ps1" %*
if errorlevel 1 pause
