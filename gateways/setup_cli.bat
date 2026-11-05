@echo off
rem setup_cli.bat - Copy downstream CLI into runtime\ and verify (size + version probe; no download, doc 6.3.6)
rem Author: Xiao Ou 2026-11-05 (remarks transliterated to English per user order; logic unchanged)
setlocal
set "SRC=%~1"
if "%SRC%"=="" (
  echo Usage: setup_cli.bat ^(full path of opencode-cli.exe^)
  exit /b 2
)
if not exist "%SRC%" ( echo Source not found: %SRC% & exit /b 2 )
if not exist "%~dp0runtime" mkdir "%~dp0runtime"
echo [1/3] Copying...
copy /Y "%SRC%" "%~dp0runtime\opencode-cli.exe" >nul || ( echo Copy failed & exit /b 2 )
echo [2/3] Checking size...
for %%F in ("%~dp0runtime\opencode-cli.exe") do set "SIZE=%%~zF"
if %SIZE% LSS 100000000 ( echo File is only %SIZE% bytes, too small, rejected & exit /b 2 )
echo [3/3] Checking version (gate 1 of 3; full admission done by gateway, doc 6.3.4)...
"%~dp0runtime\opencode-cli.exe" --version || ( echo Version probe failed & exit /b 2 )
echo Done: %~dp0runtime\opencode-cli.exe
endlocal
