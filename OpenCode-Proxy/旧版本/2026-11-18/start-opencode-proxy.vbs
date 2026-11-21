' OmniAgent OpenCode Proxy 开机自启脚本
' 用途：开机时隐藏启动 node 代理(127.0.0.1:18080)，绕过 Bun uSockets ECONNREFUSED
' 代理脚本自带端口占用检查，重复运行会自动退出，无需额外判断。
' 位置：启动文件夹，用户登录时自动运行
Set sh = CreateObject("WScript.Shell")
sh.Run """E:\Appsw\nodejs\node.exe"" ""E:\Appsw\opencode-proxy.js""", 0, False
