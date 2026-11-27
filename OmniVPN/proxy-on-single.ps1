# proxy-on-single.ps1 — 一键开代理(一级模式): 启动 mihomo(用 config-single.yaml) + 设系统代理 + 验证出口
# 编写人: 商量    日期: 2026-11-28    版本: v1.1
# 用途: 与二级 proxy-on.ps1 并存互斥。一级模式 = 出口节点直连裸线, 无二级池(INDONESIA_POOL/EXIT_POOL)。
#       用 mihomo\config-single.yaml(-f 指定) 启动, 独立端口 7892/9092, 与二级 7890/9090 并存不冲突。
# 用法:
#   powershell -ExecutionPolicy Bypass -File proxy-on-single.ps1            # 一级 mihomo:7892
#   powershell -ExecutionPolicy Bypass -File proxy-on-single.ps1 -Port 7892 -NoStart
# 参数:
#   -Port     本地代理端口(一级 mihomo=7892)
#   -NoStart  不启动 mihomo(仅设系统代理)

param(
    [int]$Port = 7892,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$mihomoExe = Join-Path $PSScriptRoot 'mihomo\mihomo-slim.exe'
$mihomoDir = Join-Path $PSScriptRoot 'mihomo-single'
$singleCfg = Join-Path $mihomoDir 'config.yaml'
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$ctrl = "http://127.0.0.1:9092"   # 一级 mihomo 外部控制器(切换节点用)

"============================================================"
"proxy-on-single v1.0  一键开代理(一级模式)   $stamp"
"============================================================"
""

function Test-Port([int]$p) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    return [bool]$c
}

# 1. 起 mihomo(端口没在听才起; 用 config-single.yaml 一级配置)
'[1] 启动内核 (mihomo, 一级配置 config-single.yaml)'
if (-not $NoStart -and -not (Test-Port $Port)) {
    if (-not (Test-Path $mihomoExe)) { throw "[错误] 未找到内核程序: $mihomoExe" }
    if (-not (Test-Path $singleCfg)) { throw "[错误] 未找到一级配置: $singleCfg" }
    # 先停旧: 检测到一级端口 7892 被占则只停掉该端口的一级实例(不影响二级 7890/9090)
    $old = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($old) {
        '    检测到一级端口 ' + $Port + ' 已被占用, 停止旧一级实例...'
        $old | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep 2
    }
    Start-Process $mihomoExe -ArgumentList '-d', $mihomoDir, '-f', $singleCfg -WindowStyle Hidden
    '    内核进程   : 已启动(一级配置), 等待端口就绪...'
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep 1
        if (Test-Port $Port) { break }
    }
} else {
    '    内核进程   : 已在运行 (跳过启动)'
}
if (-not (Test-Port $Port)) { throw "[错误] 代理端口 $Port 未监听: 内核进程未启动, 手动执行 mihomo\mihomo-slim.exe -d mihomo-single -f mihomo-single\config.yaml 查看报错" }
"    代理端口 $Port : 运行中"
""

# 2. 设系统代理(只对认系统代理的程序生效)
'[2] 系统代理 (WinInet)'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
Set-ItemProperty $key -Name ProxyEnable -Value 1
Set-ItemProperty $key -Name ProxyServer -Value "127.0.0.1:$Port"
Set-ItemProperty $key -Name ProxyOverride -Value '<local>;localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.2*;172.30.*;172.31.*;192.168.*'
$sig = @'
using System;
using System.Runtime.InteropServices;
public class WinInet {
    [DllImport("wininet.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
}
'@
if (-not ('WinInet' -as [type])) { Add-Type -TypeDefinition $sig }
[WinInet]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
[WinInet]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null
"    状态       : 启用 -> 127.0.0.1:$Port `(仅本机地址绕过`)"
""

# 3. 池子清单(离线读 mihomo\config-single.yaml + log\buckets.tsv, 不联网, 秒出)
'[3] 节点池 (一级模式: 单级池, 节点数/桶数)'
$stats = Join-Path $PSScriptRoot 'nodepool\_bucket_stats.py'
if (Test-Path $stats) { python $stats $singleCfg --by-node } else { '    桶统计脚本缺失: ' + $stats }
""

# 4. 代理链路(读 9092 运行态, 一级直出; 控制器不可达时降级提示)
'[4] 代理链路 (一级直出 · 读 9092 运行态)'
function Get-Px([string]$name) {
    try { Invoke-RestMethod "http://127.0.0.1:9092/proxies/$name" -TimeoutSec 2 } catch { $null }
}
$px = Get-Px 'PROXY'
if ($null -eq $px) {
    '    控制器 9092 不可达, 跳过链路展示 (不影响代理本身)'
} else {
    "    本机程序 ──系统代理──> 127.0.0.1:$Port (mihomo)"
    "    当前一级直出 (PROXY 选中 = $($px.now)), 未串联二级出口"
}
""

# 5. 验证出口(直连 vs 走代理, 对照着看才看得出生效没)
'[5] 出口对照 (Cloudflare trace, 3~8 秒/项, 请勿中途关窗)'
$rot = Join-Path $PSScriptRoot 'exit_rotator.py'
'    直连出口   : (裸线, 不经 mihomo; 恒为 loc=CN 属正常)'
python $rot --verify | ForEach-Object { "    $_" }
'    代理出口   : (经 mihomo -> 节点, 看这一项)'
$proxyOut = python $rot --verify --proxy "http://127.0.0.1:$Port"
$proxyOut | ForEach-Object { "    $_" }
if (($proxyOut -join "`n") -match '当前出口: \? \(\?\)') {
    '    [提示] 选中节点失联(出口 ? (?)), 自动切换到下一个存活节点'
    python $rot --target mihomo --url $ctrl --group PROXY --wait --proxy http://127.0.0.1:$Port
    '    复验出口   :'
    python $rot --verify --proxy "http://127.0.0.1:$Port" | ForEach-Object { "    $_" }
}
""

# 5.5 启动时自动避开最近桶(记住上次退出的桶, 用新桶启动)
'[5.5] 启动时避开最近桶 (读 bucket_history.json, 当前桶在历史里就换新桶)'
$histFile = Join-Path $PSScriptRoot 'log\bucket_history.json'
if (Test-Path $histFile) {
    $hist = Get-Content $histFile -Encoding UTF8 | ConvertFrom-Json
    $recentKeys = $hist | ForEach-Object { $_.key }
    $currentOut = python $rot --verify --proxy "http://127.0.0.1:$Port"
    $m = ($currentOut -join "`n") | Select-String -Pattern '(\d+\.\d+\.\d+\.\d+/\d+).*?loc=(\w+)'
    if ($m.Matches.Count -gt 0) {
        $currentBucket = "$($m.Matches[0].Groups[1].Value)|$($m.Matches[0].Groups[2].Value)"
        if ($recentKeys -contains $currentBucket) {
            "    当前出口桶 $currentBucket 在最近用过列表里, 自动换新桶..."
            python $rot --target mihomo --url $ctrl --group PROXY --wait --proxy http://127.0.0.1:$Port
            '    复验出口   :'
            python $rot --verify --proxy "http://127.0.0.1:$Port" | ForEach-Object { "    $_" }
        } else {
            "    当前出口桶 $currentBucket 不在最近用过列表里, 无需换桶"
        }
    }
}
""

# 6. 换桶备忘
'[6] 换桶操作 (撞 429 配额时执行)'
"    python `"$rot`" --target mihomo --group PROXY --wait --proxy http://127.0.0.1:$Port"
