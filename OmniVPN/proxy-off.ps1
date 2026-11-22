# proxy-off.ps1 — 一键关代理(取消系统代理, 可选停掉 mihomo)
# 编写人: 小欧    日期: 2026-11-11    版本: v1.4    更新时间: 2026-11-22 19:48:51
# 更新: v1.1 小欧 2026-11-12 目录迁移 OmniVPN\: 路径自洽; 停进程同时收 mihomo-slim 与官方内核名
# 更新: v1.2 小欧 2026-11-12 输出文案统一重排: 区分「已停止/未在运行」, 状态措辞规范化
# 更新: v1.3 小欧 2026-11-22 输出改为 exit_probe 风格 [1]~[3] 阶段编号, 与 proxy-on 一致, 文案精简
# 更新: v1.4 小欧 2026-11-22 系统代理取消从置 ProxyEnable=0 改为删 ProxyEnable/ProxyServer/ProxyOverride 三键, 彻底清除代理地址与绕过表残留, 杜绝机器重启后开关关但地址仍在的死代理
# 用途: 恢复"直连"状态; 只改「系统代理」与本地进程, 不动路由/网卡
# 用法:
#   powershell -ExecutionPolicy Bypass -File proxy-off.ps1            # 只取消系统代理
#   powershell -ExecutionPolicy Bypass -File proxy-off.ps1 -Stop      # 顺带杀掉 mihomo

param(
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"============================================================"
"proxy-off v1.4  一键关代理   $stamp"
"============================================================"
""

# 1. 取消系统代理
'[1] 系统代理 (WinInet)'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
foreach ($name in 'ProxyEnable','ProxyServer','ProxyOverride') {
    Remove-ItemProperty -Path $key -Name $name -ErrorAction SilentlyContinue
}
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
'    状态       : 已清除 (ProxyEnable/ProxyServer/ProxyOverride)'
""

# 2. 可选: 停掉 mihomo(两个内核名都收, 精简版/官方版)
'[2] 内核进程'
if ($Stop) {
    $procs = Get-Process -Name 'mihomo-slim','mihomo-windows-amd64-v1-go122' -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force
        Start-Sleep 1
        '    状态       : 已停止'
    } else {
        '    状态       : 未在运行'
    }
} else {
    '    状态       : 跳过 (未指定 -Stop)'
}
""

# 3. 报告当前出口
'[3] 当前直连出口 (Cloudflare trace, 3~8 秒, 请勿中途关窗)'
python (Join-Path $PSScriptRoot 'exit_rotator.py') --verify | ForEach-Object { "    $_" }
