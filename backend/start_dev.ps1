# 开发后端启动器: watchfiles 热重载 + run_server.py 正式入口 — 小欧 2026-11-02
# 原禁用 uvicorn --reload: Windows 上 restart() 走 os.kill(子进程, CTRL_C_EVENT), 子进程收不到即卡死在
#   basereload.py:98 self.process.join(); 首次改文件起热重载永久失效, 而 worker 照常应答(判定见 AGENTS.md)
# 用法: 双击 backend\start.bat → uvicorn --reload(默认); 双击 backend\start_watch.bat → watchfiles(原方案)
#       E2E 用 start_e2e.bat(固定 watch), 命令行传参 backend\start.bat watch 等效 start_watch.bat
# 2026-11-08 小欧 - 免手工装依赖: 解释器/uvicorn/watchfiles 三步自检, watchfiles 缺失则 pip 装一次;
#   一律经 python -m ... 起(不依赖 Scripts 目录是否在 PATH) — 小欧-2026-11-08
# 2026-11-08 小欧 - 增模式参数: 无参默认 uvicorn --reload(补 --forwarded-allow-ips 供其代理中间件用;
#   app 层注入仍缺——reload 子进程不跑 run_server.py, 启动会打一条该告警), watch 走 watchfiles — 小欧-2026-11-08
param(
    [Parameter(Position = 0)]
    [ValidateSet('uvicorn', 'watch', 'watchfiles')]
    [string]$Reloader = 'uvicorn'
)
Set-Location -LiteralPath $PSScriptRoot

$python = 'python'
$appDir = Join-Path $PSScriptRoot 'app'

if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    Write-Host '[start_dev] 未找到 python, 请先把 Python 加入 PATH' -ForegroundColor Red
    exit 1
}

# 缺 uvicorn 时重载器会反复拉起又崩溃(刷屏且难判读), 先一次性判死
& $python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[start_dev] 当前 python 缺 uvicorn, 请先执行: python -m pip install -r requirements.txt' -ForegroundColor Red
    exit 1
}

if ($Reloader -eq 'uvicorn') {
    Write-Host '[start_dev] 重载方式: uvicorn --reload (监视 app)' -ForegroundColor Cyan
    & $python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000 --forwarded-allow-ips 127.0.0.1,::1
    exit $LASTEXITCODE
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

Write-Host "[start_dev] 重载方式: watchfiles (监视 $appDir)" -ForegroundColor Cyan
& $python -m watchfiles --filter python --verbosity info -- "$python run_server.py --host 0.0.0.0 --port 8000" $appDir
exit $LASTEXITCODE
