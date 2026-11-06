@echo off
title OmniAgent SPA Build
echo ========================================
echo   SPA Build (frontend + backend)
echo ========================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_spa.ps1"
echo.
pause