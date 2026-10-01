import { test, expect } from '@playwright/test';
import {
  activeTaskId,
  allTaskIdsInList,
  API_BASE,
  attachStreamDiag,
  ChatPage,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  pollTaskStatus,
  printDiag,
  readLogSince,
  startNormalUiEnv,
  statusOfTask,
  taskStatusInList,
  readStepCounter,
  counterFailMsg,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * E2E-17 旧会话·任务执行中·刷新·验回来挂的是在跑的那个任务
 *
 * 断什么: 会话里已有跑完的任务 A、正在跑的任务 B, 刷新一下页面却显示 A 的结果(老陈截图)。
 *   新会话只有一个任务, 天然挑不错, 测不到这层。
 *
 * 两个场景, 差别只在刷新时地址栏带不带参数, 也就是走 useChatSession 场景1 还是场景3:
 *   ① 同标签页先跑 A 再跑 B → 点「历史会话」切走 → F5(地址栏**不带** session_id) → 点「对话任务」切回
 *   ② 从历史列表点开一个早先生成的旧会话(搜标题, 断言只剩 1 张卡, 点「继续」, 地址栏**带** id)
 *      → 在里面直接发新任务 → F5(地址栏仍带 id)
 *
 * 判据(两个场景都适用):
 *   ①动作确实发生: 切走时 URL 真变成 /history, 刷新时 JS 上下文真重建
 *   ②切走与刷新全程零 abort、零 DELETE /chat/*
 *   ③DB 里在跑的任务没被改状态, 已完成的旧任务没被误改
 *   ④**回来后左侧选中的是在跑的那个任务** —— 本 case 核心, 就这一条
 *   ⑤切走前的轮次回来后一个不少
 *   ⑥在跑的任务最终必须 completed; 拿到 failed/cancelled 打后端 ERROR 行后显式判红
 *
 * 编辑历史: 2026-10-01 小欧 —— 从 fre2e_15 第二个 test 拆出(老陈: 新旧会话拆开, 且只到 17 为止);
 *   同日补场景②(老陈指出旧会话有两种: 同会话内接着发 / 打开旧会话再续新任务)。
 * 铁规: AGENTS.md 禁止 commit 测试文件。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const AWAY_MENU_TEXT = '历史会话';
const AWAY_URL_PATH = '/history';

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
 * 阶段1 的前置任务 A —— 短、必完成, 只为在会话里留下一条 completed 历史任务。
 * 主题词与 B 完全分开(前置校验 vs 近地小行星), 便于判"刷新后挂到了哪个任务"。
 */
const PROMPT_A =
  '请先完成一个极简的前置动作, 为后续任务留一条历史记录。请实际操作(不要停留在思考层面): ' +
  '第一步: 新建一个临时工作目录 fe17_old_session, 并在其中创建一份 markdown 文件 precheck.md, ' +
  '文件里只写一行"前置校验通过"; ' +
  '第二步: 读回该文件, 确认那一行确实存在; ' +
  '第三步: 在对话中用一句话回复"前置校验完成"。请在回复中包含"前置校验通过"这几个字。';

/**
 * 阶段2 的目标任务 B —— 长活期多步(建目录→写骨架→联网查→读回), 保证刷新窗口内仍在跑。
 * 刻意与 fre2e_14/15 的任务同主题(近地小行星): 同会话续发, 唯一变量是"会话里已有历史任务",
 * 这样与单任务场景的差异被隔离出来, 失败才能归因到"多任务 + 刷新"而非"任务本身跑不动"。
 */
const PROMPT_B =
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

/**
 * 阶段2 的目标任务 B(第2个 test 用)—— 深海矿产梯级开发。
 * 刻意换主题(近地小行星 / 深海矿产)与工具链措辞, 与其余 case 的任务互不相同,
 * 便于在历史列表/任务列表里凭正文锚点区分"本 case 的任务"与其他遗留任务。
 */
const PROMPT_STALE =
  '请完成一份"深海矿产梯级开发可行性"技术评估报告, 全文不少于1200字、分七大部分并给出具体数值参数: ' +
  '①海洋平台能源供给方案对比(≥3种, 附功率与续航)②深海作业耐压装备清单(≥5类, 附潜深与承压) ' +
  '③提升系统效率与能耗核算(给出公式与数值代入)④海水分离淡化产能测算(吨/日) ' +
  '⑤材料输送与返航链路参数(管径/流速/寿命)⑥环境风险与应急处置(≥5类排序) ' +
  '⑦分级结论(可行/不可行/需论证)。' +
  '为支撑报告数据, 请按以下步骤实际操作(不要停留在思考层面): ' +
  '第一步: 新建一个临时工作目录 fe17_stale, 并在其中创建一份 markdown 报告骨架文件(含标题+七个小节标题目录); ' +
  '第二步: 用网络工具查一次深海耐压材料的真实公开参数(耐压深度或强度等, 任选其一), 并把结果填入报告文件对应小节; ' +
  '第三步: 读回该文件, 核对骨架与数据是否完整; ' +
  '第四步: 在对话中给出完整的评估报告正文(仍覆盖七大部分并包含你查到的数值)。' +
  '请务必在最终回答中包含"深海矿产梯级开发"这几个字。';

test.describe('[1] 旧会话多任务 · 切页面 + 刷新续传', () => {
  test('老会话已有完成任务A + 任务B执行中 → 切走页 + 刷新 → 回来挂的是B且A不被误改', async ({
    page,
  }) => {
    test.setTimeout(900_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // ═══ 阶段1: 前置任务 A(短, 必完成), 给会话留下一条 completed 历史任务 ═══
    await chat.sendPrompt(PROMPT_A);
    await chat.waitDone(180_000);
    const taskIdA = await activeTaskId(page);
    expect(taskIdA).toBeTruthy();
    // A 是本标签页新建会话的首个任务 → useChatSession.ts:538 必写 URL, 故此处 URL 必带 id。
    // (发完 B 后 URL 仍不带 id —— 同一会话续发不再写 URL, 属 useChatSend.ts:145-154 既定行为)
    const sessionIdOfA = (page.url().match(/session_id=([^&]+)/) ?? [])[1] ?? '';
    expect(sessionIdOfA).toBeTruthy();
    // 不能只信 waitDone —— 它看的是最后一条消息有没有出终态文案, 与列表 status 是两套数据源
    // (实测出现过 waitDone 返回了但列表仍 executing)。A 必须真落 completed 才有资格当"历史任务"。
    const statusA = await pollTaskStatus(sessionIdOfA, taskIdA, 120_000);
    console.log(`[E2E] 阶段1 前置任务A: task=${taskIdA} status=${statusA}`);
    expect(statusA).toBe('completed');

    // ═══ 阶段2: 同会话发长活期任务 B, 执行中即走"切页面 + 刷新"两个动作 ═══
    const baseB = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_B);
    await chat.waitReceiving(90_000);

    // 等 B 走到 ≥2 轮, 让动作落在中段(刷新窗口的前提)
    const dlB = Date.now() + 300_000;
    while (Date.now() < dlB && seenRounds(diag.consoleAll, baseB).length < 2) {
      await page.waitForTimeout(500);
    }
    const roundsAtAway = seenRounds(diag.consoleAll, baseB);
    console.log(`[E2E] 阶段2 任务B: 轮次=${roundsAtAway.length}`);
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
        `[E2E] 窗口错过: 任务B 刷新前仅 ${roundsAtAway.length} 轮(<2)——请重跑以覆盖刷新续传分支`
      );
    }
    const taskIdB = await activeTaskId(page);
    expect(taskIdB).toBeTruthy();
    expect(taskIdB).not.toBe(taskIdA);

    // 2026-10-01 小欧 [1] 硬判据补齐(北京老陈: 要真实):
    //   本 case 的全部价值在"刷新回来挂的是 B", 而 findLiveTask(chatStreamStore.ts:422-434)
    //   只从 **executing 的任务**里挑(ASC 取最后一个)。所以:
    //     - 若此刻 B 已自然跑完 → 会话里 executing 数为 0 → findLiveTask 挑不出 B,
    //       根本走不到本 case 要验的那条分支, 断言全成空转;
    //     - 若此刻 A 还在跑(不该发生, A 已硬校验 completed, 但防回归) → 会挑到 A, 挂错。
    //   故切走前必须硬校验: **恰好 B 一个 executing, A 不是 executing**。
    const sessionId = sessionIdOfA;
    const stBNow = await statusOfTask(sessionId, taskIdB);
    const stANow = await statusOfTask(sessionId, taskIdA);
    console.log(
      `[E2E] 切走前: B.status=${stBNow} A.status=${stANow}(须 B=executing 且 A≠executing)`
    );
    if (stBNow !== 'executing') {
      throw new Error(
        `[E2E] 切走前 B.status=${stBNow} 不是 executing —— 任务已跑完, ` +
          `findLiveTask 挑不出在飞任务, 「刷新回来挂B」这条判据无法验证。请重跑`
      );
    }
    expect(stANow).not.toBe('executing');

    // 判据用 DB 权威接口核对"该会话确实有 A、B 两个任务";
    // UI 列表那条只作软证据 —— 列表可能只渲染最近 N 条, 拿它断言会假失败。
    const tasksFromApi = (await fetch(
      `${API_BASE}/sessions/${sessionId}/tasks`
    ).then((r) => r.json())) as {
      tasks?: { task_id: string; status: string }[];
    };
    const apiIds = (tasksFromApi.tasks ?? []).map((t) => t.task_id);
    const uiIds = await allTaskIdsInList(page);
    console.log(
      `[E2E] 刷新前任务清单(DB)=${JSON.stringify(apiIds)} UI列表=${JSON.stringify(uiIds)}`
    );
    expect(apiIds).toContain(taskIdA);
    expect(apiIds).toContain(taskIdB);

    // ═══ 动作①: 切页面(切到历史会话页) ═══
    const reqBase1 = diag.streamReqs.length;
    const failBase1 = diag.allFailed.length;
    const urlAtAway = page.url();
    // 北京老陈 2026-10-01 要求: 切走前先读顶栏计数器基线, 刷新回来后与它比 ——
    //   判"step 还在不在正常显示、计数器还在不在正常计数"(与 14/15/16 同口径)。
    //   本 case 抓的是"挂错到历史任务 A", 但"计数器从 0 重来/不显示"是同一类可见缺陷。
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
    await page
      .locator('.ant-menu-item', { hasText: AWAY_MENU_TEXT })
      .first()
      .click();
    // 2026-10-01 小欧 [2] 北京老陈"什么算通过要真实" —— 裸 sleep 6000 换成观察窗。
    //   固定 sleep 只覆盖"6 秒内发生"的效应; 若产品把清理挂定时器(切走 10s 后才 DELETE/cancel),
    //   sleep 6s 后断言 → 请求还没发 → 通过 → 假通过。用固定 sleep 抓"切走误伤任务"自相矛盾。
    const AWAY_OBSERVE_MS = 20_000;
    const dlObs17 = Date.now() + AWAY_OBSERVE_MS;
    while (Date.now() < dlObs17) {
      await page.waitForTimeout(1000);
      const stMid = await statusOfTask(sessionIdOfA, taskIdB);
      if (stMid !== 'executing') {
        throw new Error(
          `[E2E] 动作① 观察窗内任务 B 已离开 executing(status=${stMid}) —— ` +
            `「切走时在跑的任务不受影响」无法验证。请重跑 —— 不当通过处理`
        );
      }
    }
    const urlAfterAway = page.url();
    console.log(`[E2E] 动作① 切走: ${urlAtAway} -> ${urlAfterAway}`);
    expect(urlAfterAway).not.toBe(urlAtAway);
    expect(urlAfterAway).toContain(AWAY_URL_PATH);

    const abortsAway = diag.allFailed
      .slice(failBase1)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(`[E2E] 动作① 新增abort=${abortsAway.length}`);
    expect(abortsAway).toEqual([]);

    // ═══ 动作②: 在切走页上刷新浏览器(强制走 useChatSession 场景3 裸 URL 分支) ═══
    const failBaseRefresh = diag.allFailed.length;
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    const urlAfterRefresh = page.url();
    console.log(`[E2E] 动作② 刷新: ${urlAfterAway} -> ${urlAfterRefresh}`);
    // 2026-10-01 小欧 [1]: 此处**不断言** URL 含 /history。
    //   实测 vite dev 下对 /history 发 reload, 服务端回落渲染 ChatPage, URL 变成 `/`
    //   (同源断言曾在 fre2e_15 红过一次)。刷新动作本身已由"零 abort / 无 DELETE /
    //   DB status 未被误改"三条实证覆盖, 不必拿 URL 形态当判据 —— 记日志即可。
    const abortsRefresh = diag.allFailed
      .slice(failBaseRefresh)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(`[E2E] 动作② 刷新新增abort=${abortsRefresh.length}`);
    expect(abortsRefresh).toEqual([]);

    // 切走 + 刷新全程不得发 DELETE 掐断任务
    const deletes = diag.streamReqs
      .slice(reqBase1)
      .filter((l) => l.includes('REQ DELETE') && l.includes('/chat/'));
    console.log(`[E2E] 切走+刷新后新增 DELETE类请求=${deletes.length}`);
    expect(deletes).toEqual([]);

    // ═══ 判据③: 刷新后 DB 里 B 仍 executing, A 仍 completed ═══
    const statusBAfterRefresh = await statusOfTask(sessionId, taskIdB);
    const statusAAfterRefresh = await statusOfTask(sessionId, taskIdA);
    console.log(
      `[E2E] 动作② 后 B.status=${statusBAfterRefresh} A.status=${statusAAfterRefresh}`
    );
    // B 掉出 executing/completed 说明刷新破坏了任务(failed/cancelled 即产品问题)
    expect(['executing', 'completed']).toContain(statusBAfterRefresh);
    // A 是已完成的历史任务, 刷新全程不得被误改
    expect(statusAAfterRefresh).toBe('completed');

    // ═══ 判据④: 刷新回来后 active 必须是 B, 不是历史 A ═══
    // 2026-10-01 小欧 [1] 修正一处会掩盖缺陷的导航(北京老陈: 什么算通过要真实):
    //   原写法是「`page.reload()` 之后无条件再 `page.goto('/')`」。但实测 vite dev 下对 /history
    //   发 reload, 服务端会回落渲染 ChatPage, URL 自己就变成了 `/` —— 此时再 goto('/')
    //   等于**把第一次刷新后的真实结果整个跳过**, 换成一次全新的干净加载。
    //   那样即使"刷新后挂错任务(A)"也会被第二次 goto 洗成正确, 判据形同虚设。
    //   改为: 只在确实**还停在 /history**(刷新没回落) 时才导航回会话页; 已经回落的直接用现状判。
    const landedOnChat = !page.url().includes(AWAY_URL_PATH);
    if (!landedOnChat) {
      console.log(`[E2E] 刷新后仍停在 ${page.url()}, 点菜单「对话任务」返回会话页`);
      await page
        .locator('.ant-menu-item', { hasText: '对话任务' })
        .first()
        .click();
      await page.waitForTimeout(3000);
    } else {
      console.log(`[E2E] 刷新后已回落会话页 ${page.url()}, 直接判(不再额外导航)`);
    }
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    // 轮询到 active 落定(非空)再读 —— 要走 resume → listTasks → 渲染 active 一串异步,
    // 立即读会拿空串假红。会话页 URL 刻意不带 session_id(菜单回跳靠 sessionStorage 回落),
    // 故不断言 URL 带 id, 改用列表实证判"挂到了哪个任务"。
    await expect
      .poll(
        async () => (await activeTaskId(page)) !== '',
        { timeout: 60_000, intervals: [500] }
      )
      .toBeTruthy();
    const activeAfter = await activeTaskId(page);
    const statusBList = await taskStatusInList(page, taskIdB);
    const statusAList = await taskStatusInList(page, taskIdA);
    console.log(
      `[E2E] 回来后: active=${activeAfter}(应为B=${taskIdB}) B.status=${statusBList} A.status=${statusAList}(应仍completed)`
    );
    // 本 case 专属: active 必须是正在跑的 B, 挂到历史 A 上就是老陈截图那个 bug
    expect(activeAfter).toBe(taskIdB);
    // A 是历史已完成任务, 不得被刷新误改
    expect(statusAList).toBe('completed');

    // ═══ 判据⑤: 轮次不丢 ═══
    const roundsBack = seenRounds(diag.consoleAll, baseB);
    const lostRounds = roundsAtAway.filter((r) => !roundsBack.includes(r));
    console.log(
      `[E2E] 回来后B轮次数=${roundsBack.length}(切走时=${roundsAtAway.length}) 丢失=${JSON.stringify(lostRounds)}`
    );
    expect(lostRounds).toEqual([]);

    // ═══ 判据⑥: B 终态必须 completed ═══
    // 2026-10-01 小欧 [1]: 实测曾出现 B 最终 status=failed 而当时断言写成
    // `if (status === 'executing')` —— failed 分支恰好不触发, 失败被静默放过。
    // 铁规「测试目的是发现问题, 不是跑脚本」: 失败就是问题, 必须显式暴露。
    const statusBFinal = await pollTaskStatus(sessionId, taskIdB, 420_000);
    console.log(`[E2E] 任务B 终态=${statusBFinal}(DB 权威)`);
    if (statusBFinal === 'failed') {
      const errLines = readLogSince(BLOG, logBase)
        .split('\n')
        .filter((l) => l.includes(taskIdB) && /ERROR|失败|error|Traceback/i.test(l))
        .slice(-25);
      console.log(`[E2E][DIAG] 任务B failed 的后端日志行(${errLines.length}条):`);
      for (const l of errLines) console.log(`[E2E][DIAG]   ${l.slice(0, 220)}`);
      throw new Error(
        `[E2E] 任务B 最终为 failed(本 case 未点停止, 失败即产品问题)。` +
          `后端相关日志行数=${errLines.length}，见上方 DIAG`
      );
    }
    if (statusBFinal === 'cancelled') {
      throw new Error(
        `[E2E] 任务B 最终为 cancelled —— 本 case 全程未点停止, 不应被取消(疑似误 cancel)`
      );
    }
    expect(statusBFinal).toBe('completed');
    // 终态后轮次不得回退(证明刷新后是真续传, 而非停在最后一帧)
    await page.waitForTimeout(3000);
    const roundsFinal = seenRounds(diag.consoleAll, baseB);
    console.log(
      `[E2E] 任务B 终态轮次=${roundsFinal.length}(切走时=${roundsAtAway.length})`
    );
    expect(roundsFinal.length).toBeGreaterThanOrEqual(roundsBack.length);

    // 【北京老陈 2026-10-01 要求】刷新回来后 step 正常显示 + 计数器正常计数。
    //   与 14/15/16 同口径(共用 lib/step-counter)。判据:
    //   ① 刷新后计数器读得到 —— 读不到 = step 不显示 = 不过
    //   ② 轮/步都 >= 切走前     —— 变小 = 挂到了历史 A 或累计被清 = 不过
    //   ③ 步数 > 0               —— 显示 0 等于页面像从头开始
    //   本 case 专属价值: 若刷新后挂错到 A(已完成的旧任务), A 的计数与 B 不同,
    //   ②③ 会先于 active===B 那条判出来, 给出更直观的失败原因。
    const counterAfter = await readStepCounter(page);
    console.log(
      `[E2E] 刷新后计数器: ${counterAfter ? `轮=${counterAfter.rounds} 步=${counterAfter.steps}` : '(读不到)'}` +
        ` (切走前 轮=${counterAway.rounds} 步=${counterAway.steps})`
    );
    if (!counterAfter) {
      throw new Error(
        `[E2E] 刷新后读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 刷新后未渲染', counterAway, null) +
          ` —— 不当通过处理`
      );
    }
    expect(counterAfter.rounds).toBeGreaterThanOrEqual(counterAway.rounds);
    expect(counterAfter.steps).toBeGreaterThanOrEqual(counterAway.steps);
    expect(
      counterAfter.steps,
      counterFailMsg(
        '刷新后步数为 0 —— 累计计数没恢复(疑似挂到了已完成的旧任务 A)',
        counterAway,
        counterAfter
      )
    ).toBeGreaterThan(0);

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

  /**
   * 2026-10-01 小欧 [1] 旧会话的第二种形态 —— 北京老陈指示补齐。
   *
   * 与上一个 test 的本质差别(**不是任务内容不同, 是进入路径与刷新分支不同**):
   *   上一个 test: 本标签页新建会话 → 连续跑 A、B。刷新时 URL 已被 useChatSession.ts:538
   *     写成带 id, 但**发完 B 后同一会话续发不再写 URL**(useChatSend.ts:145-154),
   *     故切走/刷新时是**裸 URL** → 走 useChatSession 场景3(loadLatestHistoryMessages)。
   *
   *   本 test: 从**历史列表点开一个早先生成的旧会话**, 在里面**直接发新任务**, 执行中刷新。
   *     进入路径是 History/index.tsx:343 `navigate('/?session_id=' + id)` ——
   *     **URL 带 id**, 所以刷新走的是 useChatSession **场景1**(URL 加载历史)。
   *     这正是老陈描述的第二种旧会话: "处理已有的会话中, 续新的任务进行刷新"。
   *
   * 为什么必须单独覆盖: 两种旧会话的刷新分别落在场景1 与场景3, 是两条独立代码路径;
   *   且本路径下面板里有**若干个早已完成的旧任务**, findLiveTask 若按"第一个"而非
   *   "最新的 executing"挑, 就会挂到某个更早的旧任务上 —— 上一 test 只有 1 个历史任务,
   *   暴露面小得多。
   *
   * 旧会话的选取(不 Mock): 用 REST 取 `GET /sessions?page=1&page_size=50`,
   *   挑**有 task 且 task 全部已终态、且不是本轮刚造**的会话 —— 即"早先遗留"的真实会话。
   *   取不到则显式 skip 并说明原因, 不静默通过、也不伪造。
   */
  test('历史遗留旧会话(URL带id) + 直接发新任务执行中 → 刷新 → 挂的是新任务不是旧任务', async ({
    page,
  }) => {
    test.setTimeout(900_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // ── 前置: 挑一个"早先遗留、且无在飞任务"的真实旧会话 ──
    // 先造一个必然是本轮的会话, 用于在候选里排除(避免自造自测)。
    await chat.sendPrompt(PROMPT_A);
    await chat.waitDone(180_000);
    const freshSessionOfThisRun = (
      page.url().match(/session_id=([^&]+)/) ?? []
    )[1] ?? '';

    // ── 旧会话选取: 自造, 不依赖外部历史库的残留数据 ──
    // 2026-10-01 小欧 [2] 北京老陈"测试烂代码能不能都消灭"—— 这里是本 case 最大的设计缺陷, 已重写:
    //   原实现扫 `GET /sessions?page=1&page_size=50` 找"有 task 且全部终态"的**外部遗留**会话,
    //   找不到就 `test.skip(true, '无合适的历史遗留旧会话可测 —— 不伪造')`。
    //   问题有三, 每一件都足以让这条 case 失去意义:
    //     ① **依赖外部环境** —— 跑在谁机器上结果不同; 干净库里必然无可选 → 整条 case 静默跳过。
    //     ② skip 让"没测"和"通过"在报告里长得一样 —— 违反 AGENTS.md
    //        "测试目的是发现问题, 严禁看到 FAIL 跳过"。
    //     ③ 每次跑挑中的旧会话都不同, 历史任务数量不可控, 判据无法收敛。
    //   改为**自己造这个旧会话**: 上一步 PROMPT_A 已在本次运行里建好一个会话并跑完一个任务,
    //   它此刻就是"一个已存在的、有已完成任务的会话"。只需把它从历史列表重新打开,
    //   就能走通「打开旧会话 → 直接发新任务 → 刷新」这条真实路径, 且**零额外 LLM 开销**、
    //   **零跳过、结果可复现**。
    //   注: 「面板里有若干个已完成旧任务」的更大暴露面由上一个 test(场景①, A+B 两个任务)覆盖,
    //       本 test 的定位是**入口路径**(URL 带 id → 场景1), 不重复承担任务数量维度。
    const staleSession = freshSessionOfThisRun;
    const staleTaskIds = await allTaskIdsOfApi(staleSession);
    const staleTitleResp = (await fetch(
      `${API_BASE}/sessions?page=1&page_size=50`
    ).then((r) => r.json())) as {
      sessions?: { session_id: string; title?: string }[];
    };
    const staleTitle = (
      staleTitleResp.sessions ?? []).find(
        (s) => s.session_id === staleSession
      )?.title ?? '';
    if (staleTitle.trim().length === 0) {
      throw new Error(
        `[E2E] 自造旧会话 ${staleSession} 取不到标题 —— 进入旧会话要靠搜索框按标题定位, 无标题无从下手`
      );
    }
    if (staleTaskIds.length === 0) {
      throw new Error(
        `[E2E] 自造旧会话 ${staleSession} 一个 task 都没有 —— 「旧会话里发新任务」无从验证`
      );
    }
    console.log(
      `[E2E] 自造旧会话=${staleSession} 标题="${staleTitle.slice(0, 40)}" 历史task=${JSON.stringify(staleTaskIds)}`
    );

    // ── 从历史列表搜索并点「继续」进入该旧会话(真实入口, 不直接改 URL) ──
    // 定位方式: 用搜索框按标题精确检索(History/index.tsx:425 onSearch →
    //   session_service.py:64-66 `title LIKE %keyword%`, 真服务端过滤),
    //   检索到**只剩 1 张卡片**时才点它的"继续"。不靠"第 N 个按钮"猜位置 ——
    //   卡片无 data-session-id, 按序号点会点到别的会话, 那就是假测。
    await page
      .locator('.ant-menu-item', { hasText: AWAY_MENU_TEXT })
      .first()
      .click();
    await expect(page.locator('.history-page')).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(2000);
    await page.locator('.history-page input.ant-input').first().fill(staleTitle);
    await page.locator('.history-page input.ant-input').first().press('Enter');
    // 等检索结果落定: 卡片数收敛到 1
    await expect
      .poll(
        async () =>
          page.locator('.history-page .ant-btn', { hasText: '继续' }).count(),
        { timeout: 30_000, intervals: [500] }
      )
      .toBe(1);
    await page
      .locator('.history-page .ant-btn', { hasText: '继续' })
      .first()
      .click();
    // 2026-10-01 小欧 [2]: 裸 sleep 6000 换成等输入框真正可见 —— 睡固定时长可能页面还没挂完,
    //   后面立刻读 URL/active 会读到中间态(假红)。等具体元素出现才是"确实进来了"。
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const urlAfterResume = page.url();
    console.log(`[E2E] 历史列表搜标题后点继续 -> ${urlAfterResume}`);
    // 该入口刻意带 session_id(History/index.tsx:343 navigate(`/?session_id=${id}`)),
    // 故本 test 的刷新走 useChatSession 场景1(URL 加载历史) —— 这是与上一个 test 的核心区别
    expect(urlAfterResume).toContain(`session_id=${staleSession}`);
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    // ── 在这个旧会话里直接发新任务, 执行中刷新 ──
    const baseNew = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_STALE);
    await chat.waitReceiving(90_000);

    const dlN = Date.now() + 300_000;
    while (
      Date.now() < dlN &&
      seenRounds(diag.consoleAll, baseNew).length < 2
    ) {
      await page.waitForTimeout(500);
    }
    const roundsBefore = seenRounds(diag.consoleAll, baseNew);
    const taskNew = await activeTaskId(page);
    console.log(
      `[E2E] 旧会话内新任务: task=${taskNew} 轮次=${roundsBefore.length}`
    );
    if (!taskNew || roundsBefore.length < 2) {
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
        `[E2E] 窗口错过: 旧会话内新任务刷新前仅 ${roundsBefore.length} 轮(<2)——请重跑`
      );
    }
    // 新任务不得与该会话的历史任务重合
    expect(staleTaskIds).not.toContain(taskNew);
    // 2026-10-01 小欧 [1] 硬判据补齐: 同场景①的理 —— findLiveTask 只从 executing 里挑,
    //   且本 case 要验的是"多个旧任务在场时也能挑中唯一在飞的那个"。故刷新前必须硬校验:
    //   新任务 executing + **所有旧任务都不是 executing**(否则刷新挑到旧任务就是"按设计"而非 bug)。
    const stNewBefore = await statusOfTask(staleSession, taskNew);
    const oldStillRunning: string[] = [];
    for (const h of staleTaskIds) {
      if ((await statusOfTask(staleSession, h)) === 'executing') {
        oldStillRunning.push(h);
      }
    }
    console.log(
      `[E2E] 刷新前: 新任务.status=${stNewBefore} 旧任务里仍executing的=${JSON.stringify(oldStillRunning)}`
    );
    if (stNewBefore !== 'executing') {
      throw new Error(
        `[E2E] 刷新前新任务 status=${stNewBefore} 不是 executing —— 已跑完, ` +
          `findLiveTask 挑不出在飞任务, 「刷新回来挂新任务」无从验证。请重跑`
      );
    }
    expect(oldStillRunning).toEqual([]);

    // 北京老陈 2026-10-01: 刷新前读顶栏计数器基线, 刷新后与它比(同 14/15/16 口径)
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

    // ── 刷新(此路径 URL 带 session_id → 走场景1) ──
    const failBaseR = diag.allFailed.length;
    await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const urlAfterReload = page.url();
    console.log(`[E2E] 刷新: ${urlAfterReload}`);
    expect(urlAfterReload).toContain(`session_id=${staleSession}`);

    const abortsR = diag.allFailed
      .slice(failBaseR)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(`[E2E] 刷新新增abort=${abortsR.length}`);
    expect(abortsR).toEqual([]);

    // 刷新不得 DELETE 掐断任务
    const delR = diag.streamReqs
      .slice(failBaseR)
      .filter((l) => l.includes('REQ DELETE') && l.includes('/chat/'));
    expect(delR).toEqual([]);

    // 刷新后 DB: 新任务仍在跑/已完成, 且历史任务未被误改
    const stNew = await statusOfTask(staleSession, taskNew);
    let stHistoryBad = '';
    for (const h of staleTaskIds) {
      const s = await statusOfTask(staleSession, h);
      if (s === 'executing') stHistoryBad = h;
    }
    console.log(
      `[E2E] 刷新后 新任务.status=${stNew} 历史任务里仍executing的=${stHistoryBad || '(无)'}`
    );
    expect(['executing', 'completed']).toContain(stNew);
    expect(stHistoryBad).toBe('');

    // 回到页面后 active 必须是新任务, 不是任何历史旧任务 —— 老陈 bug 的正面判据
    await expect
      .poll(async () => (await activeTaskId(page)) !== '', {
        timeout: 60_000,
        intervals: [500],
      })
      .toBeTruthy();
    const activeAfter2 = await activeTaskId(page);
    console.log(
      `[E2E] 刷新后 active=${activeAfter2}(应为新任务=${taskNew}; 历史任务=${JSON.stringify(staleTaskIds)})`
    );
    expect(activeAfter2).toBe(taskNew);

    // 轮次不丢
    const roundsAfter = seenRounds(diag.consoleAll, baseNew);
    const lost2 = roundsBefore.filter((r) => !roundsAfter.includes(r));
    console.log(
      `[E2E] 刷新后轮次数=${roundsAfter.length}(刷新前=${roundsBefore.length}) 丢失=${JSON.stringify(lost2)}`
    );
    expect(lost2).toEqual([]);

    // 终态必须 completed; failed/cancelled 打日志并显式红
    const stFinal = await pollTaskStatus(staleSession, taskNew, 420_000);
    console.log(`[E2E] 旧会话内新任务终态=${stFinal}`);
    if (stFinal === 'failed' || stFinal === 'cancelled') {
      const errLines = readLogSince(BLOG, logBase)
        .split('\n')
        .filter(
          (l) => l.includes(taskNew) && /ERROR|失败|error|Traceback/i.test(l)
        )
        .slice(-25);
      for (const l of errLines) console.log(`[E2E][DIAG] ${l.slice(0, 220)}`);
      throw new Error(
        `[E2E] 旧会话内新任务终态为 ${stFinal}(本 case 未点停止)。后端日志行数=${errLines.length}`
      );
    }
    expect(stFinal).toBe('completed');

    // 【北京老陈 2026-10-01 要求】刷新后 step 正常显示 + 计数器正常计数(同 14/15/16 口径)。
    //   本场景专属价值: 刷新前挂的是新任务, 刷新后若挂错到任何历史旧任务(都已完成) ——
    //   旧任务计数与新任务不同, 下面 ②③ 会先于 active===taskNew 那条判出来。
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
    expect(counterAfter.rounds).toBeGreaterThanOrEqual(counterAway.rounds);
    expect(counterAfter.steps).toBeGreaterThanOrEqual(counterAway.steps);
    expect(
      counterAfter.steps,
      counterFailMsg(
        '刷新后步数为 0 —— 累计计数没恢复(疑似挂到了已完成的旧任务)',
        counterAway,
        counterAfter
      )
    ).toBeGreaterThan(0);

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