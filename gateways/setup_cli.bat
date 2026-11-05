@echo off
rem setup_cli.bat - 把下游 CLI 复制进 runtime\ 并校验（不联网下载, 6.3.6）
rem 编写人: 小欧    2026-11-05
setlocal
set "SRC=%~1"
if "%SRC%"=="" (
  echo 用法: setup_cli.bat ^(opencode-cli.exe 完整路径^)
  exit /b 2
)
if not exist "%SRC%" ( echo 源文件不存在: %SRC% & exit /b 2 )
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
echo [1/3] 复制...
copy /Y "%SRC%" "%~dp0runtime\opencode-cli.exe" >nul || ( echo 复制失败 & exit /b 2 )
echo [2/3] 校验大小...
for %%F in ("%~dp0runtime\opencode-cli.exe") do set "SIZE=%%~zF"
if %SIZE% LSS 100000000 ( echo 文件 %SIZE% 字节明显偏小, 拒绝使用 & exit /b 2 )
echo [3/3] 校验版本（三关准入的第 1 关由网关完整执行, 6.3.4）...
"%~dp0runtime\opencode-cli.exe" --version || ( echo 版本命令失败 & exit /b 2 )
echo 完成: %~dp0runtime\opencode-cli.exe
endlocal
