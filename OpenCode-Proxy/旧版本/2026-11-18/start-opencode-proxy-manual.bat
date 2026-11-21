@echo off
setlocal enabledelayedexpansion
title OmniAgent OpenCode Proxy - Manual Start

echo ============================================
echo   OmniAgent OpenCode Proxy Manual Start
echo   Address: 127.0.0.1:18080
echo ============================================
echo.

set NODE=E:\Appsw\nodejs\node.exe
set SCRIPT=E:\Appsw\opencode-proxy.js

if not exist "%NODE%" (
    echo [ERROR] node not found: %NODE%
    goto :fail
)
if not exist "%SCRIPT%" (
    echo [ERROR] proxy script not found: %SCRIPT%
    goto :fail
)

netstat -ano | findstr ":18080" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] Proxy already running on port 18080.
    goto :ok
)

echo [1/2] Starting proxy...
start "" /B "%NODE%" "%SCRIPT%"

set /a tries=0
:waitloop
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":18080" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto :started
set /a tries+=1
if %tries% lss 5 goto :waitloop

echo [ERROR] Port 18080 not listening after 5s.
echo Check: port occupied / node runnable.
goto :fail

:started
echo [2/2] Proxy started, listening 127.0.0.1:18080

:ok
echo.
echo ============================================
echo   [OK] Proxy ready.
echo   Test: curl -x http://127.0.0.1:18080 ...
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo   [FAIL] Start failed, check errors above.
echo ============================================
echo.
pause
exit /b 1
