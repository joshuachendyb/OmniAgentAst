' OmniAgent OpenCode Proxy watchdog - silent launcher
' Purpose: called by scheduled task OpenCodeProxyWatchdog every 5 minutes.
'          Runs watchdog-opencode-proxy.ps1 with a hidden window (no black console).
' Why: wscript.exe is a GUI-subsystem host and never creates a console window;
'      the child powershell is started with window style 0 (hidden).
' Exit code: waits for powershell and returns its code, so Task Scheduler shows 0/1.
' Note: ASCII-only comments on purpose (VBScript reads non-BOM files as ANSI).
' History:
'   2026-11-20 xiaoou  initial version
Set sh = CreateObject("WScript.Shell")
cmd = """C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -ExecutionPolicy Bypass -File ""E:\Appsw\watchdog-opencode-proxy.ps1"""
rc = sh.Run(cmd, 0, True)
WScript.Quit rc
