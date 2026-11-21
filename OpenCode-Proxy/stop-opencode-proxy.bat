@echo off
chcp 936 >nul
setlocal EnableExtensions EnableDelayedExpansion
title OpenCode 本地代理 - 停止

set "TASK=OpenCodeProxyWatchdog"
set "KEEPOFF=0"
if /I "%~1"=="/keepoff" set "KEEPOFF=1"

echo ============================================================
echo   OpenCode 本地代理 - 停止
echo ============================================================
echo.

rem ---------- 1. 找进程 ----------
set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080" ^| findstr "LISTENING"') do set "PID=%%p"
if not defined PID (
    echo [INFO] 18080 当前没有监听，代理未在运行
) else (
    echo [1/3] 停止代理进程 PID=%PID%
    taskkill /PID %PID% /F >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] 停止失败，可能权限不足，请以管理员身份重试
        goto :end
    )
    ping -n 2 127.0.0.1 >nul
    netstat -ano | findstr ":18080" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo   [FAIL] 端口仍被占用，请手动排查: netstat -ano ^| findstr ":18080"
        goto :end
    )
    echo   [OK] 代理已停止，18080 已释放
)

rem ---------- 2. 是否连看门狗一起停 ----------
echo [2/3] 看门狗处理
if "%KEEPOFF%"=="1" (
    schtasks /Change /TN "%TASK%" /DISABLE >nul 2>&1
    if errorlevel 1 (
        echo   [WARN] 禁用看门狗失败，任务可能不存在
    ) else (
        echo   [OK] 已禁用看门狗任务 %TASK%，不会再自动拉起
        echo        恢复自愈: schtasks /Change /TN "%TASK%" /ENABLE
    )
) else (
    echo   [INFO] 看门狗仍启用，5 分钟内会自动把代理拉起
    echo          要长时间停用请运行: stop-opencode-proxy.bat /keepoff
)

rem ---------- 3. 提示 ----------
echo [3/3] 影响说明
echo   opencode 已配置 HTTPS_PROXY=127.0.0.1:18080，代理停止后模型请求会失败
echo   需要恢复请运行: start-opencode-proxy-manual.bat
echo.

:end
echo ============================================================
echo.
pause
exit /b 0
