/**
 * e2e_case/api-proxy.ts — 断线重连 E2E 专用后端代理(9000→8000) — 小欧-2026-09-13
 *
 * "进程分离"断流方案核心: 页面由 vite(:5173) 永活服务, API/SSE 直连本代理(:9000)跨域;
 * 断流只 kill 本代理进程 → 浏览器<->9000 的 TCP 直连 RST → 前端 fetch 立即感知(真断线),
 * 页面(vite:5173)永活不 reload → 重连 timer 存活 → 续传必达。与"真实网关/反代短暂重启"语义一致。
 *
 * 职责: ① OPTIONS/preflight 与正文请求全部透传(后端 uvicorn 自身已配 CORS 允许 localhost:5173,
 *         代理不再注入 CORS 头, 避免与后端 ACAO 重复成 "http://localhost:5173, *" 被浏览器拒收)
 *       ② axios 双前缀归一化: 页面 VITE_API_BASE_URL=http://localhost:9000/api/v1 时,
 *          axios 拼出 /api/v1/api/v1/... 双前缀 → 剥掉一个 /api/v1 再转发 8000
 *       ③ SSE/POST/GET 流原样直通(不缓冲)
 *       ④ 每请求一行日志自落盘 e2e_case/output/api-proxy.log
 *
 * 依赖: 零第三方依赖(node 内置 http), node 直接运行: `node e2e_case/api-proxy.ts`
 * 编辑历史: 2026-09-13 小欧 - 初创(断流根因,vite client reload 整页刷新销毁重连timer, 故隔离API链路)
 * 编辑历史: 2026-09-13 小欧 - 加 CORS/OPTIONS/双前缀归一化: vite http-proxy 对上游RST静默挂起(前端无感),
 *   断流必须浏览器直连代理跨域(直连RST才能被fetch感知); axios VITE_API_BASE_URL 注入后产生双前缀需归一 - 小欧-2026-09-13
 * 编辑历史: 2026-09-13 小欧 - 日志改进程内自落盘(转发每请求一行), 移除对 PS -RedirectStandard* 的依赖
 *   (PS 5.1 Start-Process -Redirect 会持有子进程句柄直至子进程退出, node 代理常驻致父PS永不退出ETIMEDOUT) - 小欧-2026-09-13
 * 编辑历史: 2026-09-13 小欧 - 移除 CORS 注入/自答 OPTIONS: 后端 uvicorn 已配 CORS(允许5173), 代理再注入*致
 *   多值头 "http://localhost:5173, *" 被浏览器护栏拒收(Net Error/网络连接异常); 全透传交由后端CORS中间件 - 小欧-2026-09-13
 * 编辑历史: 2026-09-13 小欧 - 迁移: tests/e2e → e2e_case; 日志路径同步改 e2e_case/output - 小欧-2026-09-13
 */
import http from 'node:http';
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const TARGET = process.env.PROXY_TARGET || 'http://localhost:8000';
const PORT = Number(process.env.PROXY_PORT || 9000);
const LOG_PATH = join(process.cwd(), 'e2e_case', 'output', 'api-proxy.log');

mkdirSync(join(process.cwd(), 'e2e_case', 'output'), { recursive: true });
const logLine = (s: string): void => {
  try {
    appendFileSync(LOG_PATH, `${new Date().toISOString()} ${s}\n`, 'utf8');
  } catch {
    /* ignore */
  }
};

const server = http.createServer((req, res) => {
  logLine(`REQ ${req.method} ${req.url} from=${req.socket.remoteAddress}`);
  // OPTIONS 预检交由后端 CORSMiddleware 处理(其已允许 localhost:5173, 返回正确 ACAO)

  // axios 双前缀归一化: /api/v1/api/v1/... → /api/v1/...
  let path = req.url || '/';
  while (path.startsWith('/api/v1/api/v1')) {
    path = path.slice('/api/v1'.length);
  }

  const proxyReq = http.request(
    new URL(path, TARGET),
    {
      method: req.method,
      headers: { ...req.headers, host: new URL(TARGET).host },
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      logLine(`RES ${proxyRes.statusCode ?? 502} ${req.method} ${path}`);
      proxyRes.pipe(res);
    }
  );
  proxyReq.on('error', (e) => {
    logLine(`ERR upstream ${req.method} ${path} :: ${e.message}`);
    // 上游不可达(本代理目标8000异常) → 502
    if (!res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'text/plain' });
    }
    res.end('upstream unavailable');
  });
  req.pipe(proxyReq);
});

server.listen(PORT, () => {
  logLine(`[api-proxy] listening on :${PORT} -> ${TARGET} (pid=${process.pid})`);
});