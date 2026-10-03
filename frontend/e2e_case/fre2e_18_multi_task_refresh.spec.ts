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
  readElapsed,
  readStepCounter,
  sessionIdOfTask,
  startNormalUiEnv,
  statusOfTask,
  taskStatusInList,
  waitCounterIncreases,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * 18 — 同一会话内连跑两个任务, 第二个任务执行中「切走 → 切回 → 刷新」
 * 小欧 2026-10-01（自 fre2e_17_old_session_refresh_resume.spec.ts 拆出，见该文件被拆说明）
 *
 * 【本 case 的命题】
 *   一个会话里先跑完任务 A, 再发任务 B; **B 执行到中段**时先切到历史页、再刷新浏览器;
 *   回来后必须满足:
 *     ① 挂的还是 **B**(不是已完成的 A, 也不是空)
 *     ② **A 不被误改**(仍是 completed)
 *     ③ 计数器**不回退**且**继续增长**(B 真的在跑)
 *     ④ 全程**不发 DELETE / cancel**(切页与刷新都不许掐断任务)
 *
 * 【为什么 A 必须先跑完】
 *   面板里同时存在「已完成的 A」与「执行中的 B」, 刷新时若挑错任务就会挂到 A ——
 *   那正是"刷新后显示其他任务结果"这类缺陷的形态。A 未完成时 B 是唯一在飞任务, 挑不错。
 *
 * 【与 17 的分工】两个独立 case, 各自单独跑:
 *   · 本 case(18): **新建会话** + 同会话连跑 A、B + 「切走 → 切回 → 刷新」三个动作
 *   · 17: **不新建会话**, 从当前/最新会话发新任务 + 只刷新(一个动作)
 *
 * 【口径纪律 —— 三条, 都是踩过的坑】
 *   ① abort **只记录不判红**: 切页/刷新触发组件卸载 cleanup 调 abortController.abort()
 *      是**技术性**关连接(任务照跑), 与「点停止」在网络面板上完全一样却效果相反。
 *      拿它当判红 = 必红(刷新必然断连)。真命题由 DB status + 零 DELETE + 计数器承担。
 *   ② 判「续传还在推数据」**不能只看步数增长**: 步数由 frames.stats.step_count 驱动
 *      (useTaskInfo.ts:321), 单轮长文本输出时后端连发 chunk 不发新 stats, 步数本就不动。
 *      故用「SSE 帧流入(sseParser.ts:163 每帧 console.log) **或** 计数器增长」任一成立。
 *   ③ session_id **按 task 反查**(sessionIdOfTask), 不按标题反查: 反复跑会在库里堆出
 *      20+ 个同名会话, 按标题 find 必然串到旧的(fre2e_15 实测翻车)。
 */
const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const AWAY_MENU_TEXT = '历史会话';
const AWAY_URL_PATH = '/history';
/** 从历史页回跳会话页的菜单项(左侧「对话任务」) */
const BACK_MENU_TEXT = '对话任务';

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
 * 任务 A: **必须有几步**(北京老陈 2026-10-01 指令), 且要快速跑完。
 *
 * 为什么不能只有一步: A 若只答"A"两个字, 只有 1 个 step, 它的计数器与 B 的几乎一样 ——
 *   刷新时万一挂错到 A, 计数器/步数判据**照样通过**, 这条 case 最核心的
 *   "别挂到已完成任务"就白测了。A 必须有**明显可辨的多步形态**(调工具写文件 → 读回 →
 *   汇总), 挂错时计数器与 active task_id 都会明显不同, 判据才抓得住。
 * 为什么仍要短: A 只是前置, 拖长会白烧 token 与时间; 三步足够形成可辨差异。
 */
const PROMPT_A =
  '请严格按三步执行, 不要多做任何事：' +
  '第一步：调用文件工具, 在当前工作目录创建一个名为 e2e_probe_a.md 的文件, 内容写入一行 "A"。' +
  '第二步：用文件工具读回该文件, 确认内容确实是 "A"。' +
  '第三步：回答一句话, 说明前两步已完成。' +
  '要求：必须真实创建并读回文件, 不要凭想象回答。';

/** 任务 B: 中活期五步文件链(2026-10-03 小欧改小: 原八大部分采矿报告实测 616 秒,
 *  终态 7 分钟等待不够而假红。五步每步一轮工具往返总量约 4~6 分钟, 覆盖切走切回刷新
 *  全套动作窗口, 又能在终态等待内跑完; 最终回答限一句话, 不输出长文) */
const PROMPT_B =
  '请按以下五步执行, 每步都必须真实调用文件工具, 不要跳过任何一步: ' +
  '第一步：新建一个临时工作目录，并在其中创建一份 markdown 报告骨架文件（含标题+八个小节标题目录）；' +
  '第二步：用网络工具查一次候选小行星的真实公开参数（尺寸或轨道等，任选其一），并把结果填入报告文件对应小节；' +
  '第三步：读回该文件，核对骨架与数据是否完整；' ;

test.describe('[1] 18 同会话多任务 · 任务B执行中切走+切回+刷新', () => {
  test('同会话 A已完成 + B执行中 → 切走页 + 刷新 → 挂的是B且A不被误改', async ({
    page,
  }) => {
    test.setTimeout(900_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    // 显式新建会话: 裸 URL 会命中场景3 自动加载"最近会话", 消息会落进上一轮残留会话,
    //   导致本会话 task 数累积、"A/B 同会话"这个前提失效。
    await chat.newSession();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // ═══ 阶段1: 前置任务 A(短, 必完成) ═══
    await chat.sendPrompt(PROMPT_A);
    await chat.waitDone(180_000);
    const taskIdA = await activeTaskId(page);
    if (!taskIdA) {
      throw new Error(
        `[E2E] 读不到任务A 的 task_id —— 左侧列表没有 active 项。不当通过处理`
      );
    }
    // 按 task 反查 session(不靠 URL 正则, 也不靠标题反查 —— 见文件头纪律③)
    const sessionId = await sessionIdOfTask(taskIdA);
    if (!sessionId) {
      throw new Error(
        `[E2E] 反查不到任务A(${taskIdA}) 的 session_id —— 后续判据全靠它查 DB 状态。不当通过处理`
      );
    }
    // 不能只信 waitDone(它看的是最后一条消息有没有出终态文案, 与列表 status 是两套数据源)
    const statusA = await pollTaskStatus(sessionId, taskIdA, 120_000);
    console.log(
      `[E2E] 阶段1 任务A: session=${sessionId} task=${taskIdA} status=${statusA}`
    );
    if (statusA !== 'completed') {
      throw new Error(
        `[E2E] 前置任务A status=${statusA} 不是 completed —— A 必须真落终态才有资格当"历史任务"` +
          `(否则刷新挑到 A 是"按设计"而非 bug)。请重跑 —— 不当通过处理`
      );
    }

    // ═══ 阶段2: 同会话发长活期任务 B, 执行中即走「切走 → 切回 → 刷新」 ═══
    const baseB = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_B);
    await chat.waitReceiving(90_000);

    // 等 B 走到 ≥2 轮, 让动作落在中段(刷新窗口的前提)
    const dlB = Date.now() + 300_000;
    while (Date.now() < dlB && seenRounds(diag.consoleAll, baseB).length < 2) {
      await page.waitForTimeout(500);
    }
    const roundsAtAway = seenRounds(diag.consoleAll, baseB);
    const taskIdB = await activeTaskId(page);
    console.log(
      `[E2E] 阶段2 任务B: task=${taskIdB} 轮次=${roundsAtAway.length}`
    );
    if (!taskIdB || taskIdB === taskIdA) {
      throw new Error(
        `[E2E] 读不到任务B(${taskIdB}) 或它与A(${taskIdA})相同 —— "同会话两个任务"前提不成立。不当通过处理`
      );
    }
    if (roundsAtAway.length < 2) {
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
        `[E2E] 窗口错过: 任务B 动作前仅 ${roundsAtAway.length} 轮(<2) —— 任务没进入执行中段, ` +
          `「切走/刷新时它在飞」无从验证。请重跑 —— 不当通过处理`
      );
    }

    // 2026-10-01 小欧: 动作前硬校验 —— B 必须在飞, 且 A 必须**不是**在飞。
    //   findLiveTask 只从 executing 里挑; 若此时 A 也 executing, 挑中 A 就是"按设计"而非缺陷,
    //   那这条 case 就白跑了(抓不到"挂错任务")。
    const statusBBefore = await statusOfTask(sessionId, taskIdB);
    const statusABefore = await statusOfTask(sessionId, taskIdA);
    console.log(
      `[E2E] 动作前: A.status=${statusABefore} B.status=${statusBBefore}`
    );
    if (statusBBefore !== 'executing') {
      throw new Error(
        `[E2E] 动作前任务B status=${statusBBefore} 不是 executing —— 已跑完, ` +
          `findLiveTask 挑不出在飞任务, 「回来挂 B」无从验证。请重跑 —— 不当通过处理`
      );
    }
    if (statusABefore === 'executing') {
      throw new Error(
        `[E2E] 前置任务A 此刻仍 executing —— 面板里有两个在飞任务, 刷新挑中谁都是"按设计", ` +
          `本 case 抓不到"挂错任务"。请重跑 —— 不当通过处理`
      );
    }

    // 该会话此刻应恰好 2 个 task(A + B), 多了说明落进残留会话
    const tasksBefore = await allTaskIdsOfApi(sessionId);
    if (tasksBefore.length !== 2) {
      throw new Error(
        `[E2E] 会话 ${sessionId} 动作前有 ${tasksBefore.length} 个 task(期望恰好 2 = A+B)` +
          `—— 落进了残留会话, "同会话两任务"前提失效。请重跑 —— 不当通过处理`
      );
    }

    // 切走前读顶栏计数器基线, 切回后与它比(同 14/15/16 口径)
    const counterAway = await readStepCounter(page);
    console.log(
      `[E2E] 切走前计数器: ${counterAway ? `轮=${counterAway.rounds} 步=${counterAway.steps}` : '(读不到)'}`
    );
    if (!counterAway) {
      throw new Error(
        `[E2E] 切走前读不到顶栏计数器 —— step 本来就没显示。不当通过处理`
      );
    }
    expect(counterAway.steps).toBeGreaterThan(0);
    // 耗时基线(与刷新后读数对照, 判"秒表是否在走"用)
    const elapsedAway = await readElapsed(page);
    console.log(`[E2E] 切走前耗时读数=${elapsedAway ?? '(顶栏未显示耗时)'}`);

    // ═══ 动作①: 点菜单「历史会话」切走(不刷新) ═══
    const failBase1 = diag.allFailed.length;
    const reqBase1 = diag.streamReqs.length;
    const urlAtAway = page.url();
    await page
      .locator('.ant-menu-item', { hasText: AWAY_MENU_TEXT })
      .first()
      .click();
    // 显式观察窗而非固定 sleep: 固定 sleep 只覆盖"sleep 内发生"的情形, 若产品把清理挂在
    //   定时器/防抖上(切走 10s 后才发 DELETE), sleep 完立刻断言 → 请求还没发 → **假通过**。
    const AWAY_OBSERVE_MS = 20_000;
    const dlObserve = Date.now() + AWAY_OBSERVE_MS;
    while (Date.now() < dlObserve) {
      await page.waitForTimeout(1000);
      // 观察期内若任务自己跑完了, 后面"status 仍 executing"就没有"在飞"可言, 提前如实报错
      const stMid = await statusOfTask(sessionId, taskIdB);
      if (stMid !== 'executing') {
        throw new Error(
          `[E2E] 切走观察窗内任务B 已离开 executing(status=${stMid}) —— ` +
            `「切走时任务仍在跑」无法验证(它是自己跑完的, 不是被切走害的)。请重跑 —— 不当通过处理`
        );
      }
    }
    const urlAfterAway = page.url();
    console.log(`[E2E] 动作① 切走: ${urlAtAway} -> ${urlAfterAway}`);
    // 防假通过硬断言: 视图必须真的关闭(URL 变了且落在目标页), 否则后续红线断言全部空转
    expect(urlAfterAway).not.toBe(urlAtAway);
    expect(urlAfterAway).toContain(AWAY_URL_PATH);

    // abort **只记录不判红** —— 见文件头纪律①
    const abortsAway = diag.allFailed
      .slice(failBase1)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 动作① 新增abort=${abortsAway.length}(不判红: 组件卸载必触发, 与「点停止」无法区分)`
    );

    // 零 DELETE /chat/**(切走不得掐断任务)
    const deletes = diag.streamReqs
      .slice(reqBase1)
      .filter(
        (l) =>
          /REQ (DELETE|POST) /.test(l) &&
          /\/chat\//.test(l) &&
          /delete/i.test(l)
      );
    console.log(`[E2E] 动作① 新增DELETE=${deletes.length}`);
    expect(deletes).toEqual([]);

    // 零 cancel 请求(切走不等于点停止 —— 这才是"没误停"的真证据)
    const cancelLines = diag.streamReqs
      .slice(reqBase1)
      .filter((l) => l.includes(taskIdB) && /cancel|取消/i.test(l));
    console.log(`[E2E] 动作① 新增cancel=${cancelLines.length}`);
    expect(cancelLines).toEqual([]);

    // 切走后 A 仍 completed(B 才是唯一在飞)
    const statusAAfterAway = await statusOfTask(sessionId, taskIdA);
    if (statusAAfterAway !== 'completed') {
      throw new Error(
        `[E2E] 切走后任务A status=${statusAAfterAway} 被改成了非终态 —— 切走不该动任何任务。` +
          `A=completed 记录见动作前。不当通过处理`
      );
    }

    // ═══ 动作②: 切回会话页(不刷新) ═══
    // 2026-10-01 小欧 [北京老陈指令] 动作顺序是**三个**: 切走 → 切回 → 刷新。
    //   原实现把刷新插在切走与切回之间, 页面停在 /history 上刷新, 刷新后等不到输入框
    //   (实测 reload 后仍渲染 history 视图, 与我原先注释里"回落渲染 ChatPage"的说法相反)。
    //   现按老陈的顺序: 先切回会话页, 再在会话页上刷新。
    // 不裸 goto('/'): 实测那会命中"加载最近会话"而跳到别的会话, 判据全部空转 —— 走菜单回跳。
    const backBase = diag.allFailed.length;
    await page
      .locator('.ant-menu-item', { hasText: BACK_MENU_TEXT })
      .first()
      .click();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const urlAfterBack = page.url();
    console.log(`[E2E] 动作② 切回: ${urlAfterAway} -> ${urlAfterBack}`);
    expect(urlAfterBack).not.toContain(AWAY_URL_PATH);

    // 2026-10-01 小欧 [北京老陈肉眼验收] 切回后**留 5s 可见停顿**再刷新。
    //   原实现切回后立刻 reload, 两者相隔仅 534ms, 肉眼只看得见"切了一次页", 看不出刷新 ——
    //   北京老陈据此质疑"没看到切换后的刷新"。三个动作必须在时间轴上明显分开才能被验收。
    //   停顿期同时打印当前状态, 便于事后核对切回后任务是否已挂上。
    await page.waitForTimeout(5_000);
    const counterAtBack = await readStepCounter(page);
    console.log(
      `[E2E] 动作② 切回后停顿 5s: URL=${page.url()} ` +
        `计数器=${counterAtBack ? `轮${counterAtBack.rounds}/步${counterAtBack.steps}` : '(读不到)'} —— 即将执行动作③刷新`
    );

    // 切回过程中同样零 DELETE / 零 cancel
    const abortsBack = diag.allFailed
      .slice(backBase)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 动作② 切回新增abort=${abortsBack.length}(不判红: 组件卸载必触发, 同上)`
    );
    const deletesBack = diag.streamReqs
      .slice(reqBase1)
      .filter(
        (l) =>
          /REQ (DELETE|POST) /.test(l) &&
          /\/chat\//.test(l) &&
          /delete/i.test(l)
      );
    expect(deletesBack).toEqual([]);

    // 切回后 B 必须已经挂上且还在跑(这一步就能早发现"切回来就挂错任务")
    await expect
      .poll(async () => (await activeTaskId(page)) !== '', {
        timeout: 60_000,
        intervals: [500],
      })
      .toBeTruthy();
    const activeAfterBack = await activeTaskId(page);
    console.log(
      `[E2E] 动作② 切回后 active=${activeAfterBack}(应为 ${taskIdB})`
    );
    if (activeAfterBack !== taskIdB) {
      throw new Error(
        `[E2E] 切回后页面挂到了 task=${activeAfterBack}, 期望 ${taskIdB}(B) —— ` +
          `A(${taskIdA}) 已 completed 不该被选中。不当通过处理`
      );
    }
    const statusABack = await statusOfTask(sessionId, taskIdA);
    if (statusABack !== 'completed') {
      throw new Error(
        `[E2E] 切回后任务A status=${statusABack} 被改写 —— 切走/切回不该动已完成任务。不当通过处理`
      );
    }

    // ═══ 动作③: 在会话页上刷新浏览器 ═══
    // 此刻页面在会话页且 URL 带 session_id(同会话续发不重写 URL, 见 useChatSend.ts:145-154),
    // 故刷新走 useChatSession 场景1(URL 加载历史)。不断言刷新后的 URL 形态 —— 刷新动作由
    // 「A 仍 completed + 挂回 B + 计数器续涨 + 零 DELETE」四条实证覆盖, URL 只记日志。
    const failBaseRefresh = diag.allFailed.length;
    // 2026-10-01 小欧 [北京老陈肉眼验收] 刷新**是否真的执行**用页面级标记做硬判据, 不用推断。
    //   病根: 此前只靠 console.log 打印 URL 与后端日志推断"刷新跑了", 而 2026-10-01 22:00 那轮
    //   我据后端"只有 1 次重连"误判"刷新没执行"(实际是切回那次), 又据 framenavigated 反过来确认 ——
    //   两次都靠推断, 结论互相打架。改为: reload 前在 window 上打标记, reload 后该标记必消失
    //   (整份 JS 上下文被重建)。标记还在 = 页面没重新加载 = 动作③ 没真发生, 显式报错。
    await page.evaluate(() => {
      (window as unknown as { __preReloadMark?: string }).__preReloadMark =
        'set-before-reload';
    });
    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const markAfterReload = await page.evaluate(
      () => (window as unknown as { __preReloadMark?: string }).__preReloadMark
    );
    const urlAfterRefresh = page.url();
    console.log(
      `[E2E] 动作③ 刷新: ${urlAfterBack} -> ${urlAfterRefresh} ` +
        `页面标记=${markAfterReload === undefined ? '已消失(刷新确已执行)' : '仍存在(刷新未执行!)'}`
    );
    if (markAfterReload !== undefined) {
      throw new Error(
        `[E2E] 动作③ 刷新**没有真正执行**: reload 前打的 window 标记在 reload 后仍存在` +
          `(值=${markAfterReload}) —— 说明页面 JS 上下文没被重建。` +
          `URL=${urlAfterRefresh}。本 case 后续判据全部失效 —— 不当通过处理`
      );
    }
    // 刷新后留 5s 可见停顿, 让北京老陈能肉眼确认"刷新后任务仍在跑"(而不是停在旧画面)
    await page.waitForTimeout(5_000);
    const counterAtRefresh = await readStepCounter(page);
    console.log(
      `[E2E] 动作③ 刷新后停顿 5s: 计数器=${counterAtRefresh ? `轮${counterAtRefresh.rounds}/步${counterAtRefresh.steps}` : '(读不到)'}`
    );
    // 2026-10-01 小欧 [北京老陈肉眼发现"第二个任务计时一直不动到结束"] 耗时探针:
    //   耗时与轮/步**不同源**。TaskInfoBar `shownElapsed` 的取值路由(useTaskSelection.ts:52):
    //     selectedDetail=null            → 走本地 setInterval 秒表(每秒走);
    //     selectedDetail 有值(detail 分支) → 走 info.elapsedSec = stats.duration(只在收到 stats 帧时跳)。
    //   故"轮/步在动而耗时不动"完全可能。此处先**只记录**实测值, 定位清楚再决定是否判红 ——
    //   绝不在没搞清是哪条路之前把观察现象直接写成断言。
    const elapsedAtRefresh = await readElapsed(page);
    console.log(
      `[E2E] 动作③ 刷新后耗时读数=${elapsedAtRefresh ?? '(顶栏未显示耗时)'}`
    );

    const abortsRefresh = diag.allFailed
      .slice(failBaseRefresh)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 动作③ 刷新新增abort=${abortsRefresh.length}(不判红: 刷新必然断连, 同上)`
    );

    // 零 DELETE /chat/**(刷新也不得掐断任务)
    const deletesRefresh = diag.streamReqs
      .slice(reqBase1)
      .filter(
        (l) =>
          /REQ (DELETE|POST) /.test(l) &&
          /\/chat\//.test(l) &&
          /delete/i.test(l)
      );
    expect(deletesRefresh).toEqual([]);

    // 刷新后 A 必须仍是 completed(刷新不得改写历史任务)
    const statusAAfterRefresh = await statusOfTask(sessionId, taskIdA);
    console.log(`[E2E] 动作③ 刷新后 A.status=${statusAAfterRefresh}`);
    if (statusAAfterRefresh !== 'completed') {
      throw new Error(
        `[E2E] 刷新后任务A status=${statusAAfterRefresh} 被改写 —— 刷新不该动已完成任务。不当通过处理`
      );
    }

    // 轮询到 active 落定(异步链最后一环, 立即读必拿空串假红; 真挂错则轮询到超时仍不对 → 照样红)
    await expect
      .poll(async () => (await activeTaskId(page)) !== '', {
        timeout: 60_000,
        intervals: [500],
      })
      .toBeTruthy();
    const activeAfter = await activeTaskId(page);
    console.log(`[E2E] 回来后 active=${activeAfter}(应为 ${taskIdB})`);
    if (activeAfter !== taskIdB) {
      throw new Error(
        `[E2E] 回来后页面挂到了 task=${activeAfter}, 期望 ${taskIdB}(B) —— ` +
          `A(${taskIdA}) 已 completed 不该被选中。这正是"刷新后显示其他任务结果"的形态。不当通过处理`
      );
    }
    // 左侧列表里 A 必须仍显示 completed(UI 层同样不许被误改)
    const statusAList = await taskStatusInList(page, taskIdA);
    console.log(`[E2E] 回来后 列表内A.status=${statusAList}`);
    if (statusAList !== 'completed') {
      throw new Error(
        `[E2E] 回来后左侧列表里任务A 显示 ${statusAList}(应 completed) —— UI 层状态被误改。不当通过处理`
      );
    }

    // 计数器: 不回退
    const counterAfter = await readStepCounter(page);
    console.log(
      `[E2E] 回来后计数器: ${counterAfter ? `轮=${counterAfter.rounds} 步=${counterAfter.steps}` : '(读不到)'}` +
        ` (切走前 轮=${counterAway.rounds} 步=${counterAway.steps})`
    );
    if (!counterAfter) {
      throw new Error(
        `[E2E] 回来后读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 回来后未渲染', counterAway, null) +
          ` —— 不当通过处理`
      );
    }
    expect(
      counterAfter.rounds,
      counterFailMsg('回来后轮数倒退(序号回退)', counterAway, counterAfter)
    ).toBeGreaterThanOrEqual(counterAway.rounds);
    expect(
      counterAfter.steps,
      counterFailMsg('回来后步数倒退(步骤丢失)', counterAway, counterAfter)
    ).toBeGreaterThanOrEqual(counterAway.steps);
    expect(
      counterAfter.steps,
      counterFailMsg(
        '回来后步数为 0 —— 累计计数没恢复(疑似挂到了已完成的 A)',
        counterAway,
        counterAfter
      )
    ).toBeGreaterThan(0);

    // 判「B 真的还在跑」—— 见文件头纪律②
    // 2026-10-01 小欧 [北京老陈"改正确"] 观察窗 20s → 90s。原 20s 是**凭空假设**"刷新后 20 秒内
    //   必有帧", 被实测打脸: 2026-10-01 22:08 那轮, 后端续传连接建立后**首帧延迟 28.6 秒**
    //   (LLM 连写长文时一个响应可持续 28s+ 才吐下一个 chunk), 于是 20s 窗内零帧 → 假红。
    //   对照实测两轮首帧延迟: 绿轮 +0.4s / 红轮 +28.6s, 故取 90s(约 3 倍余量)。
    //   注意这**不是放宽判据**: 90s 内仍零帧且计数器不动 = 续传真的没在推数据, 照样判红。
    const RESUME_WATCH_MS = 90_000;
    const statusBAfter = await statusOfTask(sessionId, taskIdB);
    if (statusBAfter === 'executing') {
      const base = diag.consoleAll.length;
      const grew = await waitCounterIncreases(
        page,
        counterAfter.rounds,
        counterAfter.steps,
        RESUME_WATCH_MS
      );
      const framesIn = diag.consoleAll.length - base;
      console.log(
        `[E2E] 回来后 ${RESUME_WATCH_MS / 1000}s 内: SSE帧=${framesIn} 计数器 轮${counterAfter.rounds}->${grew?.rounds} 步${counterAfter.steps}->${grew?.steps}`
      );
      expect(
        framesIn > 0 ||
          (grew?.rounds ?? 0) > counterAfter.rounds ||
          (grew?.steps ?? 0) > counterAfter.steps,
        `回来后任务B 仍 executing, 但 ${RESUME_WATCH_MS / 1000}s 内既无 SSE 帧流入(帧=${framesIn})、计数器也没动` +
          `(轮${counterAfter.rounds}->${grew?.rounds} 步${counterAfter.steps}->${grew?.steps}) —— 续传没真在推数据`
      ).toBe(true);
    }

    // 轮次不许丢(切走+刷新期间已出现过的轮次, 回来后还得在)
    const roundsBack = seenRounds(diag.consoleAll, baseB);
    const lostRounds = roundsAtAway.filter((r) => !roundsBack.includes(r));
    console.log(
      `[E2E] 回来后轮次数=${roundsBack.length}(切走时=${roundsAtAway.length}) 丢失=${JSON.stringify(lostRounds)}`
    );
    if (lostRounds.length > 0) {
      throw new Error(
        `[E2E] 切走期间已出现的轮次 ${JSON.stringify(lostRounds)} 回来后消失 —— 步骤回退。不当通过处理`
      );
    }

    // ═══ 终态: B 跑完, A 不受影响 ═══
    const statusBFinal = await pollTaskStatus(sessionId, taskIdB, 420_000);
    console.log(`[E2E] 任务B 终态 status=${statusBFinal}`);
    if (statusBFinal === 'failed' || statusBFinal === 'cancelled') {
      const errText = readLogSince(BLOG, logBase);
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        errText,
        diag.allFailed,
        getCaseId()
      );
      throw new Error(
        `[E2E] 任务B 终态为 ${statusBFinal}(本 case 未点停止)。后端日志见上方 DIAG`
      );
    }
    if (statusBFinal !== 'completed') {
      throw new Error(
        `[E2E] 任务B 终态为 ${statusBFinal} —— 切走+刷新后它没能自己跑完。不当通过处理`
      );
    }
    // A 终态复核
    const statusAFinal = await statusOfTask(sessionId, taskIdA);
    if (statusAFinal !== 'completed') {
      throw new Error(
        `[E2E] 终态时任务A status=${statusAFinal} —— 整个流程中 A 被误改了。不当通过处理`
      );
    }

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
