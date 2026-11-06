@echo off
REM ============================================================================
REM deploy_spa.bat - 同源SPA 一键部署(按文档"同源SPA打包与部署说明"3.4节)
REM 创建: 2026-11-06 小欧
REM 依据: doc-打包与E2E\同源SPA打包与部署说明-小杨-2026-10-27.md 3.4节 升级部署方式
REM   本机实际部署目录: G:\OmniAgent-SPA (2026-10-30 小欧补记)
REM   只替换 exe + OmniAgent使用说明.md + _internal/, config/files/logs/version.txt 一律不动
REM 用法: deploy_spa.bat [目标目录]
REM   [目标目录] 可选, 缺省用 G:\OmniAgent-SPA; 传其他目录可部署到测试位置
REM 注意: 本文件必须用 GBK/ANSI 编码 + CRLF 换行保存(cmd 解析 .bat 用系统 ANSI 代码页)
REM   不用 if 括号块(块内 echo 含括号会触发"此时不应有"), 全部用 goto 标签
REM ============================================================================
chcp 936 >nul
setlocal

REM ── 定位仓库根(本 bat 所在目录, 稳妥去尾部反斜杠) ──
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DEPLOY_SCRIPT=%ROOT%\backend\deploy_spa.py"

REM ── 目标目录: 参数1优先, 缺省本机部署目录 ──
set "TARGET=G:\OmniAgent-SPA"
if not "%~1"=="" set "TARGET=%~1"

echo ============================================================
echo   同源SPA 部署  -^>  %TARGET%
echo ============================================================
echo.

REM ── 前置检查: 部署脚本存在(缺则跳标签) ──
if not exist "%DEPLOY_SCRIPT%" goto :noScript

REM ── 前置检查: 打包产物存在(缺则跳标签) ──
if not exist "%ROOT%\backend\dist\OmniAgentBackend\OmniAgentBackend.exe" goto :noDist

echo [OK] 打包产物存在: backend\dist\OmniAgentBackend\
echo [..] 正在部署(调用 backend\deploy_spa.py)...
echo [..] 默认 dist=backend\dist\OmniAgentBackend
echo.

REM ── 调用部署脚本(进程占用/产物缺失由脚本自行判断并给出退出码) ──
python "%DEPLOY_SCRIPT%" --target "%TARGET%"
set "RC=%errorlevel%"
echo.

REM ── 按退出码提示(用 goto 标签, cmd 不支持 else if 链) ──
if "%RC%"=="0" goto :rc0
if "%RC%"=="1" goto :rc1
if "%RC%"=="2" goto :rc2
if "%RC%"=="3" goto :rc3
goto :rcOther

:noScript
echo [FAIL] 部署脚本不存在: %DEPLOY_SCRIPT%
echo        请确认本 bat 放在仓库根目录, 与 backend 同级。
goto :end

:noDist
echo [FAIL] 打包产物缺失: %ROOT%\backend\dist\OmniAgentBackend\
echo        请先执行 build_spa.bat 打包, 再运行本部署脚本。
goto :end

:rc0
echo [OK] 部署完成! 目标目录: %TARGET%
goto :end

:rc1
echo [WARN] 目标 exe 正在运行, 部署未执行, 退出码 1。
echo        请先停止进程再重跑: taskkill /F /IM OmniAgentBackend.exe
goto :end

:rc2
echo [FAIL] 打包产物不完整, 退出码 2。请先 build_spa.bat 打包。
goto :end

:rc3
echo [FAIL] 写入被拒, 可能仍有进程占用文件, 退出码 3。
echo        请停止所有 OmniAgentBackend.exe 后重试。
goto :end

:rcOther
echo [FAIL] 部署脚本异常返回, 退出码 %RC%。
goto :end

:end
echo.
pause
endlocal
