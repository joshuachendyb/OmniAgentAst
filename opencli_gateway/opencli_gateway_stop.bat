@echo off
chcp 936 >nul
rem opencli gateway 停止壳: 调用 opencli_gateway_stop.ps1 按端口 8080/8081 结束监听进程 - xiaoou 2026-11-09
rem 更新: 2026-11-12 xiaoou 更名 opencli_gateway_stop.bat(母本目录前缀, 名实相符); 停止逻辑移入 opencli_gateway_stop.ps1(cmd 多行续行不可靠, 依 OmniVPN bat->ps1 惯例); 输出文案人类化: 逐进程列端口/角色/pid, 结束后复检端口, 结论明确(已停止/未在运行/未完全停止)
echo ============================================
echo  停止网关: opencli gateway
echo ============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0opencli_gateway_stop.ps1"
echo.
pause
