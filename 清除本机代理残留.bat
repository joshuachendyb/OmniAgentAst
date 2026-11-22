@echo off
title Clear local proxy leftovers
echo ============================================================
echo  Clear local proxy leftovers
echo  Use when this machine needs NO proxy: removes leftover
echo  system proxy settings from earlier B-machine debugging
echo  (ProxyEnable / ProxyServer / ProxyOverride), restore direct.
echo ============================================================
echo.

set "KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

reg delete "%KEY%" /v ProxyEnable   /f >nul 2>&1
reg delete "%KEY%" /v ProxyServer   /f >nul 2>&1
reg delete "%KEY%" /v ProxyOverride /f >nul 2>&1

echo Cleared ProxyEnable / ProxyServer / ProxyOverride.
echo.
echo Current system proxy settings (should all be absent):
reg query "%KEY%" /v ProxyEnable   2>nul || echo   ProxyEnable   : NOT FOUND (cleared)
reg query "%KEY%" /v ProxyServer   2>nul || echo   ProxyServer   : NOT FOUND (cleared)
reg query "%KEY%" /v ProxyOverride 2>nul || echo   ProxyOverride : NOT FOUND (cleared)

echo.
echo Note: Python/httpx reads registry live, effective immediately;
echo       browsers already open may need a restart to drop old proxy.
echo.
pause
