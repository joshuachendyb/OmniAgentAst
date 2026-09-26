/**
 * e2e_front_lib/auth.ts — 前端 E2E 访问口令注入
 *
 * 编辑历史:
 *   2026-09-26 - 小欧 - [72]第九章(9.6-3) 新建
 *
 * [72]第九章(9.6-3) - 后端给 12 个 router 挂了统一 token 鉴权（/health 豁免），
 *   若前端 E2E 不带口令，**全部 8 个前端 E2E 会 401 失败**。按 9.6-3 要求
 *   "统一在 e2e_front_lib 注入，不逐个用例改" —— 故在此提供单一入口。
 *
 * 为什么只需预置 localStorage：
 *   页面请求路径是 浏览器页面(localStorage) → client.ts 拦截器附加 `Authorization: Bearer <token>`
 *   → e2e_case/api-proxy.ts 原样透传全部请求头 → 后端校验通过。
 *   api-proxy 的 `headers: { ...req.headers }` 已透传 Authorization，故**代理无需改动**。
 *
 * token 来源：环境变量 OMNIAGENT_API_TOKEN（与后端同一份，保证前后端一致）。
 * 后端未启用鉴权（OMNIAGENT_REQUIRE_AUTH=0）时不注入也无害。
 */
import type { Page } from '@playwright/test';

/** 取 E2E 用的访问口令（环境变量优先）。未设置返回空串。 */
export const getE2eToken = (): string =>
  (process.env.OMNIAGENT_API_TOKEN || '').trim();

/**
 * 在页面加载前预置访问口令（写入 localStorage 的 omniagent_auth，与
 * client.ts 的 getAccessToken 读取结构严格对称）。
 *
 * 用 addInitScript 而非 page.evaluate：前者在任何页面脚本执行前注入，
 * 避免首屏请求（模型列表/设置等）在 token 写入前就发出而 401。
 */
export const injectAuthToken = async (page: Page): Promise<boolean> => {
  const token = getE2eToken();
  if (!token) {
    // 后端若已启用鉴权，用例会集体 401；显式提醒避免误判为"用例失败"
    // eslint-disable-next-line no-console
    console.warn(
      '[E2E][第九章] 未设置 OMNIAGENT_API_TOKEN：页面请求将不带 Authorization。' +
        '若后端已启用 token 鉴权，全部前端 E2E 会 401。'
    );
    return false;
  }
  await page.addInitScript((t: string) => {
    try {
      // 2026-09-26 - 小欧 - [72]三堂会审后修正（与 client.ts setAccessToken 同一修法）:
      //   按原包络回写，不把 zustand persist 的 {"state":{...}} 展平。
      //   注：此处逻辑与 client.ts 重复是**被迫的** —— addInitScript 回调会被 Playwright
      //   序列化后在浏览器执行，不能引用外部 import 的函数，只能内联（DRY 在此让位给约束）。
      const raw = window.localStorage.getItem('omniagent_auth');
      if (raw) {
        try {
          const p: unknown = JSON.parse(raw);
          if (p && typeof p === 'object' && !Array.isArray(p)) {
            const obj = p as Record<string, unknown>;
            if (obj.state && typeof obj.state === 'object') {
              window.localStorage.setItem(
                'omniagent_auth',
                JSON.stringify({
                  ...obj,
                  state: {
                    ...(obj.state as Record<string, unknown>),
                    accessToken: t,
                  },
                })
              );
              return;
            }
            window.localStorage.setItem(
              'omniagent_auth',
              JSON.stringify({ ...obj, accessToken: t })
            );
            return;
          }
        } catch {
          /* 解析失败则走全新写入 */
        }
      }
      window.localStorage.setItem('omniagent_auth', JSON.stringify({ accessToken: t }));
    } catch {
      /* ignore */
    }
  }, token);
  return true;
};
