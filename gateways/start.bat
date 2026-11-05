@echo off
rem start.bat - 启动网关。NO_PROXY 显式设置: 回环请求不得走系统代理（9.7 表第 2 条）
rem 编写人: 小欧    2026-11-05
setlocal
set "NO_PROXY=127.0.0.1,localhost"
set "no_proxy=127.0.0.1,localhost"
cd /d "%~dp0"
python gateway.py
endlocal
