import { test, expect } from '@playwright/test';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';
import {
  ChatPage,
  API_BASE,
  STATUS_NOT_FOUND,
  activeTaskId,
  attachStreamDiag,
  counterFailMsg,
  errorLinesOfTask,
  getCaseId,
  getTodayLogPath,
  injectAuthToken,
  keepBrowserOpenIfRequested,
  logBaseOf,
  printDiag,
  readLogSince,
  readStepCounter,
  sessionIdFromUrl,
  startNormalUiEnv,
  statusOfTask,
} from '../e2e_front_lib';

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

/** 该会话的 task 数(走 REST; 无 task 即"无 taskId"态) */
const taskCountOf = async (sessionId: string): Promise<number> => {
  if (!sessionId) return -1;
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return -1;
  const d = (await res.json()) as { total?: number };
  return d.total ?? 0;
};

/** 帧日志里已出现过的轮次(去重, 保序) */
const seenRounds = (all: string[], base: number): number[] => {
  const out: number[] = [];
  for (let i = base; i < all.length; i += 1) {
    const m = all[i].match(/轮次=(\d+)/);
    if (m) {
      const n = Number(m[1]);
      if (!out.includes(n)) out.push(n);
    }
  }
  return out;
};

/**
 * E2E-16 关掉页面一段时间后重新打开 · 恢复在跑任务
 *
 * 做什么: 发一条长任务 → 等它执行中 → **整个关掉那个标签页** → 等一段时间 →
 *   **新开一个标签页**进去, 看那个任务还在不在、step 还在不在数、最后能不能跑完。
 * 断什么: 「我把页面关了」不该等于「任务丢了」。关页面只是断了 SSE, 后端 agent 是
 *   独立 asyncio task, 应当继续跑到底(stream_orchestrator.py:618-620 明确设计如此);
 *   重新打开时前端应当把那个还在跑的任务重新挂上。
 *
 * 【为什么必须另起一个标签页, 不能用 page.reload()】
 *   恢复能力 100% 依赖 **sessionStorage**, 而 sessionStorage 是**标签页级**的:
 *     - 同一标签页 F5 刷新 → sessionStorage 存活 → 走 `sse_execution_steps_backup_v2_<id>`
 *       锚点续传, **无时间限制**。fre2e_14/15 守的正是这条。
 *     - 关掉标签页再新开 → sessionStorage **整体消失** → 备份判废
 *       (chatStreamStore.ts:955 `version !== 2` → 'invalid') → 走
    *       → adoptLiveTaskOrDraft。但实际**到不了**: backupLoad 返回 null → restore='invalid'
    *       → resume() 直接早退 'idle'(chatStreamStore.ts resume/restore), findLiveTask 不会被调。
    *       即"关页面重进"目前恢复不了 —— 本 case 判据③会红, 那正是要暴露的缺陷。
 *   也就是说: **最容易出问题的那条恢复路径(fre2e_14/15/16 原版/17 全部不覆盖)**。
 *   page.reload() 永远走不到它, 所以本 case 必须 close + newPage。
 *
 * 【已知产品边界 —— 本 case 在窗口内验证, 窗口外不测】
 *   findLiveTask 有 300s 窗口, 且**从 task.created_at 起算**(chatStreamStore.ts:430-431,
 *   裸字面量 300_000)。即: 任务已跑 4'50" 时关页面, 只剩 10s 窗口。
 *   本 case 关闭后只等 SHORT_CLOSE_WAIT_MS(远小于 300s), 故必在窗口内;
 *   **窗口外(恢复不了)的分支本 case 不覆盖** —— 等 5 分钟不可接受, 已在文档登记为盲区。
 *
 * 判据(逐条说清过/不过):
 *   ① 关页面前任务在飞(DB=executing)且计数器 step>0 —— 否则前提不成立, 显式报错
 *   ② 关页面后后端任务**仍在跑** —— 关页面 ≠ 停任务(这是本 case 的第一红线)
 *   ③ 新标签页必须挂到**同一个 task**(不是别的、不是空)
 *   ④ 新标签页不重建任务: 该会话 task 数仍 ===1, 且**不得发出新的 POST /chat/stream**
 *   ⑤ 新标签页 step 正常显示且不为 0(同 14/15/17 口径, 共用 lib/step-counter)
 *   ⑥ 任务最终 completed, 正文完整; failed/cancelled 打后端 ERROR 行后显式红
 *
 * 铁规: AGENTS.md 禁止 commit 测试文件。
 */

/** 关页面后到重开之间的等待时长: 要足够长到"确实过了会儿", 又远小于 300s 窗口 */
const SHORT_CLOSE_WAIT_MS = 15_000;
/** 新标签页里等任务终态的上限 */
const FINAL_WAIT_MS = 420_000;

test.describe('[1] 关掉页面一段时间后重新打开 · 恢复在跑任务', () => {
  test('执行中关掉标签页 → 等 15s → 新开标签页: 后端任务没停/挂回同一个task/step继续显示/最终completed', async ({
    page,
    context,
  }) => {
    test.setTimeout(900_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // ══ 阶段1: 在标签页①里发一条长任务, 等它执行中 ══
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
    const postBaseB = diag.streamReqs.filter(
      (l) => l.includes('REQ POST ') && l.includes('/chat/stream')
    ).length;
    const liveSession = sessionIdFromUrl(page);
    expect(liveSession).toBeTruthy();
    const taskIdOf16 = await activeTaskId(page);
    expect(taskIdOf16).toBeTruthy();

    // 等 ≥2 轮 —— 攒不够显式报错, 不把"没等到"当通过(裸 while 无断言 = 假通过)
    const dlB = Date.now() + 240_000;
    while (Date.now() < dlB) {
      const rs = seenRounds(diag.consoleAll, frameBaseB);
      if (rs.length >= 2) break;
      await page.waitForTimeout(500);
    }
    const roundsBefore = seenRounds(diag.consoleAll, frameBaseB);
    if (roundsBefore.length < 2) {
      throw new Error(
        `[E2E] 窗口错过: 关页面前仅 ${roundsBefore.length} 轮(<2)—— ` +
          `本 case 守的是「关页面时任务在飞」, 任务没进入执行中段该分支无从验证。请重跑 —— 不当通过处理`
      );
    }

    // ① 前置: 任务在飞 + step 已显示
    const statusBefore16 = await statusOfTask(liveSession, taskIdOf16);
    if (statusBefore16 !== 'executing') {
      throw new Error(
        `[E2E] 前置不成立: 关页面前 DB status=${statusBefore16} 不是 executing —— ` +
          `「关页面时任务在飞」无从验证。请重跑 —— 不当通过处理`
      );
    }
    const counterBefore = await readStepCounter(page);
    console.log(
      `[E2E] 标签页① 关前: task=${taskIdOf16} session=${liveSession} ` +
        `轮=${roundsBefore.length} 计数器=${counterBefore ? `轮${counterBefore.rounds}/步${counterBefore.steps}` : '(读不到)'}`
    );
    if (!counterBefore) {
      throw new Error(
        `[E2E] 关页面前读不到顶栏计数器 —— step 本来就没显示。不当通过处理`
      );
    }
    expect(counterBefore.steps).toBeGreaterThan(0);

    // ══ 阶段2: 整个关掉标签页①(这才是"关页面", 不是刷新) ══
    //   close() 会真断 SSE, 与用户关标签页同构。关掉后 sessionStorage 随之销毁 ——
    //   下一阶段新开标签页, sessionStorage 已空, 走的是 backupLoad 判废 → restore='invalid'
    //   → resume() 早退 'idle' 这条路(产品缺陷, 见文件头注释)。
    await page.close();
    console.log(
      `[E2E] 标签页① 已关闭(轮次=${roundsBefore.length}, 计数器步=${counterBefore.steps}) —— 等 ${SHORT_CLOSE_WAIT_MS / 1000}s 后重开`
    );

    // ② 【第一红线】关页面后后端任务仍在跑 —— 关页面 ≠ 停任务。
    //   等一段(15s)足够暴露"断开即误回收"这类缺陷: 若后端把断连当取消, 这 15s 内就会落终态。
    await new Promise((r) => setTimeout(r, SHORT_CLOSE_WAIT_MS));
    const statusAfterClose = await statusOfTask(liveSession, taskIdOf16);
    console.log(`[E2E] 关页面 ${SHORT_CLOSE_WAIT_MS / 1000}s 后 DB status=${statusAfterClose}`);
    if (statusAfterClose === STATUS_NOT_FOUND) {
      throw new Error(
        `[E2E] 关页面后查不到 task=${taskIdOf16} —— 任务被误删/误回收。` +
          `关页面只是断 SSE, 后端 agent 应继续跑(stream_orchestrator.py:618-620)`
      );
    }
    // 关页面期间不该被取消; 也不该是 failed(纯文稿任务)。
    // 允许 completed —— 若这 15s 里它自己跑完了, 那也是"没被关页面害死"的正确落点,
    // 只是下面阶段3 就抓不到"执行中恢复"了, 故要求它仍在 executing 才能继续验恢复。
    expect(
      statusAfterClose,
      `关页面 ${SHORT_CLOSE_WAIT_MS / 1000}s 后 status=${statusAfterClose} —— ` +
        `cancelled 说明关页面被当成了"停止"(红线), failed 必是产品问题`
    ).toBe('executing');

    // ══ 阶段3: 新开标签页②进去 —— sessionStorage 是空的, 只能靠 findLiveTask 找回任务 ══
    const page2 = await context.newPage();
    // injectAuthToken 用的是 addInitScript, **按 page 生效**, 新页必须重新注入
    await injectAuthToken(page2);
    const chat2 = new ChatPage(page2);
    const diag2: DiagBundle = attachStreamDiag(page2);

    await chat2.gotoChat();
    await expect(chat2.input).toBeVisible({ timeout: 60_000 });
    const urlInTab2 = page2.url();
    console.log(`[E2E] 标签页② 已打开: ${urlInTab2}`);
    // 本 case 不要求 URL 带 id —— 真实用户关页面再进来就是裸地址栏, 走
    // useChatSession 场景3(loadLatestHistoryMessages)。URL 形态不作判据, 只记日志。

    // 观察窗: 持续确认**没有新建 POST**(重进不得重建任务)。
    // 固定 sleep 只覆盖"sleep 内发生"; 若重建挂在定时器上, sleep 一过就查 → 假通过。
    const REOPEN_OBSERVE_MS = 25_000;
    const dlReopen = Date.now() + REOPEN_OBSERVE_MS;
    while (Date.now() < dlReopen) {
      await page2.waitForTimeout(1000);
      const nowPost = diag2.streamReqs.filter(
        (l) => l.includes('REQ POST ') && l.includes('/chat/stream')
      ).length;
      expect(
        nowPost,
        `重开后 ${Math.round((REOPEN_OBSERVE_MS - (dlReopen - Date.now())) / 1000)}s 内出现第 ` +
          `${nowPost} 次 POST /chat/stream(标签页①关闭前 ${postBaseB} 次) —— ` +
          `重开页面重建了任务, 同一段输出会出两遍、token 记两遍`
      ).toBe(0);
    }

    // ④ 该会话 task 数仍恰好 1, 且还是原来那个(没被换成别的 / 没整个消失)
    const tasksAfterReopen = await taskCountOf(liveSession);
    console.log(`[E2E] 重开后该会话 task 数=${tasksAfterReopen}(必须恰好1)`);
    expect(tasksAfterReopen).toBe(1);
    const statusAfterReopen = await statusOfTask(liveSession, taskIdOf16);
    if (statusAfterReopen === STATUS_NOT_FOUND) {
      throw new Error(
        `[E2E] 重开后查不到 task=${taskIdOf16} —— 任务整个丢了。不当通过处理`
      );
    }

    // ③ 挂回的是**同一个 task**(不是别的任务, 也不是空)
    //   直接轮询到它落定: activeTaskId 是异步链最后一环(读 backup → listTasks → 渲染),
    //   立即读必拿空串假红; 若真挂错了, 轮询到超时仍不等于它 → 照样红, 不会洗白。
    await expect
      .poll(async () => (await activeTaskId(page2)) !== '', {
        timeout: 60_000,
        intervals: [500],
      })
      .toBeTruthy();
    const activeAfterReopen = await activeTaskId(page2);
    console.log(`[E2E] 重开后 active=${activeAfterReopen}(应为 ${taskIdOf16})`);
    expect(
      activeAfterReopen,
      `重开后页面挂到了 task=${activeAfterReopen}, 期望 ${taskIdOf16} —— ` +
        `sessionStorage 已丢, findLiveTask 应按 executing 找回同一个任务`
    ).toBe(taskIdOf16);

    // ⑤ 新标签页 step 正常显示且不为 0(同 14/15/17 口径, 共用 lib/step-counter)
    const counterAfter = await readStepCounter(page2);
    console.log(
      `[E2E] 重开后计数器: ${counterAfter ? `轮=${counterAfter.rounds} 步=${counterAfter.steps}` : '(读不到)'}` +
        ` (关页面前 轮=${counterBefore.rounds} 步=${counterBefore.steps})`
    );
    if (!counterAfter) {
      throw new Error(
        `[E2E] 重开后读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 重开后未渲染', counterBefore, null) +
          ` —— 不当通过处理`
      );
    }
    expect(counterAfter.steps).toBeGreaterThan(0);

    // ⑥ 任务最终 completed; failed/cancelled 打后端 ERROR 行后显式红
    const dlFinal = Date.now() + FINAL_WAIT_MS;
    let statusFinal = statusAfterReopen;
    while (Date.now() < dlFinal && statusFinal === 'executing') {
      await page2.waitForTimeout(2000);
      statusFinal = await statusOfTask(liveSession, taskIdOf16);
    }
    console.log(`[E2E] 重开后任务终态 status=${statusFinal}`);
    if (statusFinal === 'failed' || statusFinal === 'cancelled') {
      const errLines = errorLinesOfTask(
        readLogSince(BLOG, logBase),
        taskIdOf16,
        20
      );
      for (const l of errLines) console.log(`[E2E][DIAG] ${l.slice(0, 200)}`);
      throw new Error(
        `[E2E] 重开后任务终态为 ${statusFinal}(本 case 未点停止)。` +
          `后端相关日志行数=${errLines.length}，见上方 DIAG`
      );
    }
    expect(statusFinal).toBe('completed');

    // 终态正文完整 —— 证明关页面重进后拿到的不是残缺/错误结果
    await chat2.waitDone(120_000).catch(() => {
      // 等不到"发送"钮复现不算致命(可能 UI 已随页面重开处于别的态), 下面用正文兜底判
    });
    const finalText = await chat2.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('近地小行星采矿工程');

    printDiag(
      diag2.streamReqs,
      diag2.reconnectLogs,
      diag2.sseErrors,
      diag2.consoleAll,
      readLogSince(BLOG, logBase),
      [...diag.allFailed, ...diag2.allFailed],
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page2);
  });
});
