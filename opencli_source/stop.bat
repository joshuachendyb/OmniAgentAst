@echo off
rem opencli gateway stop (kill listeners on port 8080/8081) - xiaoou 2026-11-09
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8080,8081 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
