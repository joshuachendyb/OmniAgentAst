# 开发后端启动器: watchfiles 热重载 + run_server.py 正式入口 — 小欧 2026-11-02
# 原禁用 uvicorn --reload: Windows 上 restart() 走 os.kill(子进程, CTRL_C_EVENT), 子进程收不到即卡死在
#   basereload.py:98 self.process.join(); 首次改文件起热重载永久失效, 而 worker 照常应答(判定见 AGENTS.md)
# 用法: 双击 backend\start_uvicorn.bat → uvicorn --reload(默认); 双击 backend\start_watch.bat → watchfiles(原方案)
#       E2E 用 start_e2e.bat(固定 watch), 命令行传参 backend\start_uvicorn.bat watch 等效 start_watch.bat
# 2026-11-08 小欧 - 免手工装依赖: 解释器/uvicorn/watchfiles 三步自检, watchfiles 缺失则 pip 装一次;
#   一律经 python -m ... 起(不依赖 Scripts 目录是否在 PATH) — 小欧-2026-11-08
# 2026-11-08 小欧 - 增模式参数: 无参默认 uvicorn --reload(补 --forwarded-allow-ips 供其代理中间件用;
#   app 层注入仍缺——reload 子进程不跑 run_server.py, 启动会打一条该告警), watch 走 watchfiles — 小欧-2026-11-08
# 2026-11-08 小欧 - 开发端口 8000→8100: 取 env BACKEND_PORT(缺省 8100), 两种重载器同源;
#   8000 上有 OpenCode 桌面版内置 vLLM provider 每 30s 探 /v1/models 刷 404。打包链 run_server.py 不动 — 小欧-2026-11-08
# 2026-11-08 小欧 - uvicorn 分支补 --log-level warning: 裸 uvicorn 默认 access 日志打控制台, 与
#   run_server.py 的"只落盘不挂 console"对齐(刷屏无排障价值, 且同步 stdout 有冻结事件循环风险) — 小欧-2026-11-08
# 2026-11-08 小欧 - 启动前按端口清残留树: 关窗不级联清 uvicorn --reload 子树(detached worker),
#   残留实例 SO_REUSEADDR 抢同一端口致请求随机分发; 只按端口清, 其它进程不动 — 小欧-2026-11-08
# 2026-11-28 小欧 - 清残留补上溯重载器父链: 只杀监听者会留下 watchfiles 父进程, 子进程退出后它立刻重生
#   新子进程抢同一端口(实测: 杀监听者后旧 watchfiles 8s 内拉起新子进程并重新占住 8100), 新旧两个守护
#   进程并存即回到本段要消除的随机分发; 改为先杀守护(仅 cmdline 命中 watchfiles/start_dev/uvicorn --reload 的父链)再杀 worker
# 2026-11-28 小欧 - 增崩溃自愈看护: watchfiles 只在文件变更时重启子进程, 子进程崩溃后它空转不退, 服务永久失联;
#   外层按端口探活(宽限 60s, 连续 10s 无监听)重起重载链, 重载链自身退出按 3s 退避重起
# 2026-11-28 小欧 - 看护误杀修复: 热重载间隙端口短暂消失(导入/建库慢时>10s)会被误判"已崩"整链重启;
#   探活加"watchfiles 有存活子进程=链在启动/重载中"判据, 有子进程只重置 miss 不杀。
#   同批: 端口 cmdline 匹配加边界(正则 \s|$ 锚定), 杜绝 --port 8100 误杀 --port 81000 进程
param(
    [Parameter(Position = 0)]
    [ValidateSet('uvicorn', 'watch', 'watchfiles')]
    [string]$Reloader = 'uvicorn'
)
Set-Location -LiteralPath $PSScriptRoot

$python = 'python'
$appDir = Join-Path $PSScriptRoot 'app'
# 端口单源: BACKEND_PORT 覆盖, 默认 8100(避开 8000 —— OpenCode 桌面版内置 vLLM provider 每 30s 探 127.0.0.1:8000/v1/models)
$backendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8100 }

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

# 启动前按端口清残留树(上方注释): 监听者 + 其重载器父链 + direct 子进程, 不碰其它进程
# 2026-11-28 小欧 - 抽成函数: 首启前与看护重起前共用一处, 避免"看护重起时残留监听把新子进程顶掉"
function Clear-StalePort {
    param([int]$Port, [string]$AppDir)
    $workers = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    # 2026-11-28 小欧 - 无监听的孤儿重载链: 子进程已死但 watchfiles 还活着, 下次文件变更它会拉起新子进程
    #   抢同一端口(实测 26508 形态); 只按端口清树看不见它, 故按 cmdline 精确匹配本仓 app 目录 + 本端口
    # 2026-11-28 小欧 - 端口匹配加边界: 无边界 Contains 会把 --port 81000 误当 --port 8100 命中(短端口
    #   误杀长端口进程), 改正则 \s|$ 锚定端口参数结尾
    $portPattern = "--port {0}(\s|$)" -f [regex]::Escape($Port)
    $reloaders = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match 'watchfiles' -and
            $_.CommandLine.Contains($AppDir) -and $_.CommandLine -match $portPattern
        } | Select-Object -ExpandProperty ProcessId)
    if (-not $workers.Count -and -not $reloaders.Count) { return }
    foreach ($ownerPid in $workers) {
        $workers += @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ownerPid" |
            Select-Object -ExpandProperty ProcessId)
        $cursor = $ownerPid
        for ($hop = 0; $hop -lt 5; $hop++) {
            $self = Get-CimInstance Win32_Process -Filter "ProcessId=$cursor" -ErrorAction SilentlyContinue
            if (-not $self) { break }
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($self.ParentProcessId)" -ErrorAction SilentlyContinue
            # 上溯到本进程即止: 本脚本自身 cmdline 也含 start_dev.ps1, 继续走会把自己杀掉
            if (-not $parent -or $parent.ProcessId -eq $PID) { break }
            if ($parent.CommandLine -notmatch 'watchfiles|start_dev\.ps1|uvicorn.*--reload') { break }
            $reloaders += $parent.ProcessId
            $cursor = $parent.ProcessId
        }
    }
    $reloaders = @($reloaders | Select-Object -Unique | Where-Object { $_ -ne $PID })
    $workers = @($workers | Select-Object -Unique | Where-Object { $reloaders -notcontains $_ -and $_ -ne $PID })
    Write-Host "[start_dev] 端口 $Port 有残留(守护PID $($reloaders -join ','); 工作PID $($workers -join ',')), 已清树后重起" -ForegroundColor Yellow
    $reloaders | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 800
    $workers | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

Clear-StalePort -Port $backendPort -AppDir $appDir

if ($Reloader -eq 'uvicorn') {
    Write-Host "[start_dev] 重载方式: uvicorn --reload (监视 app, 端口 $backendPort)" -ForegroundColor Cyan
    & $python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port $backendPort --forwarded-allow-ips 127.0.0.1,::1 --log-level warning
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

Write-Host "[start_dev] 重载方式: watchfiles (监视 $appDir, 端口 $backendPort)" -ForegroundColor Cyan
# 2026-11-28 小欧 - 崩溃自愈看护: watchfiles 只在"文件变更"时重启子进程(run.py arun_process 的
#   stop/start 全在 awatch 循环内), 子进程自行退出后它只空转等待, 服务永久失联且不再有任何日志。
#   实测: 杀掉 run_server 后 30s 无监听、watchfiles 进程仍活。故在它外面加一层端口看护:
#   启动宽限 60s(导入/建库慢), 之后连续 2 次(10s)探不到监听即判定子进程已崩, 清树后整体重起重载链。
#   进程句柄不用 Start-Process: ①变量名 $reloader 与脚本参数 $Reloader 大小写不敏感同名, 赋值会撞
#   ValidateSet; ②-ArgumentList 按空格重拼, 会把 "python run_server.py ..." 拆散。改用 ProcessStartInfo 精确控制
$watchCmd = "$python run_server.py --host 0.0.0.0 --port $backendPort"
while ($true) {
    Clear-StalePort -Port $backendPort -AppDir $appDir
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = "-m watchfiles --filter python --verbosity info -- ""$watchCmd"" ""$appDir"""
    $psi.WorkingDirectory = $PSScriptRoot
    $psi.UseShellExecute = $false
    $wfProc = [System.Diagnostics.Process]::Start($psi)
    $graceUntil = (Get-Date).AddSeconds(60)
    $miss = 0
    while (-not $wfProc.HasExited) {
        Start-Sleep -Seconds 5
        if ($wfProc.HasExited) { break }
        if ((Get-Date) -lt $graceUntil) { continue }
        if (Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue) {
            $miss = 0
        } else {
            # 2026-11-28 小欧 - 误杀健康重载修复: 热重载间隙(先杀旧子进程再起新子进程)端口短暂消失,
            #   导入/建库慢时超 10s 即被误判"已崩"整链重启, 服务无谓被打断; watchfiles 仍有存活子进程
            #   (run_server 在启动中)说明链是活的, 只是在重载——重置 miss 等它起来, 不杀。
            $childAlive = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($wfProc.Id)" -ErrorAction SilentlyContinue).Count -gt 0
            if ($childAlive) { $miss = 0; continue }
            $miss++
            if ($miss -ge 2) {
                Write-Host "[start_dev] 端口 $backendPort 连续 $($miss * 5)s 无监听且重载链无子进程(已崩, watchfiles 不会自愈), 重起重载链" -ForegroundColor Yellow
                Stop-Process -Id $wfProc.Id -Force -ErrorAction SilentlyContinue
                break
            }
        }
    }
    $exitCode = 'n/a'
    try { $wfProc.WaitForExit(3000) | Out-Null; $exitCode = $wfProc.ExitCode } catch { }
    Write-Host "[start_dev] 重载链退出(code=$exitCode), 3s 后重起" -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}
