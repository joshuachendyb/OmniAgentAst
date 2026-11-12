# proxy-on.ps1 — 一键开代理(启动 mihomo + 设系统代理 + 验证出口)
# 编写人: 小欧    日期: 2026-11-11    版本: v2.0    更新时间: 2026-11-12 01:20:00
# 更新: v1.1 小欧 2026-11-11 出口查询各需 3~8 秒, 加提示防止误判卡死关窗(实测踩过)
# 更新: v1.2 小欧 2026-11-12 内核优先用自编精简版 mihomo-slim.exe, 缺文件回落官方原版
# 更新: v2.0 小欧 2026-11-12 目录迁移 OmniVPN\: 内核/配置/脚本全在本目录下自洽, 不再依赖 vpn-trial\ 与 hooks\
# 更新: v2.1 小欧 2026-11-12 输出文案统一重排: 状态措辞规范化(运行中/启用), 分节标题对齐
# 更新: v2.2 小欧 2026-11-12 用途注释中性化: 删外部工具(skyline)提法, 改为独立 VPN 表述
# 用途: 接管本机上网出口(流量经节点出去); 只改「系统代理」与本地进程, 不动路由/网卡
# 用法:
#   powershell -ExecutionPolicy Bypass -File hooks\proxy-on.ps1            # 默认 mihomo:7890
#   powershell -ExecutionPolicy Bypass -File hooks\proxy-on.ps1 -Port 10808 -NoStart
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

function Test-Port([int]$p) {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    return [bool]$c
}

# 1. 起 mihomo(端口没在听才起)
if (-not $NoStart -and -not (Test-Port $Port)) {
    if (-not (Test-Path $mihomoExe)) { throw "[错误] 未找到内核程序: $mihomoExe" }
    Start-Process $mihomoExe -ArgumentList '-d', $mihomoDir -WindowStyle Hidden
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep 1
        if (Test-Port $Port) { break }
    }
}
if (-not (Test-Port $Port)) { throw "[错误] 代理端口 $Port 未监听: 内核进程未启动, 手动执行 mihomo\mihomo-slim.exe -d mihomo 查看报错" }
"[OK] 代理端口 $Port : 运行中"

# 2. 设系统代理(只对认系统代理的程序生效)
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
"[OK] 系统代理: 启用 -> 127.0.0.1:$Port (仅本机地址绕过)"

# 3. 验证出口(直连 vs 走代理, 对照着看才看得出生效没)
"---- 出口验证 (Cloudflare trace, 每项 3~8 秒, 请勿中途关窗) ----"
"-- 直连出口 (裸线, 不经 mihomo; 恒为 loc=CN 属正常) --"
python (Join-Path $PSScriptRoot 'exit_rotator.py') --verify
"-- 代理出口 (经 mihomo -> 节点, 看这一项) --"
python (Join-Path $PSScriptRoot 'exit_rotator.py') --verify --proxy "http://127.0.0.1:$Port"
"-- 换桶操作 (撞 429 配额时执行) --"
"python (Join-Path $PSScriptRoot 'exit_rotator.py') --target mihomo --group PROXY --wait --proxy http://127.0.0.1:$Port"
