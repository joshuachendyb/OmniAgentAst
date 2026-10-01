import { test, expect } from '@playwright/test';
import {
  ChatPage,
  activeTaskId,
  allTaskIdsOfApi,
  attachStreamDiag,
  counterFailMsg,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  pollTaskStatus,
  printDiag,
  readLogSince,
  readStepCounter,
  sessionIdOfTask,
  startNormalUiEnv,
  statusOfTask,
  taskStatusInList,
  waitCounterIncreases,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * 17 — 从当前(最近)会话发新任务, 任务执行中刷新浏览器
 * 小欧 2026-10-01（自 fre2e_17_old_session_refresh_resume.spec.ts 拆出）
 *
 * 【本 case 的命题 —— 北京老陈 2026-10-01 指定】
 *   「从当前的或者最新会话中发消息, 任务执行的时候执行刷新浏览器的操作」, 回来后:
 *     ① 挂的还是**刚发的新任务**(不是该会话里的旧任务, 不是空)
 *     ② 会话里的**旧任务不被误改**(仍 completed)
 *     ③ 计数器**不回退**且**继续增长**(续传真在跑)
 *     ④ 全程**不发 DELETE / cancel**
 *
 * 【与 18 的分工 —— 两个独立 case, 各自单独跑】
 *   · 18: **新建会话** + 同会话连跑 A、B + 「切页面 + 刷新」两个动作 → 覆盖"同会话多任务别挂错"
 *   · 17(本文件): **不新建会话**, 用页面自动加载的**最近会话**发一条任务 + **只刷新**一个动作
 *     → 覆盖"回到久别的会话续新任务"。两者动作数与入口都不同, 不可互相替代。
 *
 * 【阶段0 —— 旧任务由本 case 自己造, 不靠环境自带】
 *   命题②是「旧任务不被误改」, 所以会话里**必须**先有一个已落终态的历史任务。
 *   原实现进页面直接发新任务, 靠"最近会话恰好留有上一轮的任务"才成立 —— 实测命中空会话时
 *   `旧task=[]`, 命题②形同虚设, case 变成靠运气绿。现补阶段0: 先发一步即完成的短任务当 A,
 *   waitDone + pollTaskStatus 双源确认 completed(与 18 阶段1 同款, 复用同一套 helper),
 *   再发新任务 B; 并硬校验 A ∈ oldTasks, 否则命题②验的不是本 case 造的那个任务。
 *
 * 【为什么刻意不调 newSession()】
 *   老陈要的就是"从当前/最新会话" —— 真实用户关掉页面再回来, 打开就是最近会话。
 *   `gotoChat()` 裸 URL 命中 `useChatSession` 场景3(loadLatestHistoryMessages) 自动加载它,
 *   正是这条路径。**刻意不新建**, 因为新建就变成了 18 的前提。
 *
 * 【怎么定位"当前会话" —— 不猜、不靠标题反查】
 *   发消息**之前**确实拿不到 session_id(还没 task)。故顺序是:
 *     发消息 → 从左侧列表读 `taskNew` → `sessionIdOfTask(taskNew)` **按 task 反查** session
 *     → `allTaskIdsOfApi` 取该会话全部 task, 减去 `taskNew` 即"本会话里的旧任务"。
 *   按 task 唯一定位, **结构上不会串台**。曾用过的两条错路都留了教训:
 *     · 按标题 find 反查 → 库里 20+ 个同名会话, 必然串到旧的(fre2e_15 实测翻车);
 *     · 造"旧会话" + 改名 + 历史页搜索点「继续」 → 前置噪声太大, 失败原因会被淹没,
 *       且改标题/搜索都与被测命题无关。已整体删除。
 *
 * 【口径纪律 —— 与 18 相同, 三条】
 *   ① abort **只记录不判红**(刷新必然断连, 与「点停止」在网络面板上无法区分)。
 *   ② 判「续传还在推数据」**不能只看步数增长**: 步数由 frames.stats.step_count 驱动
 *      (useTaskInfo.ts:321), 单轮长文本输出时后端连发 chunk 不发新 stats, 步数本就不动。
 *      故用「SSE 帧流入(sseParser.ts:163 每帧 console.log) **或** 计数器增长」任一成立。
 *   ③ session_id **按 task 反查**, 见上。
 */
const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

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

/** 本 case 的新任务: 长活期多步, 保证有足够执行中段供刷新落点。
 *  与 18 的 PROMPT_A/PROMPT_B **刻意不同**: 避免两个 case 在库里造出同名会话,
 *  一旦将来需要按标题排查, 能一眼分清是哪条 case 留下的。 */
/** 前置旧任务 A: 一步即完成, 只为在当前会话里造出一个"已落终态的历史任务"。
 *  2026-10-01 小欧 [北京老陈裁定 补阶段0]: 原 case 进页面直接发新任务, 而裸 URL 入口会命中
 *  「最近会话」——该会话可能一个任务都没有, 于是 oldTasks=[] , 命题②「旧任务不被误改」在结构上
 *  无从成立(实测 旧task=[] ), case 变成靠环境运气绿。旧任务必须由本 case 自己造, 不能指望环境。
 *  刻意取最短 prompt(18 的 PROMPT_A 是三步文件操作, 对本 case 过重, 白烧 2~3 分钟)。 */
const PROMPT_OLD = '请只回答两个字：就绪';

const PROMPT_NEW =
  '请撰写一份关于"深空通信延迟与探测器自主决策"的系统性说明材料，全文不少于1000字，必须包含：' +
  '①信号单程光时延的量级推算(按日地距离量级)；②延迟对地面在轨控制的实际约束；' +
  '③自主决策必须具备的三个前置条件；④延迟与自主性的取舍边界；' +
  '⑤举一个真实探测任务中出现过的延迟相关事件。' +
  '请先在临时工作目录创建一份 markdown 骨架文件并写入上述五节标题, 再逐节填充内容, 最后读回校验。' +
  '请务必在最终回答中包含"深空通信延迟"这几个字。';

test.describe('[1] 17 当前(最近)会话发新任务 · 执行中刷新', () => {
  test('从当前会话发新任务 → 执行中刷新 → 挂的是新任务且旧任务不被误改', async ({
    page,
  }) => {
    test.setTimeout(900_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    // 刻意**不调** newSession() —— 见文件头「为什么刻意不调」。走的是"最近会话"这条真实路径。
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);
    const urlAtEntry = page.url();
    console.log(`[E2E] 进入页面(裸 URL, 前端自动加载最近会话): ${urlAtEntry}`);

    // ═══ 阶段0: 前置旧任务 A(短, 必完成) —— 造出命题②要验的"历史任务" ═══
    // 2026-10-01 小欧 [北京老陈裁定 补阶段0]: 旧任务不能指望环境自带。裸 URL 入口命中的
    //   「最近会话」可能是空会话(实测 旧task=[]), 那样命题②「旧任务不被误改」形同虚设。
    //   本段与 18 的阶段1 同款(复用同一套 helper, 不重造): 发短任务 → 等终态 → DB 校验 completed。
    await chat.sendPrompt(PROMPT_OLD);
    await chat.waitDone(180_000);
    const taskOld = await activeTaskId(page);
    if (!taskOld) {
      throw new Error(
        `[E2E] 读不到前置任务A 的 task_id —— 左侧列表没有 active 项。不当通过处理`
      );
    }
    const sessionOfOld = await sessionIdOfTask(taskOld);
    if (!sessionOfOld) {
      throw new Error(
        `[E2E] 反查不到前置任务A(${taskOld}) 的 session_id。不当通过处理`
      );
    }
    // 不能只信 waitDone(它看最后一条消息有没有终态文案, 与列表 status 是两套数据源)
    const statusOld = await pollTaskStatus(sessionOfOld, taskOld, 120_000);
    console.log(
      `[E2E] 阶段0 前置任务A: session=${sessionOfOld} task=${taskOld} status=${statusOld}`
    );
    if (statusOld !== 'completed') {
      throw new Error(
        `[E2E] 前置任务A status=${statusOld} 不是 completed —— A 必须真落终态才有资格当"历史任务"。` +
          `请重跑 —— 不当通过处理`
      );
    }

    // ═══ 阶段1: 在当前会话发新任务 ═══
    const baseNew = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_NEW);
    await chat.waitReceiving(90_000);

    // 等新任务走到 ≥2 轮, 让刷新落在执行中段
    const dlNew = Date.now() + 300_000;
    while (
      Date.now() < dlNew &&
      seenRounds(diag.consoleAll, baseNew).length < 2
    ) {
      await page.waitForTimeout(500);
    }
    const roundsBefore = seenRounds(diag.consoleAll, baseNew);
    const taskNew = await activeTaskId(page);
    console.log(`[E2E] 新任务: task=${taskNew} 轮次=${roundsBefore.length}`);
    if (!taskNew) {
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
        `[E2E] 读不到新任务的 task_id —— 左侧列表没有 active 项。不当通过处理`
      );
    }
    if (roundsBefore.length < 2) {
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
        `[E2E] 窗口错过: 新任务刷新前仅 ${roundsBefore.length} 轮(<2) —— 任务没进入执行中段, ` +
          `「执行中刷新」无从验证。请重跑 —— 不当通过处理`
      );
    }

    // 按 task 反查 session(不靠 URL 正则、不靠标题反查 —— 见文件头纪律③)
    const sessionOfNew = await sessionIdOfTask(taskNew);
    if (!sessionOfNew) {
      throw new Error(
        `[E2E] 反查不到新任务(${taskNew}) 的 session_id —— 后续判据全靠它查 DB 状态。不当通过处理`
      );
    }
    // 该会话的旧任务 = 全部 task 减去刚发的新任务
    const allTasks = await allTaskIdsOfApi(sessionOfNew);
    const oldTasks = allTasks.filter((t) => t !== taskNew);
    console.log(
      `[E2E] 当前会话=${sessionOfNew} 全部task=${allTasks.length} 旧task=${JSON.stringify(oldTasks)}`
    );

    // 刷新前硬校验: 新任务必须在飞; 会话里**不能有另一个在飞任务**, 否则刷新挑中谁都是
    //   "按设计", 这条 case 就抓不到"挂错任务"。
    const stNewBefore = await statusOfTask(sessionOfNew, taskNew);
    if (stNewBefore !== 'executing') {
      throw new Error(
        `[E2E] 刷新前新任务 status=${stNewBefore} 不是 executing —— 已跑完, ` +
          `findLiveTask 挑不出在飞任务, 「刷新回来挂新任务」无从验证。请重跑 —— 不当通过处理`
      );
    }
    const oldStillRunning: string[] = [];
    for (const t of oldTasks) {
      if ((await statusOfTask(sessionOfNew, t)) === 'executing')
        oldStillRunning.push(t);
    }
    console.log(
      `[E2E] 刷新前: 新任务.status=${stNewBefore} 旧任务里仍executing的=${JSON.stringify(oldStillRunning)}`
    );
    if (oldStillRunning.length > 0) {
      throw new Error(
        `[E2E] 当前会话里还有别的在飞任务 ${JSON.stringify(oldStillRunning)} —— ` +
          `刷新挑中谁都是"按设计", 抓不到"挂错任务"。请重跑 —— 不当通过处理`
      );
    }
    // 2026-10-01 小欧 堵掉自造的假通过: 原写"旧任务数=0 也接受"(L190), 那会让本 case 在
    //   「最近会话恰好是空的」时**静默丢掉「旧任务不被误改」这条判据**——测试照样绿, 但没测。
    //   这正是"为了让测试能跑通而放宽判据"的典型烂代码, 与 15/16 处理 300s 窗口同法:
    //   **前提不成立就不当通过处理**, 显式报错交老陈重跑, 绝不静默降级。
    if (oldTasks.length === 0) {
      throw new Error(
        `[E2E] 会话 ${sessionOfNew} 里除新任务外一个旧任务都没有 —— 「旧任务不被误改」无从验证` +
          `(它就是本 case 的核心命题之一)。阶段0 已造过前置任务A(${taskOld}), 它不在其中说明` +
          `A 与新任务落到了不同会话。不当通过处理, 请重跑`
      );
    }
    // 阶段0 造的 A 必须在 oldTasks 里, 否则命题②验的是别的历史任务, 不是本 case 造的那个
    if (!oldTasks.includes(taskOld)) {
      throw new Error(
        `[E2E] 阶段0 造的前置任务A(${taskOld}, session=${sessionOfOld}) 不在 oldTasks` +
          `${JSON.stringify(oldTasks)} 里 —— A 与新任务(${taskNew}, session=${sessionOfNew}) 不同会话,` +
          `「旧任务不被误改」验的不是 A。不当通过处理, 请重跑`
      );
    }
    console.log(
      `[E2E] 旧任务数=${oldTasks.length}(含前置A=${taskOld}); ` +
        `仍executing的=${JSON.stringify(oldStillRunning)}`
    );

    // 刷新前读顶栏计数器基线, 刷新后与它比(同 14/15/16 口径)
    const counterAway = await readStepCounter(page);
    console.log(
      `[E2E] 刷新前计数器: ${counterAway ? `轮=${counterAway.rounds} 步=${counterAway.steps}` : '(读不到)'}`
    );
    if (!counterAway) {
      throw new Error(
        `[E2E] 刷新前读不到顶栏计数器 —— step 本来就没显示。不当通过处理`
      );
    }
    expect(counterAway.steps).toBeGreaterThan(0);

    // ═══ 动作: 执行中刷新浏览器 ═══
    const failBaseR = diag.allFailed.length;
    const reqBaseR = diag.streamReqs.length;
    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const urlAfterReload = page.url();
    console.log(`[E2E] 刷新: ${urlAtEntry} -> ${urlAfterReload}`);

    // abort **只记录不判红** —— 见文件头纪律①(刷新必然断连)
    const abortsR = diag.allFailed
      .slice(failBaseR)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 刷新新增abort=${abortsR.length}(不判红: 刷新必然断连, 与「点停止」无法区分)`
    );

    // 零 DELETE /chat/**(刷新不得掐断任务)
    const delR = diag.streamReqs
      .slice(reqBaseR)
      .filter(
        (l) =>
          /REQ (DELETE|POST) /.test(l) &&
          /\/chat\//.test(l) &&
          /delete/i.test(l)
      );
    console.log(`[E2E] 刷新新增DELETE=${delR.length}`);
    expect(delR).toEqual([]);

    // 刷新后旧任务必须仍是终态(刷新不得改写它们)
    for (const t of oldTasks) {
      const st = await statusOfTask(sessionOfNew, t);
      if (st === 'executing') {
        throw new Error(
          `[E2E] 刷新后旧任务 ${t} 变成 executing —— 刷新不该复活任何旧任务。不当通过处理`
        );
      }
    }
    console.log(
      `[E2E] 刷新后旧任务状态复核通过(共 ${oldTasks.length} 个, 均非 executing)`
    );

    // ═══ 回来后: 挂的必须是新任务 ═══
    await expect
      .poll(async () => (await activeTaskId(page)) !== '', {
        timeout: 60_000,
        intervals: [500],
      })
      .toBeTruthy();
    const activeAfter = await activeTaskId(page);
    console.log(`[E2E] 刷新后 active=${activeAfter}(应为 ${taskNew})`);
    if (activeAfter !== taskNew) {
      throw new Error(
        `[E2E] 刷新后页面挂到了 task=${activeAfter}, 期望 ${taskNew} —— ` +
          `同会话里还有旧任务 ${JSON.stringify(oldTasks)}, 挑错就是"刷新后显示其他任务结果"的形态。` +
          `不当通过处理`
      );
    }
    // 左侧列表里旧任务必须仍显示原终态(UI 层同样不许被误改)
    for (const t of oldTasks) {
      const st = await taskStatusInList(page, t);
      const apiSt = await statusOfTask(sessionOfNew, t);
      if (st && st !== apiSt) {
        throw new Error(
          `[E2E] 左侧列表里旧任务 ${t} 显示 ${st}, 后端却是 ${apiSt} —— UI 与 DB 不一致。不当通过处理`
        );
      }
    }
    console.log(`[E2E] 左侧列表旧任务状态与后端一致(共 ${oldTasks.length} 个)`);

    // 计数器: 不回退 + 步数非 0
    const counterAfter = await readStepCounter(page);
    console.log(
      `[E2E] 刷新后计数器: ${counterAfter ? `轮=${counterAfter.rounds} 步=${counterAfter.steps}` : '(读不到)'}` +
        ` (刷新前 轮=${counterAway.rounds} 步=${counterAway.steps})`
    );
    if (!counterAfter) {
      throw new Error(
        `[E2E] 刷新后读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 刷新后未渲染', counterAway, null) +
          ` —— 不当通过处理`
      );
    }
    expect(
      counterAfter.rounds,
      counterFailMsg('刷新后轮数倒退(序号回退)', counterAway, counterAfter)
    ).toBeGreaterThanOrEqual(counterAway.rounds);
    expect(
      counterAfter.steps,
      counterFailMsg('刷新后步数倒退(步骤丢失)', counterAway, counterAfter)
    ).toBeGreaterThanOrEqual(counterAway.steps);
    expect(
      counterAfter.steps,
      counterFailMsg(
        '刷新后步数为 0 —— 累计计数没恢复(疑似挂到了同会话的旧任务)',
        counterAway,
        counterAfter
      )
    ).toBeGreaterThan(0);

    // 判「新任务真的还在跑」—— 见文件头纪律②
    const stNewAfter = await statusOfTask(sessionOfNew, taskNew);
    if (stNewAfter === 'executing') {
      const base = diag.consoleAll.length;
      const grew = await waitCounterIncreases(
        page,
        counterAfter.rounds,
        counterAfter.steps,
        20_000
      );
      const framesIn = diag.consoleAll.length - base;
      console.log(
        `[E2E] 刷新后 20s 内: SSE帧=${framesIn} 计数器 轮${counterAfter.rounds}->${grew?.rounds} 步${counterAfter.steps}->${grew?.steps}`
      );
      expect(
        framesIn > 0 ||
          (grew?.rounds ?? 0) > counterAfter.rounds ||
          (grew?.steps ?? 0) > counterAfter.steps,
        `刷新后新任务仍 executing, 但既无 SSE 帧流入(帧=${framesIn})、计数器也没动` +
          `(轮${counterAfter.rounds}->${grew?.rounds} 步${counterAfter.steps}->${grew?.steps}) —— 续传没真在推数据`
      ).toBe(true);
    }

    // 轮次不许丢(刷新前已出现过的轮次, 刷新后还得在)
    const roundsAfter = seenRounds(diag.consoleAll, baseNew);
    const lost = roundsBefore.filter((r) => !roundsAfter.includes(r));
    console.log(
      `[E2E] 刷新后轮次数=${roundsAfter.length}(刷新前=${roundsBefore.length}) 丢失=${JSON.stringify(lost)}`
    );
    if (lost.length > 0) {
      throw new Error(
        `[E2E] 刷新前已出现的轮次 ${JSON.stringify(lost)} 刷新后消失 —— 步骤回退。不当通过处理`
      );
    }

    // ═══ 终态: 新任务跑完 ═══
    const stFinal = await pollTaskStatus(sessionOfNew, taskNew, 420_000);
    console.log(`[E2E] 新任务终态 status=${stFinal}`);
    if (stFinal === 'failed' || stFinal === 'cancelled') {
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
        `[E2E] 新任务终态为 ${stFinal}(本 case 未点停止)。后端日志见上方 DIAG`
      );
    }
    if (stFinal !== 'completed') {
      throw new Error(
        `[E2E] 新任务终态为 ${stFinal} —— 执行中刷新后它没能自己跑完。不当通过处理`
      );
    }

    // 终态正文完整(拿到的是完整结果, 不是残缺/空壳)
    const finalText = await chat.getFinalText();
    console.log(`[E2E] 刷新后最终正文长度=${finalText.trim().length}`);
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('深空通信延迟');

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
