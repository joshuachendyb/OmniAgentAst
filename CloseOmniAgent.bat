@echo off
rem 关闭OmniAgent.bat — 关闭 OmniAgent 后端服务
rem 2026-11-16 小欧 新建: 优先按进程名精确结束, 未命中再按端口回退; 与 启动/单实例 Mutex 配套
chcp 65001 >nul
setlocal

set "EXE=OmniAgentBackend.exe"
set "PORT=8500"

echo [OmniAgent] 正在关闭后端服务...

rem 1) 优先按进程名精确结束(不误杀同端口的其他程序)
taskkill /F /IM "%EXE%" >nul 2>&1
if not errorlevel 1 (
    echo [OmniAgent] 已结束进程 %EXE%
    goto done
)

rem 2) 进程名未命中(已改名/源码运行): 回退按端口找监听进程 PID
echo [OmniAgent] 未发现 %EXE%, 按端口 %PORT% 查找...
set "FOUND="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr /i "LISTENING"') do (
    set "FOUND=1"
    echo [OmniAgent] 结束占用端口 %PORT% 的进程 PID %%p
    taskkill /F /PID %%p >nul 2>&1
)
if not defined FOUND echo [OmniAgent] 未发现正在运行的服务(端口 %PORT% 空闲)。

:done
timeout /t 2 >nul
endlocal
