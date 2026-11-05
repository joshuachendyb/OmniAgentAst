@echo off
rem stop.bat - 停止 8199 端口上的网关进程（只动监听 8199 的 PID, 不碰宿主/下游池）
rem 下游 opencode-cli 池进程属网关子进程树, 随网关退出由 cli_manager.shutdown 清理
rem 偏差 FIX C（2026-11-05 小欧, 出处 9.1.10）: 文档版 ^ 续行在 cmd 下断行, 改单行
rem 编写人: 小欧    2026-11-05
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8199 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force } } else { Write-Host '网关(8199)未在运行' }"
