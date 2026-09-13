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

/** 执行一条 PowerShell 命令并返回去空白输出（Windows 专用封装） */
export const ps = (cmd: string): string => {
  const errLog = join(__dir, '..', 'tests', 'e2e', 'output', 'ps-errors.txt');
  try {
    return execFileSync(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-Command', `${cmd}; exit 0`],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 60_000 }
    ).trim();
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string; message?: string };
    try {
      mkdirSync(join(__dir, '..', 'tests', 'e2e', 'output'), { recursive: true });
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

// 编辑历史: 2026-09-13 小欧 - 修复: 先 Get 并判断存在再 Stop-Process(对空端口/不存在PID, Stop-Process 使进程exit=1, 空catch也救不回) - 小欧-2026-09-13
/** 杀掉指定端口（Listen 状态）的进程，用于断流/重启服务场景 */
export const killPort = (port: number): void => {
  ps(
    `$c = Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }`
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

// 编辑历史: 2026-09-13 小欧 - 新增: 启动断线重连E2E专用后端代理(node tests/e2e/api-proxy.ts, 9000→8000), 返回PID
//   进程分离断流方案核心入口; 断流=kill代理(REFUSED/RST), 恢复=再启本代理。日志代理内部自落盘, 不做PS重定向
//   (PS 5.1 Start-Process -Redirect 持有子句柄致父PS挂起ETIMEDOUT) - 小欧-2026-09-13
export const startProxyServer = (frontendDir: string): number => {
  const out = ps(
    `$p = Start-Process -FilePath 'node.exe' -ArgumentList 'tests/e2e/api-proxy.ts' -WorkingDirectory '${frontendDir}' -WindowStyle Hidden -PassThru; $p.Id`
  );
  return Number(out);
};