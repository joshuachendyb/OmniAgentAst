# OpenCode local proxy watchdog
# Purpose: keep 127.0.0.1:18080 listening. Started by scheduled task every 5 minutes.
# Behavior: if port not listening -> start proxy via VBS (hidden) -> wait up to 10s -> log result.
# Note: ASCII-only messages on purpose (PowerShell 5.1 reads non-BOM UTF-8 as ANSI).
# History:
#   2026-11-20 xiaoou  initial version
$ErrorActionPreference = "Stop"

$Port     = 18080
$NodeExe  = "E:\Appsw\nodejs\node.exe"
$ProxyJs  = "E:\Appsw\opencode-proxy.js"
$Launcher = "E:\Appsw\start-opencode-proxy.vbs"
$LogFile  = "E:\Appsw\opencode-proxy-watchdog.log"
$LogMax   = 1MB

function Write-Log([string]$Message) {
    try {
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $LogMax)) {
            Move-Item -Path $LogFile -Destination ($LogFile + ".1") -Force
        }
        $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $Message
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    } catch {
        # logging must never break the watchdog
    }
}

function Test-ProxyListening {
    try {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
        return ($conns.Count -gt 0)
    } catch {
        return $false
    }
}

if (Test-ProxyListening) { exit 0 }

Write-Log "WARN  port $Port not listening, starting proxy"
if (-not (Test-Path $NodeExe)) { Write-Log "ERROR node not found: $NodeExe"; exit 1 }
if (-not (Test-Path $ProxyJs)) { Write-Log "ERROR proxy script not found: $ProxyJs"; exit 1 }

if (Test-Path $Launcher) {
    Start-Process -FilePath "$env:WINDIR\System32\wscript.exe" -ArgumentList ('"' + $Launcher + '"') -WindowStyle Hidden
} else {
    Start-Process -FilePath $NodeExe -ArgumentList ('"' + $ProxyJs + '"') -WindowStyle Hidden
}

for ($i = 1; $i -le 10; $i++) {
    Start-Sleep -Seconds 1
    if (Test-ProxyListening) {
        Write-Log "INFO  proxy started, listening on port $Port after $i s"
        exit 0
    }
}

Write-Log "ERROR proxy did not listen on port $Port within 10 s"
exit 1
