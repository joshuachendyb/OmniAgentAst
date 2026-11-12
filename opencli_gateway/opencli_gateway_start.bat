@echo off
chcp 936 >nul
rem opencli gateway 启动壳: 前台运行网关, 关窗即停 - xiaoou 2026-11-09
rem 更新: 2026-11-12 xiaoou 更名 opencli_gateway_start.bat(母本目录前缀, 名实相符); 输出文案人类化: 启动前查重(已在运行不重复启动), 端点/管理台/配置/停止方式一览, 进程退出时给出排查提示
cd /d "%~dp0"
echo ============================================
echo  启动网关: opencli gateway (opencode2api.exe)
echo ============================================
echo  服务端点 : http://127.0.0.1:8080/v1  (OpenAI 兼容, 后端 api_base 指向此处)
echo  管理台   : http://127.0.0.1:8081     (用户 admin)
echo  配置文件 : %~dp0config.json
echo  停止方式 : 关闭本窗口即停, 或双击 opencli_gateway_stop.bat
echo ============================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo.
    echo [检查] 端口 8080 : 运行中, 网关已在运行, 不重复启动。
    echo        如需重启, 先双击 opencli_gateway_stop.bat, 再运行本脚本。
    pause
    exit /b 0
)
echo.
echo [启动] 正在拉起网关进程 (冷启动约 12 秒, 运行日志如下)...
echo.
opencode2api.exe -config config.json
echo.
echo [提示] 网关进程已退出。若非主动关窗所致, 多为启动失败(常见: 端口 8080 被占用), 原因见上方日志。
pause
