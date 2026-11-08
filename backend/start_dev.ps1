# 开发后端启动器: watchfiles 热重载 + run_server.py 正式入口 — 小欧 2026-11-02
# 不用 uvicorn --reload: Windows 上 restart() 走 os.kill(子进程, CTRL_C_EVENT), 子进程收不到即卡死在
#   basereload.py:98 self.process.join(); 首次改文件起热重载永久失效, 而 worker 照常应答(判定见 AGENTS.md)
# 用法: 双击 backend\start.bat, 或 powershell -ExecutionPolicy Bypass -File backend\start_dev.ps1
# 2026-11-08 小欧 - 免手工装依赖: 启动前三步自检(解释器/uvicorn/watchfiles), watchfiles 缺失则 pip 装一次;
#   一律经 python -m watchfiles 起(不依赖 Scripts 目录是否在 PATH), 重载器与入口/端口/监视目录保持原样 — 小欧-2026-11-08
Set-Location -LiteralPath $PSScriptRoot

$python = 'python'
$appDir = Join-Path $PSScriptRoot 'app'

if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    Write-Host '[start_dev] 未找到 python, 请先把 Python 加入 PATH' -ForegroundColor Red
    exit 1
}

# 缺 uvicorn 时 watchfiles 会反复拉起又崩溃(刷屏且难判读), 先一次性判死
& $python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[start_dev] 当前 python 缺 uvicorn, 请先执行: python -m pip install -r requirements.txt' -ForegroundColor Red
    exit 1
}

& $python -c "import watchfiles" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[start_dev] 未安装 watchfiles(热重载依赖), 正在安装...' -ForegroundColor Yellow
    & $python -m pip install "watchfiles>=0.21"
    & $python -c "import watchfiles" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[start_dev] watchfiles 安装失败。离线环境请手工安装后重试: python -m pip install watchfiles' -ForegroundColor Red
        exit 1
    }
}

Write-Host "[start_dev] 热重载监视目录: $appDir" -ForegroundColor Cyan
& $python -m watchfiles --filter python --verbosity info -- "$python run_server.py --host 0.0.0.0 --port 8000" $appDir
exit $LASTEXITCODE
