# opencli gateway 重试启动脚本 (PowerShell 核心)
# 解决 WARP 隧道间歇性建立失败 (ECONNREFUSED / context deadline exceeded)
# 逻辑: 启动 opencode2api.exe, 轮询 8080 是否监听; 失败(进程退出/卡住)则自动重试, 最多 5 次
# 不改动原 opencli_gateway_start.bat, 本脚本为独立重试版 - OmniAgent 2026-11-18
$ErrorActionPreference = 'SilentlyContinue'

Set-Location -Path $PSScriptRoot

$MAX = 5
$WAIT_SEC = 30
$EXE = Join-Path $PSScriptRoot 'opencode2api.exe'
$CONFIG = Join-Path $PSScriptRoot 'config.json'

function Test-GwPort {
    return [bool](Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
}

function Test-GwProc {
    return [bool](Get-Process -Name 'opencode2api' -ErrorAction SilentlyContinue)
}

Write-Host '============================================'
Write-Host '  OmniAgent OpenCode Gateway 启动(带重试)'
Write-Host '  服务端点 : http://127.0.0.1:8080/v1'
Write-Host '  管理台   : http://127.0.0.1:8081'
Write-Host ('  配置文件 : ' + $CONFIG)
Write-Host ('  重试上限 : ' + $MAX + ' 次')
Write-Host '============================================'
Write-Host ''

if (-not (Test-Path $EXE)) {
    Write-Host '[FAIL] 未找到 opencode2api.exe' -ForegroundColor Red
    Read-Host '按回车退出'
    exit 1
}

for ($attempt = 1; $attempt -le $MAX; $attempt++) {
    Write-Host ''
    Write-Host ('[第 ' + $attempt + '/' + $MAX + ' 次尝试] 正在启动网关...')

    if (Test-GwPort) {
        Write-Host '[OK] 网关已在运行 (端口 8080 已监听), 无需重复启动。' -ForegroundColor Green
        break
    }

    # 启动网关 (新窗口, 不阻塞本脚本)
    Start-Process -FilePath $EXE -ArgumentList '-config', (Split-Path -Leaf $CONFIG) -WorkingDirectory $PSScriptRoot

    # 轮询等待 8080 监听
    $t = 0
    $ready = $false
    while ($t -lt $WAIT_SEC) {
        Start-Sleep -Seconds 1
        $t++
        if (Test-GwPort) { $ready = $true; break }
        if (-not (Test-GwProc)) { break }  # 进程已退出 (WARP 初始化失败)
    }

    if ($ready) {
        Write-Host ''
        Write-Host '============================================' -ForegroundColor Green
        Write-Host '  [OK] 网关启动成功!' -ForegroundColor Green
        Write-Host '  端口 8080 已监听, WARP 出口就绪。' -ForegroundColor Green
        Write-Host '  服务: http://127.0.0.1:8080/v1  管理台: http://127.0.0.1:8081' -ForegroundColor Green
        Write-Host '  网关已在独立窗口运行, 关闭本窗口不影响网关。' -ForegroundColor Green
        Write-Host '============================================' -ForegroundColor Green
        Read-Host '按回车退出'
        exit 0
    }

    # 失败: 进程退出或超时卡住
    $reason = if (-not (Test-GwProc)) { '进程已退出 (可能是 WARP 隧道建立超时)' } else { ('等待 ' + $WAIT_SEC + ' 秒仍未监听 8080 (进程卡住)') }
    Write-Host ('[第 ' + $attempt + ' 次失败] ' + $reason + ', 准备重试...') -ForegroundColor Yellow
    Get-Process -Name 'opencode2api' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Red
Write-Host '  [FAIL] 已重试 5 次仍失败。' -ForegroundColor Red
Write-Host '  可能原因: Cloudflare 侧抖动 / UDP 2408 不通 / 本机无全局 IPv6' -ForegroundColor Red
Write-Host '  临时方案: 改 config.json 的 warp.enabled=false 回裸线直连' -ForegroundColor Red
Write-Host '============================================' -ForegroundColor Red
Read-Host '按回车退出'
exit 1
