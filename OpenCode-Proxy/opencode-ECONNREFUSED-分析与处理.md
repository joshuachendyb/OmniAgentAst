# opencode 桌面版 ECONNREFUSED 问题分析与处理文档

- **日期**：2026-11-18
- **处理人**：OmniAgent（商汤 商量）
- **更新人**：小欧（2026-11-20 02:19:32）
- **状态**：✅ 已解决，代理已设为开机自启，并由看门狗每 5 分钟自愈
- **适用版本**：opencode 桌面版 2.3.0（x64，Bun 单文件 CLI）
- **配套文档**：`OpenCode本地代理-部署与使用说明-小欧-2026-11-20.md`（同目录，部署与日常使用）

### 版本历史

| 版本 | 时间 | 编写/更新人 | 修改说明 |
|------|------|------------|----------|
| v1.0 | 2026-11-18 | OmniAgent（商汤 商量） | 初版：现象、分层排查、根因、node 代理方案、开机自启 |
| v1.1 | 2026-11-20 01:09:35 | 小欧 | 新增第六章「守护与日志」；附录 A 代理脚本升级（文件日志、建连超时、空闲超时、异常兜底）；新增附录 D 看门狗脚本；后续章节顺延 |
| v1.2 | 2026-11-20 01:19:26 | 小欧 | 文档迁入 `OpenCode-Proxy` 目录，与部署脚本同处一库；头部补充配套文档指引 |
| v1.3 | 2026-11-20 01:28:55 | 小欧 | 看门狗改由 `run-watchdog-hidden.vbs` 静默调用（消除每 5 分钟黑窗）；附录 B 改为 ASCII 版 VBS；新增附录 E；补充 VBS 编码告诫 |
| v1.4 | 2026-11-20 02:19:32 | 小欧 | 关键文件清单补入部署/体检/停止三个 bat，并标注手动启动脚本支持 `/restart` |

---

## 一、问题现象

用户桌面版 opencode 2.3.0 报错：

```
AI.Error: ECONNREFUSED
```

- 报错发生在**所有模型请求**（含 opencode 内置模型 `models.opencode.ai` 与自定义 provider）。
- 日志 `C:\Users\chend\.local\share\opencode\log\opencode.log` 中：
  - 237 次 `Failed to fetch models.dev`（每 5 分钟拉取 `models.opencode.ai`）；
  - 4 次 `Failed to drain Session`（`AI.Error: ECONNREFUSED`，堆栈在 `B:/~BUN/root/`）。

> 关键线索：堆栈路径 `B:/~BUN/root/` —— 报错来自 **Bun 运行时**，而非 node。

---

## 二、排查与排除项（分层对照实验）

### 2.1 网络层 —— 网络本身完全正常

| 实验 | 结果 |
|------|------|
| `curl` 经 skyline VPN 拉 `models.opencode.ai` | TCP 连接 299ms，总 16s（慢但**能通**） |
| `node net` TCP 连接（IPv4/IPv6 全部地址） | **1-3ms CONNECTED** |
| `node undici fetch` 各类 endpoint | **全部成功**（models.opencode.ai 200/592ms） |
| `node` 强制 IPv6 优先 fetch | 成功（200/940ms） |

**结论**：网络、DNS、路由、IPv6、TCP 连通性全部正常，**不是网络问题**。

### 2.2 运行时层 —— 锁定 Bun uSockets 网络栈

- 用 `node undici fetch` 与 `node net` 做对照实验，**node 全通**；
- 唯独 **Bun fetch（uSockets 网络栈）报 ECONNREFUSED**。

**结论**：Bun 的 uSockets 网络栈在这台机器上无法直连外网，被 RST → ECONNREFUSED；node 走不同路径所以能通。

### 2.3 应用层 —— 无法切换 runtime

- 查 opencode 源码 `packages\cli\src\util\process.ts` 的 `selfCommand()`：按 `path.basename(process.execPath)` 判定 runtime（bun/node/nodejs）；
- 桌面版 CLI 是 **Bun 单文件**（`opencode-cli.exe`），**无法切换到 node 运行时**。

### 2.4 已排除项清单

| 假设 | 结论 |
|------|------|
| connectTimeout 250ms 阈值 | ❌ 排除（TCP 实际 1-3ms，远低于阈值） |
| IPv6 问题 | ❌ 排除（node IPv6 优先能通） |
| 网络慢 | ❌ 排除（TCP 1-3ms） |
| 代理配置 | ❌ 排除（无代理端口，系统 ProxyEnable=0） |
| skyline VPN | ❌ 排除（进程退出、TUN 消失、路由恢复后仍报错） |
| WinDivert 驱动 | ❌ 排除（服务已删） |
| 防火墙/杀软 | ❌ 排除（无拦截） |
| 证书/TLS | ❌ 排除（握手成功） |
| hosts 文件 | ❌ 排除（空） |

---

## 三、根因结论

**opencode 桌面版的 Bun 运行时（uSockets 网络栈）在这台机器上无法直连外网，被 RST → `ECONNREFUSED`。node 网络栈完全正常。**

可能诱因：与 2026-11-10 安装的 KB5132061 / KB5132688 安全更新相关（时间线吻合），Bun 的 uSockets 与该更新后的网络栈交互异常。

---

## 四、解决方案（已生效）

**核心思路**：启动一个 **node 本地代理**（用 node 网络栈转发，能通外网），让 opencode 的 Bun fetch 走这个代理，绕过 Bun 的 uSockets 问题。

### 4.1 启动 node 本地代理

代理脚本：`E:\Appsw\opencode-proxy.js`（见附录 A）

监听：`127.0.0.1:18080`，支持 HTTPS CONNECT 隧道 + 普通 HTTP 转发。

### 4.2 让 opencode 服务走代理

```powershell
opencode service set env HTTPS_PROXY http://127.0.0.1:18080
opencode service restart
```

验证：
```powershell
opencode service get env
# 输出: {"HTTPS_PROXY": "http://127.0.0.1:18080"}
```

### 4.3 验证结果

- 重启后日志**无 ECONNREFUSED**（之前每次重启都报错）；
- 服务正常运行（mcp connected / plugin 加载 / 事件正常）；
- 代理转发实测：`curl -x http://127.0.0.1:18080` 拉 `models.opencode.ai` → **HTTP 200**。

---

## 五、开机自启配置（已完成）

### 5.1 方案

使用**启动文件夹**（无需管理员权限，用户登录时自动运行），配合 VBS 隐藏窗口启动。

- 启动脚本：`E:\Appsw\start-opencode-proxy.vbs`（见附录 B）
- 已复制到：`C:\Users\chend\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\start-opencode-proxy.vbs`

### 5.2 防重复启动

代理脚本 `opencode-proxy.js` 内置**端口占用检查**：启动时先探测 `127.0.0.1:18080`，若已监听则自动退出，避免重复加载。

### 5.3 验证

- 停掉旧代理 → 用 VBS 启动 → 新代理 PID 5804 监听 18080 ✅
- 代理转发测试 → HTTP 200 ✅

---

## 六、守护与日志（2026-11-20 加固）

### 6.1 加固背景

开机自启只保证「登录那一刻」启动一次。代理进程若崩溃、被误杀，或 node 安装目录变更，opencode 会立刻回到全模型 `ECONNREFUSED`；而原代理的 `console.log` 输出被隐藏窗口丢弃，故障后无任何可查线索。因此补充**看门狗**与**文件日志**两件基础设施。

### 6.2 看门狗（计划任务，每 5 分钟自愈）

| 项目 | 内容 |
|------|------|
| 任务名 | `OpenCodeProxyWatchdog` |
| 频率 | 每 5 分钟一次（仅用户登录状态运行） |
| 任务动作 | `wscript.exe "E:\Appsw\run-watchdog-hidden.vbs"`（静默启动器，见附录 E） |
| 实际执行 | 静默启动器以窗口样式 0 拉起 `E:\Appsw\watchdog-opencode-proxy.ps1`（见附录 D） |
| 判断逻辑 | 探测 `127.0.0.1:18080` 是否监听 → 未监听则用 VBS 隐藏启动代理 → 最多等 10 秒复检 → 结果写日志 |
| 结果日志 | `E:\Appsw\opencode-proxy-watchdog.log` |

注册命令：

```powershell
$tr = '"C:\Windows\System32\wscript.exe" "E:\Appsw\run-watchdog-hidden.vbs"'
schtasks /Create /TN "OpenCodeProxyWatchdog" /SC MINUTE /MO 5 /TR $tr /F
```

> 为什么绕一层 `wscript`：计划任务直接调用 `powershell.exe`（控制台程序）时，即使脚本 1 秒结束，也会**每 5 分钟闪出一个黑色控制台窗口**。`wscript.exe` 是 GUI 子系统宿主、本身不建控制台，再以窗口样式 0 拉起 powershell，即可完全无窗。（2026-11-20 之前正是直接调用 powershell，故有此现象。）

常见坑：`.vbs` 若存成 UTF-8 无 BOM，VBScript 按 ANSI 解析中文注释会报 `缺少对象`，`wscript` 弹错误框并把任务卡在"正在运行"。故两个 VBS 一律只写 ASCII 注释。

常用操作：

```powershell
# 立即触发一次（不必等 5 分钟）
schtasks /Run /TN "OpenCodeProxyWatchdog"

# 查看任务状态与下次运行时间
schtasks /Query /TN "OpenCodeProxyWatchdog" /V /FO LIST

# 查看看门狗日志（仅在有异常时才会写行）
Get-Content E:\Appsw\opencode-proxy-watchdog.log -Tail 20
```

### 6.3 代理文件日志

- 文件：`E:\Appsw\opencode-proxy.log`，超过 5 MB 自动滚动为 `opencode-proxy.log.1`。
- 记录内容：启动就绪、重复启动退出、转发失败、隧道建连超时、隧道空闲超时、客户端异常、未捕获异常。
- 时间格式为 **UTC**（`...Z`），与 `opencode.log` 的时间基准一致，便于交叉比对。

```powershell
Get-Content E:\Appsw\opencode-proxy.log -Tail 30
```

### 6.4 超时保护参数

| 参数 | 值 | 作用 |
|------|-----|------|
| `CONNECT_TIMEOUT_MS` | 15000 | 对外建连 15 秒不通即断开，避免请求永久挂起 |
| `IDLE_TIMEOUT_MS` | 600000 | 隧道 10 分钟无数据即回收，防止半开连接堆积 |
| 未捕获异常 | 记日志后 `exit(1)` | 交由看门狗在 5 分钟内重新拉起 |

### 6.5 自愈实测（2026-11-20 01:09）

| 步骤 | 结果 |
|------|------|
| 强制结束代理进程（PID 6208） | 18080 立刻无监听 |
| 触发 `schtasks /Run` 模拟到点 | 3 秒内恢复监听（新 PID 11976） |
| 看门狗日志 | `WARN port 18080 not listening, starting proxy` → `INFO proxy started, listening on port 18080 after 1 s` |
| 代理日志 | 新增 `PROXY_READY 127.0.0.1:18080` |
| opencode 重连 | 自动重建 `127.0.0.1:xxxxx → 18080`，转发实测 HTTP 200 |

### 6.6 未覆盖的边界

| 边界 | 现状与应对 |
|------|-----------|
| 用户未登录 | 计划任务不运行，代理也不启动；登录后由启动文件夹 VBS + 5 分钟任务双保险 |
| node 目录被移动/卸载 | 看门狗日志会写 `ERROR node not found`，需同步修改 `watchdog-opencode-proxy.ps1` 与 VBS 中的路径 |
| 端口被其他程序占用 | 代理启动即 `server error` 并退出，看门狗日志会连续记录，需 `netstat -ano \| findstr ":18080"` 定位占用进程 |

---

## 七、手动启动（自动自启失败时兜底）

若开机自启未生效（如启动文件夹 VBS 被禁用、node 未就绪、代理意外退出），可手动启动代理。

### 7.1 一键手动启动脚本（推荐）

脚本：`E:\Appsw\start-opencode-proxy-manual.bat`（双击即可运行）

自动逻辑：
1. 检查 node 与代理脚本是否存在；
2. 检查 `127.0.0.1:18080` 是否已监听——已监听则提示"已在运行"，无需重复启动；
3. 未运行则启动代理，并最多等待 5 秒验证端口就绪；
4. 给出明确结果（`[OK]` 可用 / `[FAIL]` 失败并提示排查方向）。

### 7.2 三种手动启动方式

| 方式 | 操作 | 说明 |
|------|------|------|
| ① 一键脚本（推荐） | 双击 `E:\Appsw\start-opencode-proxy-manual.bat` | 自动判断已运行/未运行，带明确结果提示 |
| ② 双击 VBS | 双击 `E:\Appsw\start-opencode-proxy.vbs` | 隐藏窗口启动，无反馈（成没成功看不出） |
| ③ 命令行前台 | `E:\Appsw\nodejs\node.exe E:\Appsw\opencode-proxy.js` | 前台运行，Ctrl+C 停止 |

### 7.3 启动后验证

```powershell
# 看端口是否监听
netstat -ano | findstr ":18080"

# 走代理实测转发（HTTP:200 即通）
curl -x http://127.0.0.1:18080 -o NUL -w "HTTP:%{http_code}" https://models.opencode.ai/experimental/v2.0/api.json?type=chat
```

### 7.4 手动启动失败排查

| 现象 | 排查方向 |
|------|----------|
| 未找到 node | 检查 `E:\Appsw\nodejs\node.exe` 是否存在 |
| 未找到脚本 | 检查 `E:\Appsw\opencode-proxy.js` 是否存在 |
| 启动后 5 秒仍未监听 | 端口被占用：`netstat -ano \| findstr ":18080"` 看占用 PID，`taskkill /PID <PID> /F` 清掉后重试 |
| 启动后无监听且无报错 | node 无法运行，检查 node 版本/环境变量 |

---

## 八、相关代码

### 附录 A：代理脚本 `opencode-proxy.js`

```javascript
// opencode 本地代理 - 用 node 网络栈转发，绕过 Bun uSockets 网络问题
// 支持 HTTPS CONNECT 隧道 + 普通 HTTP 转发
// 用途：opencode 桌面版 Bun fetch 无法直连外网(ECONNREFUSED)，经此代理用 node 网络栈转发。
// 端口：127.0.0.1:18080
// 启动前检查端口占用，若已监听则退出（避免开机自启重复加载）。
// 日志：E:\Appsw\opencode-proxy.log（超过 5MB 滚动为 .1），由看门狗计划任务兜底拉起。
//
// 修改历史（最新在下）：
// 2026-11-18  OmniAgent  初版：端口占用检查 + CONNECT 隧道 + HTTP 转发
// 2026-11-20  小欧       增加文件日志、对外建连超时、隧道空闲超时、未捕获异常兜底，客户端主动中断不记录
"use strict";

const http = require("http");
const net = require("net");
const fs = require("fs");

const HOST = "127.0.0.1";
const PORT = 18080;
const LOG_FILE = "E:\\Appsw\\opencode-proxy.log";
const LOG_MAX_BYTES = 5 * 1024 * 1024;
const CONNECT_TIMEOUT_MS = 15000;   // 对外建连超时
const IDLE_TIMEOUT_MS = 600000;     // 隧道空闲超时(10分钟)，防止半开连接堆积

// 写日志：失败不影响转发；超限自动滚动
function log(level, message) {
  try {
    if (fs.existsSync(LOG_FILE) && fs.statSync(LOG_FILE).size > LOG_MAX_BYTES) {
      fs.renameSync(LOG_FILE, LOG_FILE + ".1");
    }
    fs.appendFileSync(LOG_FILE, new Date().toISOString() + " " + level + " " + message + "\n");
  } catch (e) {
    // 手动忽略：日志不可写时继续转发
  }
}

// 未捕获异常：记日志后退出，交给看门狗计划任务重新拉起
process.on("uncaughtException", (e) => {
  log("FATAL", "uncaughtException: " + (e && e.stack ? e.stack : String(e)));
  process.exit(1);
});

function startServer() {
  const server = http.createServer((req, res) => {
    // 普通 HTTP 请求转发
    try {
      const u = new URL(req.url);
      const proxyReq = http.request({
        host: u.hostname,
        port: u.port || 80,
        path: u.pathname + u.search,
        method: req.method,
        headers: req.headers,
        timeout: CONNECT_TIMEOUT_MS
      }, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      });
      proxyReq.on("timeout", () => {
        proxyReq.destroy(new Error("upstream connect timeout " + CONNECT_TIMEOUT_MS + "ms"));
      });
      proxyReq.on("error", (e) => {
        log("WARN", "http forward failed " + req.method + " " + u.host + " -> " + e.message);
        if (!res.headersSent) res.writeHead(502);
        res.end("proxy error: " + e.message);
      });
      req.pipe(proxyReq);
    } catch (e) {
      log("WARN", "bad request " + req.url + " -> " + e.message);
      res.writeHead(400);
      res.end("bad request: " + e.message);
    }
  });

  server.on("connect", (req, clientSocket, head) => {
    // HTTPS CONNECT 隧道
    const target = req.url || "";
    const idx = target.lastIndexOf(":");
    const host = idx > 0 ? target.slice(0, idx) : target;
    const port = idx > 0 ? parseInt(target.slice(idx + 1), 10) || 443 : 443;

    let connected = false;
    const serverSocket = net.connect(port, host, () => {
      connected = true;
      clearTimeout(connectTimer);
      clientSocket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
      if (head && head.length) serverSocket.write(head);
      serverSocket.pipe(clientSocket);
      clientSocket.pipe(serverSocket);
    });

    const connectTimer = setTimeout(() => {
      if (connected) return;
      log("WARN", "tunnel connect timeout " + host + ":" + port + " (" + CONNECT_TIMEOUT_MS + "ms)");
      serverSocket.destroy();
      clientSocket.destroy();
    }, CONNECT_TIMEOUT_MS);

    serverSocket.setTimeout(IDLE_TIMEOUT_MS, () => {
      log("WARN", "tunnel idle timeout " + host + ":" + port + " (" + IDLE_TIMEOUT_MS + "ms)");
      serverSocket.destroy();
      clientSocket.destroy();
    });

    serverSocket.on("error", (e) => {
      clearTimeout(connectTimer);
      log("WARN", "tunnel error " + host + ":" + port + " -> " + e.message);
      clientSocket.destroy();
    });

    clientSocket.on("error", (e) => {
      clearTimeout(connectTimer);
      // 客户端主动中断（取消请求、切换会话）属正常行为，不记日志，避免淹没真正的故障
      if (e.code !== "ECONNRESET" && e.code !== "EPIPE") {
        log("WARN", "client error " + host + ":" + port + " -> " + e.message);
      }
      serverSocket.destroy();
    });
  });

  server.on("error", (e) => {
    log("FATAL", "server error: " + e.message);
    process.exit(1);
  });

  server.listen(PORT, HOST, () => {
    log("INFO", "PROXY_READY " + HOST + ":" + PORT);
  });
}

// 端口占用检查：若 18080 已监听，说明代理已在运行，直接退出
const probe = net.connect({ port: PORT, host: HOST });
probe.setTimeout(2000, () => {
  probe.destroy();
  startServer();
});
probe.on("connect", () => {
  log("INFO", "PROXY_ALREADY_RUNNING " + HOST + ":" + PORT);
  probe.destroy();
  process.exit(0);
});
probe.on("error", () => {
  // 端口空闲，启动代理
  startServer();
});
```

### 附录 B：开机自启脚本 `start-opencode-proxy.vbs`

```vbscript
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
```

### 附录 C：命令行操作汇总

```powershell
# 0. 一键手动启动（推荐，双击运行）
E:\Appsw\start-opencode-proxy-manual.bat

# 1. 手动启动代理（前台调试，Ctrl+C 停止）
node E:\Appsw\opencode-proxy.js

# 2. 设置 opencode 服务走代理（一次性，持久生效）
opencode service set env HTTPS_PROXY http://127.0.0.1:18080

# 3. 重启 opencode 服务
opencode service restart

# 4. 查看当前代理设置
opencode service get env

# 5. 验证代理转发
curl -x http://127.0.0.1:18080 -o NUL -w "HTTP:%{http_code}" https://models.opencode.ai/experimental/v2.0/api.json?type=chat

# 6. 看门狗：立即触发一次自愈
schtasks /Run /TN "OpenCodeProxyWatchdog"

# 7. 看门狗：查看状态与下次运行时间
schtasks /Query /TN "OpenCodeProxyWatchdog" /V /FO LIST

# 8. 代理与被守护日志
Get-Content E:\Appsw\opencode-proxy.log -Tail 30
Get-Content E:\Appsw\opencode-proxy-watchdog.log -Tail 20

# 9. 改看门狗任务动作为静默启动器（消除黑窗）
$tr = '"C:\Windows\System32\wscript.exe" "E:\Appsw\run-watchdog-hidden.vbs"'
schtasks /Change /TN "OpenCodeProxyWatchdog" /TR $tr
```

### 附录 D：看门狗脚本 `watchdog-opencode-proxy.ps1`

由静默启动器 `run-watchdog-hidden.vbs` 以隐藏窗口调用；端口已监听时静默退出（不写日志），未监听则拉起代理并回报结果。

```powershell
# OpenCode local proxy watchdog
# Purpose: keep 127.0.0.1:18080 listening. Started by scheduled task every 5 minutes.
# Behavior: if port not listening -> start proxy via VBS (hidden) -> wait up to 10s -> log result.
# Note: ASCII-only messages on purpose (PowerShell 5.1 reads non-BOM UTF-8 as ANSI).
# History:
#   2026-11-20 xiaoou  initial version
$ErrorActionPreference = "Stop"

$Port     = 18080
$NodeExe  = "E:\Appsw\nodejs\node.exe"
$ProxyJs  = "E:\Appsw\opencode-proxy.js"
$Launcher = "E:\Appsw\start-opencode-proxy.vbs"
$LogFile  = "E:\Appsw\opencode-proxy-watchdog.log"
$LogMax   = 1MB

function Write-Log([string]$Message) {
    try {
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $LogMax)) {
            Move-Item -Path $LogFile -Destination ($LogFile + ".1") -Force
        }
        $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $Message
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    } catch {
        # logging must never break the watchdog
    }
}

function Test-ProxyListening {
    try {
        $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
        return ($conns.Count -gt 0)
    } catch {
        return $false
    }
}

if (Test-ProxyListening) { exit 0 }

Write-Log "WARN  port $Port not listening, starting proxy"
if (-not (Test-Path $NodeExe)) { Write-Log "ERROR node not found: $NodeExe"; exit 1 }
if (-not (Test-Path $ProxyJs)) { Write-Log "ERROR proxy script not found: $ProxyJs"; exit 1 }

if (Test-Path $Launcher) {
    Start-Process -FilePath "$env:WINDIR\System32\wscript.exe" -ArgumentList ('"' + $Launcher + '"') -WindowStyle Hidden
} else {
    Start-Process -FilePath $NodeExe -ArgumentList ('"' + $ProxyJs + '"') -WindowStyle Hidden
}

for ($i = 1; $i -le 10; $i++) {
    Start-Sleep -Seconds 1
    if (Test-ProxyListening) {
        Write-Log "INFO  proxy started, listening on port $Port after $i s"
        exit 0
    }
}

Write-Log "ERROR proxy did not listen on port $Port within 10 s"
exit 1
```

### 附录 E：看门狗静默启动器 `run-watchdog-hidden.vbs`

计划任务的直接动作。`wscript.exe` 属 GUI 子系统、不创建控制台；内部以窗口样式 0 拉起 powershell，故每 5 分钟不会有黑窗闪现。注释必须保持 ASCII（见 6.2 的编码告诫）。

```vbscript
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
```

---

## 九、注意事项与回滚

| 事项 | 说明 |
|------|------|
| ⚠️ 代理必须保持运行 | 代理进程停止后 opencode 会再次报 ECONNREFUSED |
| ✅ 开机自启已配置 | 重启电脑后代理会自动启动（启动文件夹 VBS） |
| 回滚代理环境变量 | `opencode service unset env HTTPS_PROXY` |
| 回滚开机自启 | 删除启动文件夹的 `start-opencode-proxy.vbs` |
| 回滚看门狗 | `schtasks /Delete /TN "OpenCodeProxyWatchdog" /F` |
| 代理端口 | `127.0.0.1:18080`（仅本机监听，无外部暴露风险） |
| ✅ 崩溃自愈已配置 | 代理意外退出后，看门狗在 5 分钟内自动拉起（实测 3 秒内恢复） |
| ✅ 看门狗不弹窗 | 任务动作是 `wscript.exe` + `run-watchdog-hidden.vbs`；若改回直接跑 `powershell.exe`，每 5 分钟会闪一次黑窗 |
| 日志排查入口 | 代理异常看 `opencode-proxy.log`，拉起异常看 `opencode-proxy-watchdog.log` |

---

## 十、关键文件清单

| 文件 | 作用 |
|------|------|
| `E:\Appsw\opencode-proxy.js` | node 本地代理主脚本（v2：文件日志 + 超时保护） |
| `E:\Appsw\start-opencode-proxy.vbs` | 开机自启 VBS（源） |
| `E:\Appsw\watchdog-opencode-proxy.ps1` | 看门狗脚本（计划任务每 5 分钟调用） |
| `E:\Appsw\run-watchdog-hidden.vbs` | 看门狗静默启动器（wscript 宿主，不建控制台） |
| `E:\Appsw\start-opencode-proxy-manual.bat` | 手动启动脚本（`/restart` 强制重启；自动自启失败时兜底） |
| `E:\Appsw\deploy-opencode-proxy.bat` | 一键部署/升级（备份→复制→语法自检→启动→自启→计划任务→验收） |
| `E:\Appsw\check-opencode-proxy.bat` | 运行状态体检（7 项：端口/进程/转发/接入/配置/看门狗/日志） |
| `E:\Appsw\stop-opencode-proxy.bat` | 停止代理（`/keepoff` 同时禁用看门狗） |
| `E:\Appsw\opencode-proxy.log` | 代理运行日志（UTC 时间，5 MB 滚动） |
| `E:\Appsw\opencode-proxy-watchdog.log` | 看门狗日志（仅异常时写入） |
| `C:\Users\chend\.config\opencode\service.json` | opencode 服务的 `HTTPS_PROXY` 配置 |
| `C:\Users\chend\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\start-opencode-proxy.vbs` | 开机自启 VBS（已部署） |
| `C:\Users\chend\.local\share\opencode\log\opencode.log` | opencode 日志（根因证据） |
| `F:\agenttool\opencode2.2.5\packages\cli\src\util\process.ts` | opencode 源码（runtime 判定） |
