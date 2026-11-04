import type { Page } from '@playwright/test';

/**
 * 顶栏信息带(TaskInfoBar)「轮数 / 步骤数」计数器读取 —— 小欧 2026-10-01
 *
 * 【为什么抽到 lib】
 *   fre2e_14 / 15 / 16 / 17 四个 case 都要判同一件事(北京老陈 2026-10-01 要求):
 *   **切走/刷新回到任务页后, 那个计数器还在不在正常计数、step 还在不在正常显示。**
 *   计数器只此一处渲染, 选择器与正则口径必须四份一致 —— 各自抄一遍必然走偏。
 *   故抽到公用库, 四处共用同一实现。
 *
 * 【锚点与口径 — 核实自源码, 非猜测】
 *   容器 class: `.taskinfo-bar`（TaskInfoBar.tsx:285）
 *   计数器文本随响应式分三档(同一组件 TaskInfoBar.tsx:483-501), 字段相同:
 *     宽档: `轮数: N · 步骤: M`
 *     中档: `轮:N · 步:M`（外面套 Tooltip, title 里是完整版）
 *     窄档: `耗时 h:mm:ss·轮:N · 步:M`
 *   故一条正则同时吃三档:
 *     /轮(?:数)?\s*:\s*(\d+)/   → 轮数
 *     /步(?:骤)?\s*:\s*(\d+)/   → 步骤数
 *   (中档被 Tooltip 包裹时 innerText 仍含内部文本, 故仍能取到)
 *
 * 【读不到时返回 null — 绝不返回 0】
 *   返回 0 会把「计数器整个没了 / step 不显示」伪装成「当前计数为 0」, 那是**假通过**。
 *   返回 null 交调用方显式判红。
 */

export interface StepCounter {
  /** LLM 调用轮数(UI 文案: 轮数 / 轮) */
  rounds: number;
  /** 步骤数(UI 文案: 步骤 / 步) */
  steps: number;
  /** 顶栏信息带原始文本, 供失败时打证据 */
  raw: string;
}

/**
 * 读一次顶栏「轮数/步骤数」。
 * 容器不存在或文本形态变了 → 返回 null(交调用方判红, 不静默当 0)。
 */
export const readStepCounter = async (
  page: Page
): Promise<StepCounter | null> => {
  const bar = page.locator('.taskinfo-bar');
  if ((await bar.count()) === 0) return null;
  const raw = (await bar.first().innerText()).replace(/\s+/g, ' ');
  const r = raw.match(/轮(?:数)?\s*:\s*(\d+)/);
  const s = raw.match(/步(?:骤)?\s*:\s*(\d+)/);
  if (!r || !s) return null;
  return { rounds: Number(r[1]), steps: Number(s[1]), raw };
};

/**
 * 轮询等计数器**继续往上走**, 返回最后一次读到的值。
 *
 * 用于「切走/刷新回来后, 页面上的数字还在不在动」—— 后端 status 是 executing
 * 只说明任务在跑; 页面上看得到数字在涨, 才是 SSE 仍在推送的正面证据。
 *
 * @param fromRounds 起点轮数(通常是切走/刷新**之前**读到的基线)
 * @param fromSteps  起点步数
 * @param timeoutMs  最多等多久; 超时返回最后一个实测值(由调用方决定是否判红)
 */
export const waitCounterIncreases = async (
  page: Page,
  fromRounds: number,
  fromSteps: number,
  timeoutMs: number
): Promise<StepCounter | null> => {
  const deadline = Date.now() + timeoutMs;
  let last = await readStepCounter(page);
  while (Date.now() < deadline) {
    await page.waitForTimeout(1000);
    const cur = await readStepCounter(page);
    if (!cur) return last;
    last = cur;
    if (cur.rounds > fromRounds || cur.steps > fromSteps) return cur;
  }
  return last;
};

/**
 * 读顶栏「耗时」(TaskInfoBar 的秒表文本, 形如 `耗时 00:07:43`)。
 *
 * 【为什么单独抽一个 —— 北京老陈 2026-10-01 肉眼发现「第二个任务计时一直不动」】
 *   计时与轮/步**不同源**:
 *     · 轮数/步骤数 = 后端 `stats` 帧的 step_count / 轮次, 跨业务步骤才变;
 *     · 耗时 = TaskInfoBar `shownElapsed`, 走哪条路由 `selectedDetail` 决定
 *       (useTaskSelection.ts:52: activeTaskId !== serverTaskId → 拉 detail → 用后端 duration;
 *        相等 → selectedDetail=null → 走本地 setInterval 秒表)。
 *   即"轮/步在动而耗时不动"是**可能**的组合, 两者必须分别验, 不能互相代替。
 *
 * 读不到 → 返回 null, 交调用方显式判红(不返回 0 假装"没耗时")。
 */
export const readElapsed = async (page: Page): Promise<string | null> => {
  const bar = page.locator('.taskinfo-bar');
  if ((await bar.count()) === 0) return null;
  const raw = (await bar.first().innerText()).replace(/\s+/g, ' ');
  // 宽/中档只显「轮数: N · 步骤: M」, 无耗时; 窄档/极窄档才带「耗时 mm:ss / hh:mm:ss」
  const m = raw.match(/耗时\s*(\d{1,2}:\d{2}(?::\d{2})?)/);
  return m ? m[1] : null;
};

/**
 * 轮询等耗时文本**发生变化**(即秒表真的在走), 返回前后两次读数。
 *
 * 用途: 判「任务还在跑」最直接的正面证据 —— 后端在推帧、界面在走表。
 * 超时未变 → 返回 null, 由调用方决定判红。
 *
 * @param before 起点耗时文本(通常是动作发生前读到的)
 * @param timeoutMs 最多等多久
 */
export const waitElapsedAdvances = async (
  page: Page,
  before: string | null,
  timeoutMs: number
): Promise<{ before: string | null; after: string | null }> => {
  const deadline = Date.now() + timeoutMs;
  let last = await readElapsed(page);
  while (Date.now() < deadline) {
    await page.waitForTimeout(1000);
    last = await readElapsed(page);
    if (last && before && last !== before) return { before, after: last };
  }
  return { before, after: last };
};

/**
 * 截一条「计数器」判据的失败说明, 统一口径, 免得各 case 自己拼文字。
 * 返回可直接传给 expect(x, msg) 的字符串。
 */
export const counterFailMsg = (
  what: string,
  before: StepCounter | null,
  after: StepCounter | null
): string =>
  `${what} —— 计数器读数: ` +
  `前=${before ? `轮${before.rounds}/步${before.steps}` : '(读不到)'} ` +
  `后=${after ? `轮${after.rounds}/步${after.steps}` : '(读不到)'}`;
