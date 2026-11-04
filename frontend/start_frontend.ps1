# 编辑历史: 2026-11-02 小欧 - 新增前端常驻启动器: 隐藏窗口独立控制台 + 端口就绪轮询 + 健康校验 + pid 落盘,
#   根治"关掉控制台窗口/终端会话结束 → 控制台进程组整树被杀 → 前端无声消失"。用法: 双击 start_frontend.bat
# 链路: 前端 :5173 --proxy /api--> 后端 :8000 (见 vite.config.ts server.proxy)
param(
    [int]$Port = 5173,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir  = Join-Path $root 'logs'
$outLog  = Join-Path $logDir 'frontend-dev.log'
$pidFile = Join-Path $logDir 'frontend-dev.pid'

# 1) 已监听则直接报状态, 不重复起第二份 (vite 遇端口占用会漂到 5174, 反而更难查)
$conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    "前端已在运行: http://localhost:$Port (PID $($conn.OwningProcess))"
    exit 0
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 2) 隐藏窗口启动: Start-Process 新建独立控制台, 不挂在本终端进程组上, 关闭终端的 CTRL_CLOSE_EVENT 传不下来
$launcher = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/c', "npm run dev > `"$outLog`" 2>&1" `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru
Set-Content -Path $pidFile -Value $launcher.Id -Encoding ASCII

# 3) 轮询等端口就绪 (冷启动首次预构建 antd/react 可能 20~40s)
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 800
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { break }
    if ($launcher.HasExited) { break }
}

if (-not $conn) {
    "启动失败: :$Port 未监听 (launcher PID $($launcher.Id), HasExited=$($launcher.HasExited))"
    if (Test-Path $outLog) { '--- 日志尾部 ---'; Get-Content $outLog -Tail 30 }
    exit 1
}

# 4) 健康校验: 页面链路 + 后端代理链路, 两条都通才算真的起来了
$page  = Invoke-WebRequest -Uri "http://localhost:$Port/" -TimeoutSec 20 -UseBasicParsing
$proxy = Invoke-WebRequest -Uri "http://localhost:$Port/api/v1/health" -TimeoutSec 20 -UseBasicParsing
'启动成功'
"  页面  http://localhost:$Port  HTTP $($page.StatusCode)"
"  代理  /api/v1/health -> 后端 :8000  HTTP $($proxy.StatusCode)"
"  进程  vite PID $($conn.OwningProcess) / launcher PID $($launcher.Id)"
"  日志  $outLog"
