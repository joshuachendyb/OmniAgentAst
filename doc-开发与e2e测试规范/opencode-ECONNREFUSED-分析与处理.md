# opencode 桌面版 ECONNREFUSED 问题分析与处理文档

- **日期**：2026-11-18
- **处理人**：OmniAgent（商汤 商量）
- **状态**：✅ 已解决，代理已设为开机自启
- **适用版本**：opencode 桌面版 2.3.0（x64，Bun 单文件 CLI）

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

## 六、手动启动（自动自启失败时兜底）

若开机自启未生效（如启动文件夹 VBS 被禁用、node 未就绪、代理意外退出），可手动启动代理。

### 6.1 一键手动启动脚本（推荐）

脚本：`E:\Appsw\start-opencode-proxy-manual.bat`（双击即可运行）

自动逻辑：
1. 检查 node 与代理脚本是否存在；
2. 检查 `127.0.0.1:18080` 是否已监听——已监听则提示"已在运行"，无需重复启动；
3. 未运行则启动代理，并最多等待 5 秒验证端口就绪；
4. 给出明确结果（`[OK]` 可用 / `[FAIL]` 失败并提示排查方向）。

### 6.2 三种手动启动方式

| 方式 | 操作 | 说明 |
|------|------|------|
| ① 一键脚本（推荐） | 双击 `E:\Appsw\start-opencode-proxy-manual.bat` | 自动判断已运行/未运行，带明确结果提示 |
| ② 双击 VBS | 双击 `E:\Appsw\start-opencode-proxy.vbs` | 隐藏窗口启动，无反馈（成没成功看不出） |
| ③ 命令行前台 | `E:\Appsw\nodejs\node.exe E:\Appsw\opencode-proxy.js` | 前台运行，Ctrl+C 停止 |

### 6.3 启动后验证

```powershell
# 看端口是否监听
netstat -ano | findstr ":18080"

# 走代理实测转发（HTTP:200 即通）
curl -x http://127.0.0.1:18080 -o NUL -w "HTTP:%{http_code}" https://models.opencode.ai/experimental/v2.0/api.json?type=chat
```

### 6.4 手动启动失败排查

| 现象 | 排查方向 |
|------|----------|
| 未找到 node | 检查 `E:\Appsw\nodejs\node.exe` 是否存在 |
| 未找到脚本 | 检查 `E:\Appsw\opencode-proxy.js` 是否存在 |
| 启动后 5 秒仍未监听 | 端口被占用：`netstat -ano \| findstr ":18080"` 看占用 PID，`taskkill /PID <PID> /F` 清掉后重试 |
| 启动后无监听且无报错 | node 无法运行，检查 node 版本/环境变量 |

---

## 七、相关代码

### 附录 A：代理脚本 `opencode-proxy.js`

```javascript
// opencode 本地代理 - 用 node 网络栈转发，绕过 Bun uSockets 网络问题
// 支持 HTTPS CONNECT 隧道 + 普通 HTTP 转发
// 用途：opencode 桌面版 Bun fetch 无法直连外网(ECONNREFUSED)，经此代理用 node 网络栈转发。
// 端口：127.0.0.1:18080
// 启动前检查端口占用，若已监听则退出（避免开机自启重复加载）。
const http = require("http");
const net = require("net");
const PORT = 18080;

// 端口占用检查：若 18080 已监听，说明代理已在运行，直接退出
const probe = net.connect({ port: PORT, host: "127.0.0.1" });
probe.on("connect", () => {
  // 已有一个代理在跑，退出
  console.log("PROXY_ALREADY_RUNNING 127.0.0.1:" + PORT);
  probe.destroy();
  process.exit(0);
});
probe.on("error", () => {
  // 端口空闲，启动代理
  startServer();
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
        headers: req.headers
      }, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      });
      proxyReq.on("error", (e) => { res.writeHead(502); res.end("proxy error: " + e.message); });
      req.pipe(proxyReq);
    } catch (e) {
      res.writeHead(400); res.end("bad request: " + e.message);
    }
  });

  server.on("connect", (req, clientSocket, head) => {
    // HTTPS CONNECT 隧道
    const [host, portStr] = req.url.split(":");
    const port = parseInt(portStr) || 443;
    const serverSocket = net.connect(port, host, () => {
      clientSocket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
      if (head && head.length) serverSocket.write(head);
      serverSocket.pipe(clientSocket);
      clientSocket.pipe(serverSocket);
    });
    serverSocket.on("error", () => { clientSocket.destroy(); });
    clientSocket.on("error", () => { serverSocket.destroy(); });
  });

  server.listen(PORT, "127.0.0.1", () => console.log("PROXY_READY 127.0.0.1:" + PORT));
}
```

### 附录 B：开机自启脚本 `start-opencode-proxy.vbs`

```vbscript
' OmniAgent OpenCode Proxy 开机自启脚本
' 用途：开机时隐藏启动 node 代理(127.0.0.1:18080)，绕过 Bun uSockets ECONNREFUSED
' 代理脚本自带端口占用检查，重复运行会自动退出，无需额外判断。
' 位置：启动文件夹，用户登录时自动运行
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
```

---

## 八、注意事项与回滚

| 事项 | 说明 |
|------|------|
| ⚠️ 代理必须保持运行 | 代理进程停止后 opencode 会再次报 ECONNREFUSED |
| ✅ 开机自启已配置 | 重启电脑后代理会自动启动（启动文件夹 VBS） |
| 回滚代理环境变量 | `opencode service unset env HTTPS_PROXY` |
| 回滚开机自启 | 删除启动文件夹的 `start-opencode-proxy.vbs` |
| 代理端口 | `127.0.0.1:18080`（仅本机监听，无外部暴露风险） |

---

## 九、关键文件清单

| 文件 | 作用 |
|------|------|
| `E:\Appsw\opencode-proxy.js` | node 本地代理主脚本 |
| `E:\Appsw\start-opencode-proxy.vbs` | 开机自启 VBS（源） |
| `E:\Appsw\start-opencode-proxy-manual.bat` | 一键手动启动脚本（自动自启失败时兜底） |
| `C:\Users\chend\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\start-opencode-proxy.vbs` | 开机自启 VBS（已部署） |
| `C:\Users\chend\.local\share\opencode\log\opencode.log` | opencode 日志（根因证据） |
| `F:\agenttool\opencode2.2.5\packages\cli\src\util\process.ts` | opencode 源码（runtime 判定） |
