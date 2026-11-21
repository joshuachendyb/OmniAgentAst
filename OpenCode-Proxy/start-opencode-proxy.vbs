' OmniAgent OpenCode Proxy - autostart launcher
' Purpose: start node proxy (127.0.0.1:18080) with a hidden window at user logon.
' Deployed to: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
' The proxy script self-checks the port and exits if already running, so a duplicate launch is harmless.
' Note: ASCII-only comments on purpose (VBScript reads non-BOM .vbs as ANSI and non-ASCII can break parsing).
' History:
'   2026-11-18 OmniAgent  initial version
'   2026-11-20 xiaoou     comments converted to ASCII to avoid VBScript parse errors
Set sh = CreateObject("WScript.Shell")
sh.Run """E:\Appsw\nodejs\node.exe"" ""E:\Appsw\opencode-proxy.js""", 0, False
