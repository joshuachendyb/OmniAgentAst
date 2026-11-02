# 编辑历史: 2026-11-02 小欧 - 新增前端停止脚本: 先按 logs/frontend-dev.pid 结束整棵启动器进程树,
#   兜底按端口监听进程沿父链清掉 vite/npm 包装层 (隐藏窗口进程不可见, 无此脚本只能靠任务管理器逐个找)
param(
    [int]$Port = 5173
)

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root 'logs\frontend-dev.pid'
$killed  = @()

# 1) 首选: pid 文件记录的 launcher, /T 连子进程一起收掉
$launcherId = $null
if (Test-Path $pidFile) {
    $saved = (Get-Content $pidFile -Raw).Trim()
    if ($saved -match '^\d+$') { $launcherId = [int]$saved }
}
if ($launcherId -and (Get-Process -Id $launcherId -ErrorAction SilentlyContinue)) {
    & taskkill /PID $launcherId /T /F 2>&1 | Out-Null
    $killed += $launcherId
}

# 2) 兜底: pid 文件失效时按端口找监听进程, 沿父链上溯清掉 node.exe/cmd.exe 包装层
#    上溯遇非 node/cmd 即止 (不会误杀 explorer、终端或后端 uvicorn 的 python 进程)
$targets = @()
foreach ($c in (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)) {
    $cur = $c.OwningProcess
    while ($cur) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
        if (-not $p) { break }
        if ($p.Name -notin @('node.exe', 'cmd.exe')) { break }
        $targets += $cur
        $cur = $p.ParentProcessId
    }
}
foreach ($t in ($targets | Select-Object -Unique)) {
    if ($t -and (Get-Process -Id $t -ErrorAction SilentlyContinue)) {
        & taskkill /PID $t /T /F 2>&1 | Out-Null
        $killed += $t
    }
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue

if ($killed.Count -eq 0) {
    "前端未在运行 (:$Port)"
} else {
    "已停止前端: PID $((($killed | Select-Object -Unique) -join ', '))"
}
