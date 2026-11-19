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
