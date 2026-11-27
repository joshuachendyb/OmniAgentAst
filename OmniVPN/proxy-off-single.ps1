# proxy-off-single.ps1 — 一键关代理(一级模式): 取消系统代理, 可选停掉 mihomo
# 编写人: 商量    日期: 2026-11-28    版本: v1.0
# 用途: 与二级 proxy-off.ps1 并存互斥。一级模式关代理 = 恢复直连(取消系统代理, 可选停内核)。
# 用法:
#   powershell -ExecutionPolicy Bypass -File proxy-off-single.ps1            # 只取消系统代理
#   powershell -ExecutionPolicy Bypass -File proxy-off-single.ps1 -Stop      # 顺带杀掉 mihomo

param(
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"============================================================"
"proxy-off-single v1.0  一键关代理(一级模式)   $stamp"
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
