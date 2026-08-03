@echo off 
echo == %~f1 
if exist \" "%~f1\version.txt\ forfiles /p \%~f1\ /m version.txt /c \cmd" /c echo version  "@ftime\ 
if exist \%~f1\backend\app\main.py\ echo   main.py: YES || echo   main.py: NO 
echo   app_files: 
for /f %%A in ('dir /a-d /s /b \%~f1\backend\app\ 2>nul | find /c /v \\') do echo %%A 
