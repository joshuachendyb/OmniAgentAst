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
