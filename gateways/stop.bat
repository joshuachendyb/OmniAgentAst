@echo off
rem stop.bat - Stop ONLY the process listening on port 8199 (host app / downstream pool untouched)
rem Downstream opencode-cli pool processes are children of the gateway; cleaned by cli_manager.shutdown on exit.
rem FIX C (doc 9.1.10): doc-style ^ line continuation breaks under cmd; kept single-line PowerShell.
rem Author: Xiao Ou 2026-11-05 (remarks transliterated to English per user order; logic unchanged)
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8199 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force } } else { Write-Host 'Gateway(8199) not running' }"
