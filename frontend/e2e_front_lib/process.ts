/**
 * e2e_front_lib/process.ts — Windows 进程/端口/服务控制工具（前端 Playwright E2E 公用库）
 * 小欧 2026-09-13（自 reconnect-ui.spec.ts 抽取，仅改导入路径不动业务逻辑）
 *
 * 依赖 Windows PowerShell 命令，仅适用于本机 Windows 环境。
 */
import { execFileSync } from 'node:child_process';
import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dir = dirname(fileURLToPath(import.meta.url));

// 编辑历史: 2026-09-13 小欧 v3 - 迁移后 ps 失败日志目录同步补: 原 tests/e2e/output 已迁移删除, 改 e2e_case/output - 小欧-2026-09-13
/** 执行一条 PowerShell 命令并返回去空白输出（Windows 专用封装） */
export const ps = (cmd: string): string => {
  const errLog = join(__dir, '..', 'e2e_case', 'output', 'ps-errors.txt');
  try {
    return execFileSync(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-Command', `${cmd}; exit 0`],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 60_000 }
    ).trim();
  } catch (e) {
    const err = e as {
      status?: number;
      stdout?: string;
      stderr?: string;
      message?: string;
    };
    try {
      mkdirSync(join(__dir, '..', 'e2e_case', 'output'), { recursive: true });
      appendFileSync(
        errLog,
        `[${new Date().toISOString()}] CMD: ${cmd}\n  STATUS=${err.status ?? 'n/a'}\n  MSG=${err.message ?? ''}\n  STDOUT=${(err.stdout ?? '').slice(0, 500)}\n  STDERR=${(err.stderr ?? '').slice(0, 500)}\n---\n`,
        'utf8'
      );
    } catch {
      /* ignore */
    }
    throw e;
  }
};

// 编辑历史: 2026-09-13 小欧 v2 - 杀全量 listener owner(多listener并存时 $c 为数组, $c.OwningProcess 被PS拼接成"a b"
//   致 Stop-Process -Id 无效 → 静默空杀 → 后端 is_reconnect=False 直通 final(E2E步骤5假红) - 小欧-2026-09-13
/** 杀掉指定端口（Listen 状态）的全部进程，用于断流/重启服务场景 */
export const killPort = (port: number): void => {
  ps(
    `$c = @(Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue); foreach ($x in $c) { try { Stop-Process -Id $x.OwningProcess -Force -ErrorAction Stop } catch {} }`
  );
};

/** 隐藏窗口启动 npm dev server，返回进程 PID；envCmd 为可选的 Windows 环境变量前缀(如 "set X=y && ") */
export const startDevServer = (
  projectDir: string,
  npmArgs: string,
  envCmd = ''
): number => {
  const out = ps(
    `$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',('cd /d ${projectDir} && ' + '${envCmd}' + 'npm ${npmArgs}') -WindowStyle Hidden -PassThru; $p.Id`
  );
  return Number(out);
};

// 编辑历史: 2026-09-13 小欧 - waitPortUp 判定放宽(status 200~499 视为已就绪):
//   9000 E2E代理对根路径无路由返回404, 原仅认200会误判未启动 - 小欧-2026-09-13
/** 轮询 http://localhost:port 直至返回 2xx-4xx，用于"等服务就绪"判断 */
export const waitPortUp = (port: number): boolean => {
  try {
    const out = ps(
      `try { $r = Invoke-WebRequest http://localhost:${port} -UseBasicParsing -TimeoutSec 3; $r.StatusCode } catch { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 } }`
    );
    const status = Number(out);
    return status >= 200 && status < 500;
  } catch {
    return false;
  }
};

// 编辑历史: 2026-09-13 小欧 - 新增: 等待指定端口无 Listen 占用(断流后端口真正释放, 防 kill→启动竞态下 strictPort vite 起不来) - 小欧-2026-09-13
export const waitPortDown = (port: number): boolean => {
  try {
    const out = ps(
      `if (Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue) { 'occupied' } else { 'free' }`
    );
    return out === 'free';
  } catch {
    return false;
  }
};

// 编辑历史: 2026-09-13 小欧 v2 - 迁移后路径: 断线重连E2E专用后端代理(node e2e_case/api-proxy.ts, 9000→8000), 返回PID
//   进程分离断流方案核心入口; 断流=kill代理(REFUSED/RST), 恢复=再启本代理。日志代理内部自落盘, 不做PS重定向
//   (PS 5.1 Start-Process -Redirect 持有子句柄致父PS挂起ETIMEDOUT) - 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 v3 - 按日志/产物统一规范: 支持传 logFile, 通过 PROXY_LOG 环境变量注入代理
//   自落盘命名(默认无传则沿用 e2e_case/output/api-proxy.log) - 小欧-2026-09-13
/** 启动 9000→8000 后端代理(node e2e_case/api-proxy.ts)。logFile 为可选的代理自落盘日志路径(经 PROXY_LOG 注入) */
export const startProxyServer = (
  frontendDir: string,
  logFile?: string
): number => {
  const envPrefix = logFile ? `set "PROXY_LOG=${logFile}"&& ` : '';
  const out = ps(
    `$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',('cd /d ${frontendDir} && ' + '${envPrefix}' + 'node e2e_case/api-proxy.ts') -WindowStyle Hidden -PassThru; $p.Id`
  );
  return Number(out);
};

// 编辑历史: 2026-09-13 小欧 - 新增: 生成"本轮代理日志名" e2e_case/output/api-proxy-<ts>.log(时间戳,轮次隔离) - 小欧-2026-09-13
/** 生成代理自落盘日志路径 e2e_case/output/api-proxy-<ts>.log（断连 case 每轮独立命名） */
export const proxyLogPath = (): string => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  const ts = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  return join(__dir, '..', 'e2e_case', 'output', `api-proxy-${ts}.log`);
};

// 编辑历史: 2026-09-13 小欧 v4 - 新增 ensureDevServer(复用优先起 dev server): 端口已有活服务则直接复用(不kill不冷启动),
//   无服务才 npmArgs 启动并 poll 就绪 —— 普通功能 case 免白屏冷启动, 复用由探测(~百ms)判定 - 小欧-2026-09-13
/** 复用优先确保 dev server 就绪: 端口已有活服务(HTTP 2xx-4xx)则直接复用, 否则启动并等就绪。
 *  适用: 非强制独占端口的普通会话流 case; 断连 case(须自启 hmr:false 专用config独占5173)不走本函数。 */
export const ensureDevServer = async (
  port: number,
  projectDir: string,
  npmArgs: string,
  envCmd = ''
): Promise<void> => {
  if (waitPortUp(port)) return; // 已活 → 复用(免冷启动白屏)
  startDevServer(projectDir, npmArgs, envCmd);
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (waitPortUp(port)) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`[E2E] dev server(:${port}) 就绪超时(ensureDevServer)`);
};
