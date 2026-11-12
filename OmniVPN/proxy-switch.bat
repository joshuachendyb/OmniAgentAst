@echo off
chcp 936 >nul
cd /d "%~dp0"
echo ============================================
echo  ������Ͱ: ײ 429 �������ʱ˫�����
echo ============================================
powershell -ExecutionPolicy Bypass -File "%~dp0proxy-switch.ps1"
echo.
echo [bonus] quick pool check: reverify pool + revive deadpool (~1-2 min)...
powershell -ExecutionPolicy Bypass -File "%~dp0update-pool-quick.ps1"
echo.
pause
