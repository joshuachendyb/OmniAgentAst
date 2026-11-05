@echo off
rem stop.bat - Stop the gateway on port 8199 with its downstream CLI children.
rem taskkill /T kills the whole tree: Stop-Process left opencode-cli orphans holding 8200+ (seen 2026-11-05).
rem FIX C (doc 9.1.10): doc-style ^ line continuation breaks under cmd; kept single-line PowerShell.
rem Author: Xiao Ou 2026-11-05 (remarks transliterated to English per user order)
rem
rem Edit history:
rem 2026-11-05 Xiao Ou - created: stop gateway on 8199 (single-line PowerShell, FIX C)
rem 2026-11-05 Xiao Ou - taskkill /PID /T /F: Stop-Process left downstream CLI orphans on 8200-8202
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8199 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | Select-Object -Unique | ForEach-Object { & taskkill /PID $_ /T /F | Out-Null }; Write-Host 'Gateway(8199) stopped' } else { Write-Host 'Gateway(8199) not running' }"
