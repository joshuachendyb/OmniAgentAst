# _start_single_hidden.ps1 — 隐藏窗口启动一级 mihomo(独立目录 mihomo-single)
# 编写人: 商量  日期: 2026-11-28
# 用途: 供 schtasks 计划任务调用, 启动的 mihomo 由任务计划程序托管, 不受 shell 会话回收影响
$exe = 'F:\OmniAgentAs-01\OmniVPN\mihomo\mihomo-slim.exe'
$dir = 'F:\OmniAgentAs-01\OmniVPN\mihomo-single'
$cfg = 'F:\OmniAgentAs-01\OmniVPN\mihomo-single\config.yaml'
Start-Process $exe -ArgumentList '-d', $dir, '-f', $cfg -WindowStyle Hidden
