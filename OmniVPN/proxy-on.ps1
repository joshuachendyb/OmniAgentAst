# proxy-on.ps1 — 一键开代理(启动 mihomo + 设系统代理 + 验证出口)
# 编写人: 小欧    日期: 2026-11-11    版本: v2.6    更新时间: 2026-11-23 18:33:42
# 更新: v1.1 小欧 2026-11-11 出口查询各需 3~8 秒, 加提示防止误判卡死关窗(实测踩过)
# 更新: v1.2 小欧 2026-11-12 内核优先用自编精简版 mihomo-slim.exe, 缺文件回落官方原版
# 更新: v2.0 小欧 2026-11-12 目录迁移 OmniVPN\: 内核/配置/脚本全在本目录下自洽, 不再依赖 vpn-trial\ 与 hooks\
# 更新: v2.1 小欧 2026-11-12 输出文案统一重排: 状态措辞规范化(运行中/启用), 分节标题对齐
# 更新: v2.2 小欧 2026-11-12 用途注释中性化: 删外部工具(skyline)提法, 改为独立 VPN 表述
# 更新: v2.3 小欧 2026-11-21 启动成功后加打节点池清单(节点数/桶数/逐节点所属桶, 离线读配置与桶快照);
#                             顺手修掉换桶命令备忘把 "python (Join-Path ...)" 当纯文本打印的老问题
# 更新: v2.4 小欧 2026-11-22 出口验证发现选中节点失联(代理出口 ? (?))时, 自动切换到下一个存活节点并复验
# 更新: v2.5 小欧 2026-11-22 输出改为 exit_probe 风格 [1]~[5] 阶段编号, 启动顺序清晰, 文案精简
# 更新: v2.6 小欧 2026-11-23 新增 [4] 代理链路: 读 9090 渲染两级串联与当前选中节点, 原出口对照/换桶备忘顺延为 [5]/[6]
# 用途: 接管本机上网出口(流量经节点出去); 只改「系统代理」与本地进程, 不动路由/网卡
# 用法:
#   powershell -ExecutionPolicy Bypass -File proxy-on.ps1            # 默认 mihomo:7890
#   powershell -ExecutionPolicy Bypass -File proxy-on.ps1 -Port 10808 -NoStart
# 参数:
#   -Port     本地代理端口(mihomo=7890, v2rayN SOCKS=10808)
#   -NoStart  不启动 mihomo(v2rayN 等已在跑的程序用)

param(
    [int]$Port = 7890,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$mihomoExe = Join-Path $PSScriptRoot 'mihomo\mihomo-slim.exe'
$mihomoDir = Join-Path $PSScriptRoot 'mihomo'
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"============================================================"
"proxy-on v2.6  一键开代理   $stamp"
"============================================================"
""

function Test-Port([int]$p) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    return [bool]$c
}

# 1. 起 mihomo(端口没在听才起)
'[1] 启动内核 (mihomo)'
if (-not $NoStart -and -not (Test-Port $Port)) {
    if (-not (Test-Path $mihomoExe)) { throw "[错误] 未找到内核程序: $mihomoExe" }
    Start-Process $mihomoExe -ArgumentList '-d', $mihomoDir -WindowStyle Hidden
    '    内核进程   : 已启动, 等待端口就绪...'
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep 1
        if (Test-Port $Port) { break }
    }
} else {
    '    内核进程   : 已在运行 (跳过启动)'
}
if (-not (Test-Port $Port)) { throw "[错误] 代理端口 $Port 未监听: 内核进程未启动, 手动执行 mihomo\mihomo-slim.exe -d mihomo 查看报错" }
"    代理端口 $Port : 运行中"
""

# 2. 设系统代理(只对认系统代理的程序生效)
'[2] 系统代理 (WinInet)'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
Set-ItemProperty $key -Name ProxyEnable -Value 1
Set-ItemProperty $key -Name ProxyServer -Value "127.0.0.1:$Port"
Set-ItemProperty $key -Name ProxyOverride -Value '<local>;localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.2*;172.30.*;172.31.*;192.168.*'
# 通知系统立即生效(否则要等程序重新读取)
$sig = @'
using System;
using System.Runtime.InteropServices;
public class WinInet {
    [DllImport("wininet.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
}
'@
if (-not ('WinInet' -as [type])) { Add-Type -TypeDefinition $sig }
[WinInet]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null  # INTERNET_OPTION_SETTINGS_CHANGED
[WinInet]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null  # INTERNET_OPTION_REFRESH
"    状态       : 启用 -> 127.0.0.1:$Port `(仅本机地址绕过`)"
""

# 3. 池子清单(离线读 mihomo\config.yaml + log\buckets.tsv, 不联网, 秒出)
'[3] 节点池 (当前生效: 节点数/桶数/逐节点所属桶)'
$stats = Join-Path $PSScriptRoot 'nodepool\_bucket_stats.py'
if (Test-Path $stats) { python $stats --by-node } else { '    桶统计脚本缺失: ' + $stats }
""

# 4. 代理链路(读 9090 运行态, 渲染两级串联与当前选中; 控制器不可达时降级提示)
'[4] 代理链路 (两级串联 · 读 9090 运行态)'
function Get-Px([string]$name) {
    try { Invoke-RestMethod "http://127.0.0.1:9090/proxies/$name" -TimeoutSec 2 } catch { $null }
}
$px = Get-Px 'PROXY'
if ($null -eq $px) {
    '    控制器 9090 不可达, 跳过链路展示 (不影响代理本身)'
} elseif ($px.now -eq 'DIRECT' -or $px.now -eq 'INDONESIA_POOL') {
    "    本机程序 ──系统代理──> 127.0.0.1:$Port (mihomo)"
    "    当前一级直出 (PROXY 选中 = $($px.now)), 未串联二级出口"
} elseif ($px.now -eq 'EXIT_POOL' -or $px.now -eq 'Auto') {
    $lvl1 = Get-Px 'INDONESIA_POOL'
    $lvl2 = Get-Px $px.now
    $node = if ($lvl2) { Get-Px $lvl2.now } else { $null }
    $dp = if ($node) { $node.'dialer-proxy' } else { '' }
    $via = if ($dp -eq 'INDONESIA_POOL') { '经一级中转' } elseif ($dp) { "经 $dp 中转" } else { '直连(未设 dialer-proxy)' }
    $n1 = if ($lvl1) { @($lvl1.all).Count } else { '?' }
    $n2 = if ($lvl2) { @($lvl2.all).Count } else { '?' }
    $c1 = if ($lvl1) { $lvl1.now } else { '?' }
    $c2 = if ($lvl2) { $lvl2.now } else { '?' }
    "    本机程序 ──系统代理──> 127.0.0.1:$Port (mihomo)"
    '                              │'
    "    一级·前置跳板 : INDONESIA_POOL [$c1]  印尼 ss ×$n1  (直连裸线)"
    '                              │ dialer-proxy'
    "    二级·最终出口 : $($px.now) [$c2]  出口节点 ×$n2  ($via)"
    '                              │'
    '                          目标网站   (出口 IP 见下段对照)'
} else {
    "    PROXY 选中了未识别的组: $($px.now), 跳过链路展示"
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
    python $rot --target mihomo --group PROXY --wait --proxy http://127.0.0.1:$Port
    '    复验出口   :'
    python $rot --verify --proxy "http://127.0.0.1:$Port" | ForEach-Object { "    $_" }
}
""

# 6. 换桶备忘
'[6] 换桶操作 (撞 429 配额时执行)'
"    python `"$rot`" --target mihomo --group PROXY --wait --proxy http://127.0.0.1:$Port"
