import { test, expect } from '@playwright/test';
import {
  activeTaskId,
  API_BASE,
  attachStreamDiag,
  ChatPage,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  printDiag,
  readLogSince,
  sessionIdFromUrl,
  startNormalUiEnv,
  statusOfTask,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * E2E-16 新会话·任务执行中·按 F5·验刷新只附着不重发
 *
 * 做什么: 发一条长任务, 等它执行中, 按 F5, 等它跑完。
 * 断什么: 刷新最容易出的错是**把在飞任务当成新任务重发一次** —— 同一段输出出现两遍、
 *   token 记两遍、DB 里多出一个重复任务。本 case 量的就是"刷新后没有新的 POST"。
 * 判据: ①刷新前后 POST /chat/stream 次数相同(没重发)
 *      ②该会话 task 数不翻倍(没建重复任务)
 *      ③该 task 最终 status = completed(附着后还能正常跑完)
 *      ④最终正文含任务关键词且非空
 *
 * 编辑历史:
 *   2026-09-30 小欧 - 第六章 P9 原判据引 useSSE.ts 的 isProcessingRef, 该文件已删
 *     (SSE 单源化重构), 被 chatStreamStore 取代, 防重落在 releaseUnsubscribed 宽限期
 *     与 _allocator 幂等上。故只断言可观测行为(POST 次数), 不依赖已不存在的行号。
 *   2026-10-01 小欧 - **删掉原场景A(空会话刷新不自动POST)与场景C(连点5次只1次POST)**。
 *     删除理由(北京老陈: 假通过没有价值):
 *       A —— 判据 `hasNoTaskNotice` 拿 UI 文案("尚未发送"等)当产品行为的证据, 文案一改就红,
 *           与产品行为无关; 且前置要靠 `/新会话|新建会话/` 猜入口找空会话, 找不到就抛错。
 *       C —— 真正测不到它声称要断的 bug: 连点时按钮早已被 React 换成"停止"钮,
 *           外面还套 `.catch(() => undefined)` 吞掉失败, 后面 4 次**根本没点着发送**,
 *           POST=1 自然成立(假通过); 且末尾算出的 task 数只 console.log, 一个断言都没有。
 *     现只留「执行中刷新不重发 POST」—— 这条用 14(只查 GET 续传)和 17(只查挂对任务)都验不到,
 *     不可替代。
 * 铁规: AGENTS.md 禁止 commit 测试文件。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

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

/**
 * 2026-10-01 小欧 编辑历史: 本文件原有本地 helper `statusOfTask`(与 lib/task-status 逐字相同)
 *   与 `activeTaskId`(与 lib/page-anchors 逐字相同), 均已删除改为引用公用库。
 *   三份完全相同的实现 = 选择器一改必漏一处, 漏处那个 case 悄悄读空串 → 假红/假绿。
 */

test.describe('[63] P9 执行中刷新 · 只附着不重发 POST', () => {
  test('新会话长任务执行中按F5: 无新POST/task不翻倍/终态completed', async ({
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

    // ══ 发一条长活期任务, 等它执行中 ══
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
    // 2026-10-01 小欧 [1] 自查新增: 取该会话里正在跑的 task_id, 供终态断言按 id 精确定位。
    //   不像 latest_task_id 那样"取最新的" —— 一旦挑错任务, 终态断言会跟着假通过。
    const taskIdOf16 = await activeTaskId(page);
    expect(taskIdOf16).toBeTruthy();

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
    // 北京老陈 2026-10-01: 刷新前先读顶栏计数器基线, 刷新后与它比 ——
    //   判"step 还在不在正常显示、计数器还在不在正常计数"。
    //   本 case 的核心是"刷新不重发 POST / 不新建 task", 但**刷新后 step 归零或不显示**
    //   同样是老陈截图那类现象, 一并守住(口径与 14/15/17 一致, 共用 lib/step-counter)。
    const counterBefore = await readStepCounter(page);
    console.log(
      `[E2E] 刷新前计数器: ${counterBefore ? `轮=${counterBefore.rounds} 步=${counterBefore.steps}` : '(读不到)'}`
    );
    if (!counterBefore) {
      throw new Error(
        `[E2E] 刷新前读不到顶栏计数器 —— step 本来就没显示。不当通过处理`
      );
    }
    expect(counterBefore.steps).toBeGreaterThan(0);

    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    await page.waitForTimeout(6000);

    const postAfterB = countStreamPost(diag.streamReqs);
    console.log(
      `[E2E]: 刷新前后 POST /chat/stream ${postBaseB} -> ${postAfterB}`
    );
    // ④ 刷新只附着, 不得重发 POST(重发=建重复任务, 同一段输出两遍/token记两遍)
    // 2026-10-01 小欧 [1] 硬判据整改: 原 `expect(postAfterB).toBe(postBaseB)` 本身是硬的, 保留。
    expect(postAfterB).toBe(postBaseB);
    // ⑤ 该会话 task 数必须**恰好 1**。
    //   2026-10-01 小欧 [1] 硬判据整改: 原写 `toBeLessThanOrEqual(1)` —— 变成 0 也放过,
    //   而"刷新后任务整个丢了"(找不到在飞任务、退回 idle 草稿态)恰恰是 product bug,
    //   却能绿过去。核实 chatStreamStore.ts:677-715 resume 路径: 任务在飞且在 300s 窗内
    //   → findLiveTask 命中 → attach + resumeStreamRequest(只发 GET 续传, 不建任务),
    //   代码里**没有"刷新自动重建任务"的路径**, 故正常落点必然是 1, 不是 0 也不是 2。
    const tasksAfterB = await taskCountOf(liveSession);
    console.log(`[E2E] 该会话 task 数=${tasksAfterB}(必须恰好1)`);
    expect(tasksAfterB).toBe(1);
    // ⑤b 且这个 task 必须还是原来那个(没被换成别的 task)
    expect(await statusOfTask(liveSession, taskIdOf16)).toBe('executing');

    // 等任务终态(证明附着后仍能正常跑完)
    await chat.waitDone(420_000);
    // 2026-10-01 小欧 [1] 自查修复: waitDone 返回后不能直接断言正文含关键词 ——
    //   若任务是 failed 态, 正文是错误文案, 关键词断言会红, 但看不出"是任务失败还是断言写错",
    //   根因被掩盖。这里先查该 task 的 DB 权威 status, 落到 failed 则打日志并显式报错。
    const statusB16 = await statusOfTask(liveSession, taskIdOf16);
    console.log(`[E2E]: 该任务终态 status=${statusB16}`);
    if (statusB16 === 'failed' || statusB16 === 'cancelled') {
      const errLines = readLogSince(BLOG, logBase)
        .split('\n')
        .filter((l) => l.includes(taskIdOf16) && /ERROR|失败|error/i.test(l))
        .slice(-20);
      for (const l of errLines) console.log(`[E2E][DIAG] ${l.slice(0, 200)}`);
      throw new Error(
        `[E2E] 附着后任务终态为 ${statusB16}(非 completed)。` +
          `后端相关日志行数=${errLines.length}，见上方 DIAG`
      );
    }
    expect(statusB16).toBe('completed');
    const finalText = await chat.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('近地小行星采矿工程');

    // 【北京老陈 2026-10-01 要求】刷新后 step 正常显示 + 计数器正常计数。
    //   与 14/15/17 同口径(共用 lib/step-counter)。判据:
    //   ① 刷新后计数器读得到 —— 读不到 = step 不显示 = 不过
    //   ② 轮/步都 >= 刷新前    —— 变小 = 累计被清零 = 不过
    //   ③ 步数 > 0              —— 显示 0 等于页面像从头开始
    const counterAfter = await readStepCounter(page);
    console.log(
      `[E2E] 刷新后计数器: ${counterAfter ? `轮=${counterAfter.rounds} 步=${counterAfter.steps}` : '(读不到)'}` +
        ` (刷新前 轮=${counterBefore.rounds} 步=${counterBefore.steps})`
    );
    if (!counterAfter) {
      throw new Error(
        `[E2E] 刷新后读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 刷新后未渲染', counterBefore, null) +
          ` —— 不当通过处理`
      );
    }
    expect(counterAfter.rounds).toBeGreaterThanOrEqual(counterBefore.rounds);
    expect(counterAfter.steps).toBeGreaterThanOrEqual(counterBefore.steps);
    expect(
      counterAfter.steps,
      counterFailMsg(
        '刷新后步数为 0 —— 累计计数没恢复, 页面看起来像从头开始',
        counterBefore,
        counterAfter
      )
    ).toBeGreaterThan(0);

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
