@echo off
chcp 65001 >nul
title 上传 Doc2Md Skill 到 GitHub

echo ========================================
echo  上传 Doc2Md Skill 到 GitHub
echo  目标: https://github.com/joshuachendyb/jizx
echo ========================================
echo.
echo  正在启动 PowerShell 脚本...
echo.

:: 检查PowerShell脚本是否存在
if not exist "%~dp0upload_to_github.ps1" (
    echo 错误: 找不到 upload_to_github.ps1 脚本！
    pause
    exit /b 1
)

:: 使用PowerShell执行脚本（绕过执行策略）
powershell -ExecutionPolicy Bypass -File "%~dp0upload_to_github.ps1"

:: 如果PowerShell脚本失败，显示错误
if errorlevel 1 (
    echo.
    echo 上传过程中出现错误。
    echo 请查看上面的错误信息。
    pause
    exit /b 1
)

pause
