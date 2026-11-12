@echo off
title OmniAgent SPA Build
echo ========================================
echo   OmniAgent SPA Build
echo   Frontend (Vite) + Backend (PyInstaller)
echo ========================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_spa.ps1"
echo.
pause