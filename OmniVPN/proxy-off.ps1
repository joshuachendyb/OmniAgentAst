# proxy-off.ps1 — 一键关代理(取消系统代理, 可选停掉 mihomo)
# 编写人: 小欧    日期: 2026-11-11    版本: v1.1    更新时间: 2026-11-12 01:20:00
# 更新: v1.1 小欧 2026-11-12 目录迁移 OmniVPN\: 路径自洽; 停进程同时收 mihomo-slim 与官方内核名
# 更新: v1.2 小欧 2026-11-12 输出文案统一重排: 区分「已停止/未在运行」, 状态措辞规范化
# 用途: 恢复"直连"状态; 只改「系统代理」与本地进程, 不动路由/网卡
# 用法:
#   powershell -ExecutionPolicy Bypass -File hooks\proxy-off.ps1            # 只取消系统代理
#   powershell -ExecutionPolicy Bypass -File hooks\proxy-off.ps1 -Stop      # 顺带杀掉 mihomo

param(
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'

# 1. 取消系统代理
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
Set-ItemProperty $key -Name ProxyEnable -Value 0
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
"[OK] 系统代理: 已关闭"

# 2. 可选: 停掉 mihomo(两个内核名都收, 精简版/官方版)
if ($Stop) {
    $procs = Get-Process -Name 'mihomo-slim','mihomo-windows-amd64-v1-go122' -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force
        Start-Sleep 1
        "[OK] 内核进程: 已停止"
    } else {
        "[OK] 内核进程: 未在运行"
    }
}

# 3. 报告当前出口
"---- 当前直连出口 (Cloudflare trace, 3~8 秒, 请勿中途关窗) ----"
python (Join-Path $PSScriptRoot 'exit_rotator.py') --verify
