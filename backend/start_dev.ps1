# 开发后端启动器: watchfiles 热重载 + run_server.py 正式入口 — 小欧 2026-11-02
# 不用 uvicorn --reload: Windows 上 restart() 卡死在 self.process.join(), 首次改文件即永久失效(判定见 AGENTS.md)
# 用法: 双击 backend\start.bat, 或 powershell -ExecutionPolicy Bypass -File backend\start_dev.ps1
Set-Location -LiteralPath $PSScriptRoot
watchfiles --filter python --verbosity info -- 'python run_server.py --host 0.0.0.0 --port 8000' (Join-Path $PSScriptRoot 'app')
