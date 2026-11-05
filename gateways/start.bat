@echo off
rem start.bat - Start gateway. NO_PROXY set explicitly: loopback must bypass system proxy (doc 9.7 row 2)
rem Author: Xiao Ou 2026-11-05 (remarks transliterated to English per user order; logic unchanged)
setlocal
set "NO_PROXY=127.0.0.1,localhost"
set "no_proxy=127.0.0.1,localhost"
cd /d "%~dp0"
python gateway.py
endlocal
