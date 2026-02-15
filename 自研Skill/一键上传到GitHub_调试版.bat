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

:: 显示当前目录（调试用）
echo [调试] 当前目录: %~dp0
echo.

:: 检查PowerShell脚本是否存在
if not exist "%~dp0upload_to_github.ps1" (
    echo [错误] 找不到 upload_to_github.ps1 脚本！
    echo [错误] 请确保文件在相同目录下
    echo.
    pause
    exit /b 1
)

echo [1] PowerShell脚本存在，准备执行...
echo.

:: 使用PowerShell执行脚本（绕过执行策略）
echo [2] 正在执行PowerShell脚本...
echo ----------------------------------------
powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0upload_to_github.ps1"

:: 捕获退出代码
set EXIT_CODE=%ERRORLEVEL%

echo ----------------------------------------
echo.

:: 检查执行结果
if %EXIT_CODE% neq 0 (
    echo.
    echo [错误] PowerShell脚本执行失败！
    echo [错误] 退出代码: %EXIT_CODE%
    echo.
    echo 可能的原因：
    echo 1. PowerShell执行策略限制
    echo 2. Git未安装或不在PATH中
    echo 3. 网络连接问题
    echo 4. 权限不足
    echo.
    echo 请尝试以下方法：
    echo 方法1: 右键点击此文件，选择"以管理员身份运行"
    echo 方法2: 打开PowerShell，手动执行: .\upload_to_github.ps1
    echo.
    pause
    exit /b 1
)

echo.
echo [成功] 脚本执行完成！
pause
