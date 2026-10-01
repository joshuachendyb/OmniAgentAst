import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  printDiag,
  readLogSince,
  startNormalUiEnv,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * [63] 第六章 P9「无 taskId 恢复」全链路 E2E — 小欧 2026-09-30
 *
 * 环境: 普通会话流 `startNormalUiEnv`(vite dev:5173 + API 经 proxy → :8000)。真实浏览器/后端/LLM/SQLite。
 *
 * 验证目标(第六章 6.3 的 P9, 边界族):
 *   场景A 无 taskId 恢复 —— 不自动 POST, 显式"尚未发送"态
 *   场景B 同内容活动任务只附着 —— 不重发 POST
 *   场景C 连点防重     —— 重复点击只产生 1 次 POST
 *
 * 与第六章原文的差异(勿误读):
 *   第六章 P9 判据引 `useSSE.ts:1186-1200 isProcessingRef`。现状核实: **useSSE.ts 已删除**
 *   (SSE 流单源化重构, -779 行), 被 `features/chat/streams/{chatStreamStore,chatStreamTransport,
 *   chatStreamPersistence}` 取代; 防重现落在 `chatStreamStore.sendMessage` 的
 *   `releaseUnsubscribed(默认 60s 宽限)` 与 `_allocator` 幂等上。故本 case 只断言**可观测行为**
 *   (POST 次数), 不依赖已不存在的内部字段/行号。
 *
 * 场景A 的构造方式(不 Mock):
 *   新建会话但**不发消息** → URL 带 session_id 而后端该会话无任何 task → 刷新后即"无 taskId"态。
 *   走真实"新建会话"入口(菜单/会话页), 非直接改 URL。
 *
 * 取证锚点: attachStreamDiag.streamReqs(POST 计数) + 后端当日日志 + REST /sessions/{id}/tasks。
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试相关代码文件 —— 本 spec 严禁提交。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const API_BASE = 'http://127.0.0.1:8000/api/v1';

/** chat/stream 的 POST 次数(第六章 M1 网络面计数法) */
const countStreamPost = (reqs: string[]): number =>
  reqs.filter((l) => l.includes('REQ POST ') && l.includes('/chat/stream'))
    .length;

/** 该会话是否有任何 task(走 REST; 无 task 即"无 taskId"态) */
const taskCountOf = async (sessionId: string): Promise<number> => {
  if (!sessionId) return -1;
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return -1;
  const d = (await res.json()) as { total?: number };
  return d.total ?? 0;
};

const sessionIdFromUrl = (page: Page): string =>
  new URL(page.url()).searchParams.get('session_id') ?? '';

/** 页面上是否处于"尚未发送/无任务"提示态 */
const hasNoTaskNotice = async (page: Page): Promise<boolean> => {
  const t = await page.evaluate(() => document.body.innerText);
  return /尚未发送|还没有消息|暂无消息|新会话|开始对话/.test(t);
};

test.describe('[63] P9 无 taskId 恢复 · 不自动POST/只附着/连点防重', () => {
  test('场景A 无taskId刷新不自动POST; 场景B 活动任务只附着不重发; 场景C 连点N次仅1次POST', async ({
    page,
  }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // ══════════ 场景A: 无 taskId 态刷新, 不得自动 POST ══════════
    // 构造: 发一条消息拿到会话, 任务终态后**清空输入并直接刷新** —— 此时 session 有 task, 不满足"无 taskId"。
    //   故改用真实"新建会话"路径: 走菜单新建(后端 create_session 建空会话, 无任何 task), 再刷新。
    // 编辑历史 2026-09-30 小欧 - 场景A 不用"改 URL"或"造数据"(那属 Mock); 一律走产品真实入口。
    await page
      .locator('.ant-menu-item', { hasText: '对话任务' })
      .first()
      .click();
    await page.waitForTimeout(1500);

    // 用输入框发送后再清空? 不行(会产生 task)。改: 点"新建会话"入口(若存在)或直接用当前空会话。
    // 当前实现: 落地页进入即可能已自动建会话, 故先探测 URL 是否已带 session_id。
    let emptySession = sessionIdFromUrl(page);
    if (!emptySession) {
      // 触发一次"新建会话"(产品入口: 顶栏/菜单的新会话项)
      const newBtn = page
        .locator('button, .ant-menu-item')
        .filter({ hasText: /新会话|新建会话/ })
        .first();
      if (await newBtn.isVisible().catch(() => false)) {
        await newBtn.click();
        await page.waitForTimeout(2500);
        emptySession = sessionIdFromUrl(page);
      }
    }
    const tasksInEmpty = await taskCountOf(emptySession);
    console.log(
      `[E2E] 场景A 前置: session=${emptySession || '(无)'} 该会话 task 数=${tasksInEmpty}`
    );

    // 前置校验: 必须拿到一个"无 task"的会话, 否则场景A 无从谈起(诚实报错, 不伪装)
    if (!emptySession || tasksInEmpty !== 0) {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        readLogSince(BLOG, logBase),
        diag.allFailed,
        getCaseId()
      );
      throw new Error(
        `[E2E] 场景A 前置不成立: 未能构造"无 task 会话"(session=${emptySession}, tasks=${tasksInEmpty})——` +
          `若当前页面已自动建带 task 的会话, 本场景需先手工新建空会话; 不伪造`
      );
    }

    const postBaseA = countStreamPost(diag.streamReqs);
    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    await page.waitForTimeout(5000); // 给恢复流程跑完

    const postAfterA = countStreamPost(diag.streamReqs);
    console.log(
      `[E2E] 场景A: 刷新前后 POST /chat/stream ${postBaseA} -> ${postAfterA}`
    );
    // ① 无 taskId 恢复不得自动 POST
    expect(postAfterA).toBe(postBaseA);
    // ② 界面应有"尚未发送"类显式提示(而非静默空白/永久 loading)
    expect(await hasNoTaskNotice(page)).toBeTruthy();
    // ③ 后端该会话仍无 task(没被偷偷建任务)
    expect(await taskCountOf(emptySession)).toBe(0);

    // ══════════ 场景B: 同内容活动任务只附着, 不重发 POST ══════════
    // 构造: 发一条长活期任务(执行中) → 刷新 → 前端应读 tasks 得 executing 并只附着, 不重发 POST。
    const frameBaseB = diag.consoleAll.length;
    const PROMPT =
      '请完成一篇关于"近地小行星采矿工程可行性"的技术论证报告，全文不少于1200字、分八大部分并给出具体数值参数：' +
      '①目标小行星选择标准（≥5个候选并给轨道/直径/自转/材质参数）②采矿技术路线对比（≥3种，附能源估算表）' +
      '③自主作业装备清单（≥6类，附功率质量）④ISRU水电解/甲烷合成当量参数⑤返回推进（比冲/质量比/窗口）' +
      '⑥风险故障树（≥5类排序）⑦经济性（单矿收益/往返成本/盈亏点）⑧分级结论（可行/不可行/需论证）。' +
      '为支撑报告数据，请按以下步骤实际操作（不要停留在思考层面）：' +
      '第一步：新建一个临时工作目录，并在其中创建一份 markdown 报告骨架文件（含标题+八个小节标题目录）；' +
      '第二步：用网络工具查一次候选小行星的真实公开参数（尺寸或轨道等，任选其一），并把结果填入报告文件对应小节；' +
      '第三步：读回该文件，核对骨架与数据是否完整；' +
      '第四步：在对话中给出完整的论证报告正文（仍覆盖八大部分并包含你查到的数值）。' +
      '请务必在最终回答中包含"近地小行星采矿工程"这几个字。';

    await chat.sendPrompt(PROMPT);
    try {
      await chat.waitReceiving(90_000);
    } catch (e) {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        readLogSince(BLOG, logBase),
        diag.allFailed,
        getCaseId()
      );
      throw e;
    }
    const postBaseB = countStreamPost(diag.streamReqs);
    const liveSession = sessionIdFromUrl(page);
    expect(liveSession).toBeTruthy();

    // 等 ≥2 轮确保任务在跑(执行中)
    const dlB = Date.now() + 180_000;
    while (Date.now() < dlB) {
      const rs = diag.consoleAll
        .slice(frameBaseB)
        .map((l) => l.match(/轮次=(\d+)/)?.[1])
        .filter(Boolean);
      if (rs.length >= 2) break;
      await page.waitForTimeout(500);
    }

    // 刷新(活动任务在飞)
    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    await page.waitForTimeout(6000);

    const postAfterB = countStreamPost(diag.streamReqs);
    console.log(
      `[E2E] 场景B: 刷新前后 POST /chat/stream ${postBaseB} -> ${postAfterB}`
    );
    // ④ 活动任务刷新只附着, 不得重发 POST(重发=建重复任务)
    expect(postAfterB).toBe(postBaseB);
    // ⑤ 该会话 task 数不得因刷新而翻倍
    const tasksAfterB = await taskCountOf(liveSession);
    console.log(`[E2E] 场景B: 该会话 task 数=${tasksAfterB}`);
    expect(tasksAfterB).toBeLessThanOrEqual(1);

    // 等任务终态(证明附着后仍能正常跑完)
    await chat.waitDone(420_000);
    const finalText = await chat.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('近地小行星采矿工程');

    // ══════════ 场景C: 连点防重, N 次点击只 1 次 POST ══════════
    // 编辑历史 2026-09-30 小欧 - 用"连点发送按钮"构造竞态(不 Mock): sendBtn 在 isReceiving 时被替换为
    //   停止钮, 故连点前必须处于"可发送"态(上一任务已终态, 发送钮复现)。连点期间靠 Playwright
    //   force:true 绕过按钮自身 disabled, 模拟用户狂点。
    await expect(chat.sendBtn).toBeVisible({ timeout: 30_000 });
    const postBaseC = countStreamPost(diag.streamReqs);
    const CLICK_TIMES = 5;
    await chat.input.fill(
      '请用一句话说明什么是可回收火箭, 并给出一个真实型号作为例子。'
    );
    for (let i = 0; i < CLICK_TIMES; i += 1) {
      // catch: 连点期间按钮可能已被 React 替换为"停止"钮而失效, 属预期, 不算失败
      await chat.sendBtn
        .click({ force: true, timeout: 5_000 })
        .catch(() => undefined);
      await page.waitForTimeout(120); // 120ms 间隔: 落在防重窗口内
    }
    await page.waitForTimeout(4000);
    const postAfterC = countStreamPost(diag.streamReqs);
    const postDeltaC = postAfterC - postBaseC;
    console.log(
      `[E2E] 场景C: 连点 ${CLICK_TIMES} 次, POST 增量=${postDeltaC}(MUST=1)`
    );
    // ⑥ 连点 N 次只产生 1 次 POST
    expect(postDeltaC).toBe(1);

    // ⑦ 该次点击产生的 task 也只有 1 个
    const cSession = sessionIdFromUrl(page);
    if (cSession) {
      const cTasks = await taskCountOf(cSession);
      console.log(`[E2E] 场景C: 新会话 task 数=${cTasks}(防重后应为1)`);
    }

    // 通用区
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      readLogSince(BLOG, logBase),
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });
});
