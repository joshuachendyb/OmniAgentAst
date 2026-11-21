@echo off
chcp 936 >nul
setlocal EnableExtensions EnableDelayedExpansion
title OpenCode 本地代理 - 一键部署

set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "DST=E:\Appsw"
set "NODE=%DST%\nodejs\node.exe"
set "PROXY=%DST%\opencode-proxy.js"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "CFG=%USERPROFILE%\.config\opencode\service.json"
set "TASK=OpenCodeProxyWatchdog"
set "FILES=opencode-proxy.js watchdog-opencode-proxy.ps1 run-watchdog-hidden.vbs start-opencode-proxy.vbs start-opencode-proxy-manual.bat check-opencode-proxy.bat stop-opencode-proxy.bat"
set FAIL=0

echo ============================================================
echo   OpenCode 本地代理 - 一键部署
echo   源目录  : %SRC%
echo   目标目录: %DST%
echo ============================================================
echo.

rem ---------- 1. 前置检查 ----------
echo [1/7] 前置检查
if not exist "%NODE%" (
    echo   [FAIL] 未找到 node: %NODE%
    set FAIL=1
    goto :summary
)
for %%F in (%FILES%) do (
    if not exist "%SRC%\%%F" (
        echo   [FAIL] 源文件缺失: %%F
        set FAIL=1
    )
)
if "%FAIL%"=="1" goto :summary
echo   [OK] node 与全部源文件就绪
echo.

rem ---------- 2. 备份 ----------
echo [2/7] 备份现有部署文件
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%i"
set "BAK=%DST%\backup\deploy-%TS%"
mkdir "%BAK%" >nul 2>&1
for %%F in (%FILES%) do (
    if exist "%DST%\%%F" copy /Y "%DST%\%%F" "%BAK%\" >nul
)
echo   [OK] 已备份到 %BAK%
echo.

rem ---------- 3. 复制 ----------
echo [3/7] 复制脚本到 %DST%
for %%F in (%FILES%) do (
    copy /Y "%SRC%\%%F" "%DST%\%%F" >nul
    if errorlevel 1 (
        echo   [FAIL] 复制失败: %%F
        set FAIL=1
    )
)
if "%FAIL%"=="1" goto :summary
echo   [OK] 脚本已就位
copy /Y "%SRC%\deploy-opencode-proxy.bat" "%DST%\deploy-opencode-proxy.bat" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] 部署脚本自身未复制（运行中被锁定），可从 %SRC% 重新运行
) else (
    echo   [OK] 部署脚本本身已同步
)
echo.

rem ---------- 4. 语法自检 ----------
echo [4/7] node 语法自检
"%NODE%" --check "%PROXY%"
if errorlevel 1 (
    echo   [FAIL] opencode-proxy.js 语法检查未通过
    set FAIL=1
    goto :summary
)
echo   [OK] 语法检查通过
echo.

rem ---------- 5. 启动代理 ----------
echo [5/7] 启动代理
call :isport
if "%LISTENING%"=="1" (
    echo   [INFO] 代理已在运行，跳过启动
) else (
    start "" "%WINDIR%\System32\wscript.exe" "%DST%\start-opencode-proxy.vbs"
    call :waitport 10
)
if not "%LISTENING%"=="1" (
    echo   [FAIL] 18080 未在 10 秒内进入监听
    set FAIL=1
    goto :summary
)
echo   [OK] 已监听 127.0.0.1:18080
echo.

rem ---------- 6. 自启与看门狗 ----------
echo [6/7] 开机自启与看门狗计划任务
copy /Y "%DST%\start-opencode-proxy.vbs" "%STARTUP%\" >nul
if errorlevel 1 (
    echo   [WARN] 启动文件夹写入失败，请检查路径: %STARTUP%
) else (
    echo   [OK] 开机自启已部署
)
schtasks /Query /TN "%TASK%" >nul 2>&1
if errorlevel 1 (
    schtasks /Create /TN "%TASK%" /SC MINUTE /MO 5 /TR "\"%WINDIR%\System32\wscript.exe\" \"%DST%\run-watchdog-hidden.vbs\"" /F >nul
) else (
    schtasks /Delete /TN "%TASK%" /F >nul 2>&1
    schtasks /Create /TN "%TASK%" /SC MINUTE /MO 5 /TR "\"%WINDIR%\System32\wscript.exe\" \"%DST%\run-watchdog-hidden.vbs\"" /F >nul
)
schtasks /Query /TN "%TASK%" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] 看门狗任务注册失败，请以管理员身份重试
    set FAIL=1
    goto :summary
)
echo   [OK] 看门狗任务已注册，每 5 分钟自愈且不弹窗
echo.

rem ---------- 7. 联调验收 ----------
echo [7/7] 联调验收
if exist "%CFG%" (
    findstr /C:"18080" "%CFG%" >nul
    if errorlevel 1 (
        echo   [WARN] service.json 未配置 HTTPS_PROXY，请执行:
        echo          opencode service set env HTTPS_PROXY http://127.0.0.1:18080
    ) else (
        echo   [OK] opencode 已配置走代理
    )
) else (
    echo   [WARN] 未找到配置文件: %CFG%
)
call :forwardtest
if not "%CODE%"=="200" (
    echo   [FAIL] 代理转发异常，HTTP 返回 %CODE%
    set FAIL=1
    goto :summary
)
echo   [OK] 代理转发正常，HTTP 200
echo.

:summary
echo ============================================================
if "%FAIL%"=="0" (
    echo   [OK] 部署完成，代理可用
    echo   日志: %DST%\opencode-proxy.log
    echo   验收: 双击 check-opencode-proxy.bat
) else (
    echo   [FAIL] 部署未完成，请按上方提示排查后重跑
)
echo ============================================================
echo.
pause
exit /b %FAIL%

rem ---------- 子过程 ----------
:isport
set "LISTENING=0"
netstat -ano | findstr ":18080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set "LISTENING=1"
goto :eof

:waitport
set "LISTENING=0"
for /l %%i in (1,1,%1) do (
    call :isport
    if "!LISTENING!"=="1" goto :eof
    ping -n 2 127.0.0.1 >nul
)
goto :eof

:forwardtest
set "CODE=000"
for /f %%c in ('curl.exe -s -x http://127.0.0.1:18080 -o NUL -w "%%{http_code}" --max-time 25 "https://models.opencode.ai/experimental/v2.0/api.json?type=chat"') do set "CODE=%%c"
goto :eof
