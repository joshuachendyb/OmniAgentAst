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
 * 编辑历史: 2026-09-13 小欧 - 日志/产物统一规范: 支持 PROXY_LOG 环境变量命名自落盘日志(断连 case 每轮独立轮次文件),
 *   未注入时默认 e2e_case/output/api-proxy.log - 小欧-2026-09-13
 * 编辑历史: 2026-09-14 小欧 - 修复: LOG_PATH 对绝对路径 PROXY_LOG 又 join(cwd) 致畸形路径,
 *   mkdirSync 抛异常 node 崩溃退出(9000 不监听, E1 卡 waitPortUp), 改 resolve(绝对/相对双向正确) - 小欧-2026-09-14
 */
import http from 'node:http';
import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

const TARGET = process.env.PROXY_TARGET || 'http://localhost:8000';
const PORT = Number(process.env.PROXY_PORT || 9000);
const LOG_PATH = process.env.PROXY_LOG
  ? resolve(process.cwd(), process.env.PROXY_LOG)
  : join(process.cwd(), 'e2e_case', 'output', 'api-proxy.log');

mkdirSync(dirname(LOG_PATH), { recursive: true });
const logLine = (s: string): void => {
  try {
    appendFileSync(LOG_PATH, `${new Date().toISOString()} ${s}\n`, 'utf8');
  } catch {
    /* ignore */
  }
};

const server = http.createServer((req, res) => {
  logLine(`REQ ${req.method} ${req.url} from=${req.socket.remoteAddress}`);

  /**
   * 2026-10-22 小欧 - OPTIONS 预检**本代理自答**(反射 Origin + 放行头/方法):
   *   交后端 CORSMiddleware 的问题是: 后端只允许 localhost:5173, 页面用别的源
   *   (如断连 case 的专用页面端口)打开时预检直接失败 → 浏览器拒收 → 整站取不到数据。
   *   自答避免依赖后端的 CORS 白名单(本代理本就是 E2E 专用件)。
   */
  if (req.method === 'OPTIONS') {
    const origin = req.headers.origin || '*';
    res.writeHead(204, {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,PATCH,OPTIONS',
      'Access-Control-Allow-Headers':
        req.headers['access-control-request-headers'] ||
        'Content-Type,Authorization',
      'Access-Control-Max-Age': '600',
      Vary: 'Origin',
    });
    res.end();
    return;
  }

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
      const headers = { ...proxyRes.headers };
      /**
       * 2026-10-22 小欧 - CORS 改为**反射请求 Origin**(并删掉后端那份 ACAO):
       *   页面直连本代理 = 跨域, 后端 CORSMiddleware 只允许 localhost:5173 →
       *   页面用别的源打开时后端回的 ACAO 不含该 Origin → 浏览器拒收
       *   (ERR_FAILED + "blocked by CORS policy")→ 整站无数据, 看起来像"用例全红"。
       *   旧实现"不注入 CORS"(怕与后端 ACAO 重复成 'a, *' 被浏览器拒收)→ 改为**替换**而非追加:
       *   先删后端的 access-control-allow-origin, 再按本次请求的 Origin 回一个(单值, 不会重复)。
       */
      const origin = req.headers.origin;
      if (origin) {
        delete headers['access-control-allow-origin'];
        headers['access-control-allow-origin'] = origin;
        headers['vary'] = 'Origin';
      }
      res.writeHead(proxyRes.statusCode || 502, headers);
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
  logLine(
    `[api-proxy] listening on :${PORT} -> ${TARGET} (pid=${process.pid})`
  );
});
