/**
 * e2e_front_lib/global-setup.ts — Playwright globalSetup：统一预置访问口令
 *
 * 2026-09-27 - 小欧 - 落地
 *
 * 后端给 12 个 router 挂了统一 token 鉴权（仅 /health 豁免），前端 E2E 不带口令会全 401。
 * auth.ts 的 injectAuthToken 早已写好但全仓零调用，即「统一注入」其实没落地。
 *
 * 用 storageState 而非逐 spec 调 injectAuthToken：后者要 8 遍 beforeEach 样板（违反 DRY）；
 * storageState 由 Playwright 每次导航前自动应用，效果等价且 spec 零改动。
 *
 * token 来源：环境变量 OMNIAGENT_ACCESS_TOKEN（与后端同一份）。未设置时写**空 state** 而非跳过 ——
 * storageState 指向固定路径，文件缺失会让 Playwright 直接报错退出，那才是真正的退化。
 */
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

// 2026-09-27 小欧 - 用 process.cwd() 而非 __dirname：Playwright 加载 .ts globalSetup 时按 CJS
//   还是 ESM 处理取决于 package.json 的 type，__dirname 在 ESM 下未定义会直接抛错（实跑踩过）。
const STATE_PATH = resolve(process.cwd(), 'e2e_front_lib', '.auth-state.json');

/** 与 client.ts 的 zustand persist 包络严格对称：{state:{accessToken}} */
const buildState = (token: string) => ({
  cookies: [],
  origins: [
    {
      origin: 'http://localhost:5173',
      localStorage: [
        {
          name: 'omniagent_auth',
          value: JSON.stringify({ state: { accessToken: token }, version: 0 }),
        },
      ],
    },
  ],
});

const EMPTY_STATE = { cookies: [] as unknown[], origins: [] as unknown[] };

export default async function globalSetup(): Promise<void> {
  const token = (process.env.OMNIAGENT_ACCESS_TOKEN || '').trim();
  if (!existsSync(dirname(STATE_PATH)))
    mkdirSync(dirname(STATE_PATH), { recursive: true });
  if (!token) {
    // 2026-09-27 小欧 - 仍写空 state（不是跳过）：playwright.config 的 storageState 指向固定路径，
    //   文件不存在时 Playwright 会直接报错退出 —— 那样"没设口令"就从"照常跑"变成"跑不起来"，
    //   属功能退化。写空 state 才能让两种情况都只是"不带 Authorization"而非"启动失败"。
    writeFileSync(STATE_PATH, JSON.stringify(EMPTY_STATE));
    // eslint-disable-next-line no-console
    console.warn(
      '[E2E][第九章] 未设置 OMNIAGENT_ACCESS_TOKEN：页面请求将不带 Authorization。' +
        '若后端已启用 token 鉴权，全部前端 E2E 会 401。'
    );
    return;
  }
  writeFileSync(STATE_PATH, JSON.stringify(buildState(token), null, 2));
}
