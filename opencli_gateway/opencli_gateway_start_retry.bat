@echo off
chcp 936 >nul
rem opencli gateway 重试启动脚本 (启动壳) - 调用 opencli_gateway_start_retry.ps1
rem 解决 WARP 隧道间歇性建立失败, 自动重试最多 5 次 - OmniAgent 2026-11-18
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0opencli_gateway_start_retry.ps1"
