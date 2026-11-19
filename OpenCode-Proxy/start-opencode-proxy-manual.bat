@echo off
chcp 936 >nul
setlocal EnableExtensions EnableDelayedExpansion
title OpenCode 本地代理 - 手动启动

set "NODE=E:\Appsw\nodejs\node.exe"
set "PROXY=E:\Appsw\opencode-proxy.js"
set "VBS=E:\Appsw\start-opencode-proxy.vbs"
set "RESTART=0"
if /I "%~1"=="/restart" set "RESTART=1"

echo ============================================================
echo   OpenCode 本地代理 - 手动启动
echo   地址: 127.0.0.1:18080
echo ============================================================
echo.

rem ---------- 0. 前置检查 ----------
if not exist "%NODE%" goto :no_node
if not exist "%PROXY%" goto :no_script

rem ---------- 1. 强制重启 ----------
if "%RESTART%"=="1" (
    echo [INFO] 收到 /restart，先停止现有代理
    call :killproxy
    ping -n 2 127.0.0.1 >nul
)

rem ---------- 2. 端口状态 ----------
call :isport
if "%LISTENING%"=="1" goto :already

echo [1/3] 启动代理
start "" "%WINDIR%\System32\wscript.exe" "%VBS%"
call :waitport 10
if not "%LISTENING%"=="1" goto :not_listen
echo   [OK] 已监听 127.0.0.1:18080
goto :forward

:already
call :isproxy
if "%ISPROXY%"=="1" (
    echo [INFO] 代理已在运行，PID=%PID%
) else (
    echo [FAIL] 18080 被其他程序占用，PID=%PID%
    echo        请先停止该程序: taskkill /PID %PID% /F
    goto :fail
)

rem ---------- 3. 转发验证 ----------
:forward
echo [2/3] 转发验证
call :forwardtest
if not "%CODE%"=="200" goto :bad_forward
echo   [OK] HTTP 200

echo [3/3] 完成
echo.
echo ============================================================
echo   [OK] 代理可用
echo   日志  : E:\Appsw\opencode-proxy.log
echo   自愈  : 计划任务 OpenCodeProxyWatchdog 每 5 分钟检查
echo   停止  : stop-opencode-proxy.bat
echo   体检  : check-opencode-proxy.bat
echo ============================================================
echo.
pause
exit /b 0

:no_node
echo [FAIL] 未找到 node: %NODE%
goto :fail

:no_script
echo [FAIL] 未找到代理脚本: %PROXY%
goto :fail

:not_listen
echo [FAIL] 18080 未在 10 秒内进入监听
echo        排查: 看 E:\Appsw\opencode-proxy.log，或前台运行 node 看报错
goto :fail

:bad_forward
echo   [FAIL] 经代理访问失败，HTTP 返回 %CODE%
echo          检查外网连通性与代理日志
goto :fail

:fail
echo.
echo ============================================================
echo   [FAIL] 启动失败，请按上方提示排查
echo ============================================================
echo.
pause
exit /b 1

rem ---------- 子过程 ----------
:isport
set "LISTENING=0"
set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080" ^| findstr "LISTENING"') do (
    set "PID=%%p"
    set "LISTENING=1"
)
goto :eof

:isproxy
set "ISPROXY=0"
if not defined PID goto :eof
for /f "usebackq delims=" %%c in (`powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=%PID%').CommandLine"`) do set "CMDLINE=%%c"
echo !CMDLINE! | findstr /C:"opencode-proxy.js" >nul
if not errorlevel 1 set "ISPROXY=1"
goto :eof

:waitport
for /l %%i in (1,1,%1) do (
    call :isport
    if "!LISTENING!"=="1" goto :eof
    ping -n 2 127.0.0.1 >nul
)
goto :eof

:killproxy
call :isport
if "%LISTENING%"=="1" (
    taskkill /PID !PID! /F >nul 2>&1
    echo   [OK] 已停止 PID !PID!
)
goto :eof

:forwardtest
set "CODE=000"
for /f %%c in ('curl.exe -s -x http://127.0.0.1:18080 -o NUL -w "%%{http_code}" --max-time 25 "https://models.opencode.ai/experimental/v2.0/api.json?type=chat"') do set "CODE=%%c"
goto :eof
