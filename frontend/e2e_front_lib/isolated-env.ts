/**
 * e2e_front_lib/isolated-env.ts — 配置类 E2E 隔离环境（真配置够不到） — 小欧 2026-09-28
 *
 * 适用范围（AGENTS.md 配置隔离铁律 + 北京老陈 2026-09-28 定调）：
 *   ① 跑任务的用例（fre2e_01~07）—— **不隔离**，必须用真实后端与真实模型，行为与生产一致。
 *   ② 只读配置的用例 —— 无所谓，不强制隔离。
 *   ③ **写配置的用例（fre2e_08/09/10/11/12）—— 必须隔离**，本模块即为此而建。
 *
 * 机制（与 backend/tests/conftest.py 的 isolated_config_dir 同思路，复用唯一覆盖入口）：
 *   真 config.yaml 只读拷一份到临时目录 → 隔离后端经 OMNIAGENT_CONFIG_PATH 改道到副本。
 *   副本里 provider / api_key / models 全是真值，所以隔离不影响「用真实模型」这件事，
 *   隔离的只是**写**的落点。真配置自始至终不可写。
 *
 * 三进程栈（与断流 case 的「独立 vite + 独立代理」同款，互不干扰）：
 *   页面 vite :5174（vite.isolated.config.ts）→ 代理 :9001 → 隔离后端 :8898
 *
 * @author 小欧 2026-09-28
 */
import { execFileSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { killPort, ps, waitPortDown, waitPortUp } from './process';

export const ISO_BACKEND_PORT = 8898;
export const ISO_PROXY_PORT = 9001;
export const ISO_VITE_PORT = 5174;

/** 写配置用例的 API 基址（Playwright request 直连用；页面侧走 vite proxy，不需此值） */
export const ISO_API = `http://127.0.0.1:${ISO_BACKEND_PORT}/api/v1`;

/** 写配置用例的页面基址（替换原硬编码的 http://localhost:5173） */
export const ISO_PAGE = `http://localhost:${ISO_VITE_PORT}`;

const sleep = (ms: number): Promise<void> =>
  new Promise((r) => setTimeout(r, ms));

/** 真配置只读拷一份作模板；真配置缺失时给最小骨架，避免整批用例因「配置文件不存在」集体全红 */
function makeTempConfig(repoRoot: string): string {
  const real = join(repoRoot, 'config', 'config.yaml');
  const dir = mkdtempSync(join(tmpdir(), 'omniagent_e2e_cfg_'));
  const target = join(dir, 'config.yaml');
  if (existsSync(real)) copyFileSync(real, target);
  else
    writeFileSync(
      target,
      'ai:\n  model_ref:\n    provider: sensenova\n    model: sensenova-6.8-flash-lite\n',
      'utf8'
    );
  return target;
}

let cfgDir: string | undefined;
let cfgPath: string | undefined;

/**
 * 隔离配置副本的真实路径 —— 供 spec 里「断言写入落盘」的 readFileSync 用。
 * 必须替换原先硬编码的 F:\...\config\config.yaml：那既是 AGENTS.md 明禁的硬编码真路径，
 * 也让断言只能盯真配置（等于把「写真配置」当成验收标准）。
 * 副本里 provider/api_key/models 与真配置一致，断言语义不变，只是落点换成副本。
 */
export const isoConfigPath = (): string => {
  if (!cfgPath)
    throw new Error(
      '[E2E] 隔离配置尚未初始化：isoConfigPath() 只能在 startIsolatedEnv() 之后调用（spec 的 beforeAll 里）。'
    );
  return cfgPath;
};

/** 起一个隐藏窗口的 cmd 进程（不经 npm，直接跑命令），返回 PID */
function spawnHidden(projectDir: string, cmdLine: string): number {
  const out = ps(
    `$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',('cd /d ${projectDir} && ' + '${cmdLine}') -WindowStyle Hidden -PassThru; $p.Id`
  );
  return Number(out);
}

/**
 * 拉起隔离三进程栈并等到全部就绪。
 * @param frontendDir frontend 目录（用于定位 vite 与 api-proxy）
 */
export async function startIsolatedEnv(frontendDir: string): Promise<void> {
  const repoRoot = resolve(frontendDir, '..');
  const backendDir = join(repoRoot, 'backend');

  for (const p of [ISO_BACKEND_PORT, ISO_PROXY_PORT, ISO_VITE_PORT]) {
    if (waitPortUp(p))
      throw new Error(
        `[E2E] 隔离环境端口 ${p} 已被占用。请先释放（或改 isolated-env.ts 端口）再跑写配置用例。`
      );
  }

  const cfg = makeTempConfig(repoRoot);
  cfgPath = cfg;
  cfgDir = cfg.slice(0, cfg.lastIndexOf('\\') || cfg.lastIndexOf('/'));
  mkdirSync(join(frontendDir, 'e2e_case', 'output'), { recursive: true });

  // ① 隔离后端：唯一改道入口 OMNIAGENT_CONFIG_PATH（app/config.py get_config_path 认它）
  spawnHidden(
    backendDir,
    `set OMNIAGENT_CONFIG_PATH=${cfg}&& python -m uvicorn app.main:app --host 127.0.0.1 --port ${ISO_BACKEND_PORT}`
  );

  // ② 独立代理 → 隔离后端（api-proxy.ts 认 PROXY_TARGET/PROXY_PORT；两者都必须设，
  //    漏 PROXY_PORT 会让它回落默认 9000 —— 那正是跑任务 spec 的共享代理端口，会被抢占）
  spawnHidden(
    frontendDir,
    `set PROXY_TARGET=http://127.0.0.1:${ISO_BACKEND_PORT}&& set PROXY_PORT=${ISO_PROXY_PORT}&& set PROXY_LOG=e2e_case/output/api-proxy-isolated.log&& node e2e_case/api-proxy.ts`
  );

  // ③ 独立 vite（/api → 9001）
  spawnHidden(
    frontendDir,
    'npx vite --config e2e_case/vite.isolated.config.ts'
  );

  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (
      waitPortUp(ISO_BACKEND_PORT) &&
      waitPortUp(ISO_PROXY_PORT) &&
      waitPortUp(ISO_VITE_PORT)
    )
      return;
    await sleep(500);
  }
  throw new Error(
    `[E2E] 隔离环境 120s 未就绪（后端 ${ISO_BACKEND_PORT} / 代理 ${ISO_PROXY_PORT} / vite ${ISO_VITE_PORT}）`
  );
}

/** 拆掉三进程栈并删临时配置副本（真配置全程未被写入，无需也无法「还原」） */
export async function stopIsolatedEnv(): Promise<void> {
  for (const p of [ISO_VITE_PORT, ISO_PROXY_PORT, ISO_BACKEND_PORT]) {
    killPort(p);
  }
  for (const p of [ISO_VITE_PORT, ISO_PROXY_PORT, ISO_BACKEND_PORT]) {
    const deadline = Date.now() + 15_000;
    while (Date.now() < deadline && !waitPortDown(p)) await sleep(300);
  }
  if (cfgDir) {
    rmSync(cfgDir, { recursive: true, force: true });
    cfgDir = undefined;
  }
  cfgPath = undefined;
}

/** 供 spec 直接复用的 beforeAll/afterAll 组合（幂等：未起时 stop 也安全） */
export const isolatedEnvHooks = (
  frontendDir: string
): {
  beforeAll: () => Promise<void>;
  afterAll: () => Promise<void>;
} => ({
  beforeAll: () => startIsolatedEnv(frontendDir),
  afterAll: () => stopIsolatedEnv(),
});

// 兜底导出：个别场景需直接确认 uvicorn 可用（与 process.ts 的 ps 同源，不重复实现）
export const pythonAvailable = (): boolean => {
  try {
    execFileSync('python', ['--version'], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
};
