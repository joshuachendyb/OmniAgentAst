@echo off
chcp 936 >nul
setlocal EnableExtensions EnableDelayedExpansion
title OpenCode 本地代理 - 运行状态检查

set "CFG=%USERPROFILE%\.config\opencode\service.json"
set "TASK=OpenCodeProxyWatchdog"
set "LOGP=E:\Appsw\opencode-proxy.log"
set "LOGW=E:\Appsw\opencode-proxy-watchdog.log"
set "BAD=0"

echo ============================================================
echo   OpenCode 本地代理 - 运行状态检查
echo   时间: %DATE% %TIME%
echo ============================================================
echo.

rem ---------- 1. 端口 ----------
echo [1/7] 监听状态
set "PID="
set "LISTENING=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":18080" ^| findstr "LISTENING"') do (
    set "PID=%%p"
    set "LISTENING=1"
)
if "%LISTENING%"=="1" (
    echo   [OK] 127.0.0.1:18080 正在监听，PID=%PID%
) else (
    echo   [FAIL] 127.0.0.1:18080 没有监听，代理未运行
    set "BAD=1"
)
echo.

rem ---------- 2. 进程身份 ----------
echo [2/7] 进程身份
if "%LISTENING%"=="1" (
    for /f "usebackq delims=" %%c in (`powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=%PID%').CommandLine"`) do set "CMDLINE=%%c"
    echo   命令行: !CMDLINE!
    echo !CMDLINE! | findstr /C:"opencode-proxy.js" >nul
    if errorlevel 1 (
        echo   [WARN] 该 PID 不是代理进程，端口可能被其他程序占用
        set "BAD=1"
    ) else (
        echo   [OK] 确认是 opencode-proxy.js
    )
) else (
    echo   [SKIP] 无监听进程
)
echo.

rem ---------- 3. 转发 ----------
echo [3/7] 代理转发实测
if not "%LISTENING%"=="1" goto :fwd_skip
set "CODE=000"
call :forwardtest
if "%CODE%"=="200" goto :fwd_ok
echo   [FAIL] 经代理访问失败，HTTP 返回 %CODE%
set "BAD=1"
goto :fwd_end
:fwd_ok
echo   [OK] 经代理访问 models.opencode.ai 返回 HTTP 200
goto :fwd_end
:fwd_skip
echo   [SKIP] 代理未运行，无法测试转发
:fwd_end
echo.

rem ---------- 4. opencode 接入 ----------
echo [4/7] opencode 是否走代理
set "LINK=0"
powershell -NoProfile -Command "$p=(Get-Process opencode-cli -ErrorAction SilentlyContinue | Select-Object -First 1).Id; if($p){@(Get-NetTCPConnection -OwningProcess $p -State Established -ErrorAction SilentlyContinue | Where-Object {$_.RemotePort -eq 18080}).Count}else{0}" > "%TEMP%\oc_link.txt" 2>nul
if exist "%TEMP%\oc_link.txt" set /p LINK=<"%TEMP%\oc_link.txt"
del "%TEMP%\oc_link.txt" >nul 2>&1
if not defined LINK set "LINK=0"
if "%LINK%"=="0" (
    echo   [WARN] 未发现 opencode 到 18080 的连接，可能当前无请求或配置未生效
) else (
    echo   [OK] opencode 到 18080 的连接数: %LINK%
)
echo.

rem ---------- 5. 配置 ----------
echo [5/7] opencode 代理配置
if exist "%CFG%" (
    findstr /C:"18080" "%CFG%" >nul
    if errorlevel 1 (
        echo   [FAIL] service.json 中没有 HTTPS_PROXY=127.0.0.1:18080
        set "BAD=1"
    ) else (
        echo   [OK] service.json 已配置 HTTPS_PROXY
    )
) else (
    echo   [FAIL] 未找到 %CFG%
    set "BAD=1"
)
echo.

rem ---------- 6. 看门狗 ----------
echo [6/7] 看门狗任务
set "TINFO="
for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "try{$t=Get-ScheduledTask -TaskName '%TASK%' -ErrorAction Stop;$i=Get-ScheduledTaskInfo -TaskName '%TASK%';$n=if($i.NextRunTime){$i.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss')}else{'none'};'State=' + $t.State + ' Next=' + $n + ' LastResult=' + $i.LastTaskResult}catch{'MISSING'}"`) do set "TINFO=%%v"
if not defined TINFO (
    echo   [FAIL] 无法读取任务信息，请以管理员身份重试
    set "BAD=1"
) else (
    echo   %TINFO% | findstr /C:"MISSING" >nul
    if errorlevel 1 (
        echo   [OK] %TINFO%
        echo   [INFO] LastResult=0 正常，267009 正在运行，267011 尚未运行，其他值为异常
        echo   %TINFO% | findstr /C:"Disabled" >nul
        if not errorlevel 1 (
            echo   [FAIL] 看门狗任务当前被禁用，代理崩溃后不会自愈
            echo          恢复: schtasks /Change /TN "%TASK%" /ENABLE
            set "BAD=1"
        )
    ) else (
        echo   [FAIL] 计划任务 %TASK% 不存在，崩溃后不会自愈
        set "BAD=1"
    )
)
echo.

rem ---------- 7. 日志 ----------
echo [7/7] 日志尾部
if exist "%LOGP%" (
    for /f "usebackq delims=" %%l in (`powershell -NoProfile -Command "Get-Content '%LOGP%' -Tail 3"`) do echo   代理^| %%l
) else (
    echo   [WARN] 未找到代理日志 %LOGP%
)
if exist "%LOGW%" (
    for /f "usebackq delims=" %%l in (`powershell -NoProfile -Command "Get-Content '%LOGW%' -Tail 2"`) do echo   看门狗^| %%l
)
echo.

echo ============================================================
if "%BAD%"=="0" (
    echo   [OK] 检查通过，代理与自愈链路正常
) else (
    echo   [FAIL] 发现异常，请按上方 [FAIL]/[WARN] 提示处理
)
echo   手动启动: start-opencode-proxy-manual.bat
echo   停止代理: stop-opencode-proxy.bat
echo ============================================================
echo.
pause
exit /b %BAD%

:forwardtest
set "CODE=000"
for /f %%c in ('curl.exe -s -x http://127.0.0.1:18080 -o NUL -w "%%{http_code}" --max-time 25 "https://models.opencode.ai/experimental/v2.0/api.json?type=chat"') do set "CODE=%%c"
goto :eof
