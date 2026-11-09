@echo off
rem opencli gateway start (foreground window, close to stop) - xiaoou 2026-11-09
cd /d "%~dp0"
opencode2api.exe -config config.json
