import { test, expect } from '@playwright/test';
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
  activeTaskId,
  taskStatusInList,
  readStepCounter,
  counterFailMsg,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * E2E-14 新会话·任务执行中·按 F5·验刷新后从断点续传
 *
 * 做什么: 发一条长任务, 等它跑到第 3 轮(执行中), 按 F5, 等它跑完。
 *   刷新前地址栏是 /?session_id=<id>, 刷新后不变 → 走 useChatSession 场景1。
 * 断什么: F5 清空内存, 步骤全没。必须自己发 GET /chat/stream/{task}?after_seq=N
 *   从「最后一个序号+1」接着收, 而不是从头重收。
 * 判据: ①发出带 after_seq 的 GET ②after_seq == 刷新前 lastSeq+1
 *      ③后端续传起点 seq 与之一致且帧数>0 ④已转发==缓冲总长(不漏帧), 末帧是 final_stats
 *      ⑤刷新前的轮次不丢 ⑥左侧列表从「执行中」自己到「已完成」
 *
 * 编辑历史: 曾在此 page.goto('/') 剥掉 session_id 去测裸地址栏刷新, 与 fre2e_17 场景①
 *   重复且丢了本 case 该守的带参路径, 已撤销(2026-10-01 小欧)。
 * 铁规: AGENTS.md 禁止 commit 测试文件。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

/**
 * 2026-10-01 小欧 [1] D组: 从页面内直读恢复链真实状态(诊断用)。
 *
 * 背景: 续传请求没发出, 但不知卡在恢复链哪一环。生产代码不留 log(不污染),
 * 故 E2E 侧从 sessionStorage 备份 + 运行时可见状态取证, 定位是
 *   restore(invalid? / status 终态?) → recoverWithoutTaskId → attachActiveTask → resumeStreamRequest
 * 哪一步断的。读不到给空串, 不猜。
 */
const readRestoreState = async (
  page: import('@playwright/test').Page
): Promise<Record<string, unknown>> =>
  page.evaluate(async () => {
    const backups: Record<string, unknown> = {};
    for (const k of Object.keys(sessionStorage)) {
      try {
        const parsed = JSON.parse(sessionStorage.getItem(k) ?? 'null');
        // 备份只取顶层标量字段(steps/frames 体积极大, 截断会淹掉锚点真值)
        if (parsed && typeof parsed === 'object' && 'taskId' in parsed) {
          const { steps, frames: _frames, ...anchors } = parsed as Record<
            string,
            unknown
          >;
          backups[k] = {
            ...anchors,
            _stepsLen: Array.isArray(steps) ? steps.length : -1,
          };
        } else {
          backups[k] = parsed;
        }
      } catch {
        backups[k] = '<非JSON>';
      }
    }
    const activeEl = document.querySelector('.task-list-item.active');
    return {
      storageKeys: Object.keys(sessionStorage),
      backups,
      activeAriaLabel: activeEl?.getAttribute('aria-label') ?? '',
      allTaskLabels: Array.from(
        document.querySelectorAll('.task-list-item')
      ).map((e) => e.getAttribute('aria-label')),
    };
  });

/** 直调 listTasks API 取原始返回(created_at 格式/status 是 findLiveTask 的判据, 必须看真值) */
const readRawTasks = async (
  page: import('@playwright/test').Page,
  sessionId: string
): Promise<unknown> =>
  page.evaluate(async (sid) => {
    try {
      const r = await fetch(`/api/v1/chat/sessions/${sid}/tasks?limit=10`);
      return { status: r.status, body: (await r.text()).slice(0, 1500) };
    } catch (e) {
      return { error: String(e) };
    }
  }, sessionId);

/** 从日志片段里取该 task 已转发过的最大 seq */
const maxSeqOf = (logText: string, taskId: string): number => {
  const a = [
    ...logText.matchAll(new RegExp(`seq=(\\d+)[^\\n]*${taskId}`, 'g')),
  ].map((m) => Number(m[1]));
  const b = [
    ...logText.matchAll(new RegExp(`${taskId}[^\\n]*seq=(\\d+)`, 'g')),
  ].map((m) => Number(m[1]));
  return Math.max(0, ...a, ...b);
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

test.describe('[63] P2 刷新续传 · after_seq 断点', () => {
  test('中途刷新: 发 GET after_seq=lastSeq+1 / 续传帧不重放 / seq 单调无回退', async ({
    page,
  }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    // 1) 环境 + 进页
    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    // 2) 发长活期多步任务(同 FE-1 形态, 活期 60s+ 才容得下刷新窗口)
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

    const frameBase0 = diag.consoleAll.length;
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

    // 3) 等到 ≥3 轮作为刷新断点
    const dl = Date.now() + 240_000;
    while (
      Date.now() < dl &&
      seenRounds(diag.consoleAll, frameBase0).length < 3
    ) {
      await page.waitForTimeout(500);
    }
    const roundsBefore = seenRounds(diag.consoleAll, frameBase0);
    const taskId = await activeTaskId(page);
    expect(taskId).toBeTruthy();
    if (roundsBefore.length < 3) {
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
        `[E2E] 窗口错过: 刷新前仅 ${roundsBefore.length} 轮(<3)——请重跑以覆盖刷新续传分支`
      );
    }

    const lastSeqBefore = maxSeqOf(readLogSince(BLOG, logBase), taskId);
    // 2026-10-01 小欧 [1] D组: 记下列表 status 基线, 供刷新后比对(判「列表能否自动到终态」)
    const statusBefore = await taskStatusInList(page, taskId);
    console.log(
      `[E2E] 刷新前: task=${taskId} 轮次=${roundsBefore.length} lastSeq=${lastSeqBefore} 列表status=${statusBefore}`
    );

    // 北京老陈 2026-10-01 要求: 刷新后 step 还在不在正常显示、计数器还在不在正常计数。
    //   先读刷新前的基线, 刷新后与它比 —— 刷新后计数器"从 0 重来"或"整个不显示"都是缺陷。
    const counterBefore = await readStepCounter(page);
    console.log(
      `[E2E] 刷新前计数器: ${counterBefore ? `轮=${counterBefore.rounds} 步=${counterBefore.steps}` : '(读不到)'}`
    );
    if (!counterBefore) {
      throw new Error(
        `[E2E] 刷新前读不到顶栏计数器 —— 步骤/step 本来就没显示。不当通过处理`
      );
    }
    expect(counterBefore.steps).toBeGreaterThan(0);

// ═══ 动作: 按 F5 整页重载(JS 上下文重建 —— 内存 Store 全失, 只能靠持久化 + 续传恢复) ═══
    // 2026-10-01 小欧 场景归属: 本 case 只管**「地址栏带 session_id 时刷新」**这一支。
    //   编辑历史: 此前我曾在此加 `page.goto('/')` 剥掉 query 改测「裸地址栏刷新」, 那与
    //   fre2e_17 场景①完全重复, 且把本 case 原本要守的「带参」路径丢了 —— 已撤销, 恢复原状。
    //   裸地址栏刷新(useChatSession 场景3)由 fre2e_16(无 taskId)、fre2e_17(旧会话)各守其位。
    //   依据 useChatSend.ts:145-154 —— 地址栏参数只在本标签页「新建会话」时写入;
    //   所以本 case 新建会话后地址栏必带 id, F5 后走 useChatSession 场景1, 是该分支的正当防线。
await page.reload();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    // 5) 等续传请求出现(网络面: GET /chat/stream/{task_id}?…&after_seq=N)
    const hasAfterSeqReq = (): boolean =>
      diag.streamReqs.some(
        (l) =>
          l.includes('REQ GET ') &&
          l.includes('/chat/stream/') &&
          l.includes('after_seq=')
      );
    await expect
      .poll(hasAfterSeqReq, { timeout: 120_000, intervals: [500] })
      .toBeTruthy()
      .catch(async (e) => {
        // 2026-10-01 小欧 [1] D组: 续传未发出时先取证再抛 —— 定位恢复链断在哪一环
        const st = await readRestoreState(page);
        console.log(
          `[E2E][DIAG] 续传未发出。storageKeys=${JSON.stringify(st.storageKeys)}`
        );
        console.log(
          `[E2E][DIAG] activeAriaLabel=${String(st.activeAriaLabel)}`
        );
        console.log(
          `[E2E][DIAG] allTaskLabels=${JSON.stringify(st.allTaskLabels)}`
        );
        for (const k of st.storageKeys) {
          console.log(
            `[E2E][DIAG] backup[${k}]=${JSON.stringify(
              (st.backups as Record<string, unknown>)[k]
            )}`
          );
        }
        const sidFromKey = st.storageKeys
          .map((k) =>
            /^sse_execution_steps_backup_v2_(.+)$/.exec(String(k))?.[1]
          )
          .find(Boolean) as string | undefined;
        if (sidFromKey) {
          const raw = await readRawTasks(page, sidFromKey);
          console.log(
            `[E2E][DIAG] rawTasks(session=${sidFromKey})=${JSON.stringify(raw)}`
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
        throw e;
      });

    // 北京老陈 2026-10-01 要求: 刷新后 step 还在不在正常显示、计数器还在不在正常计数。
    //   14 的核心是「续传」, 所以此处不只判"计数没丢", 更判**它还在继续涨** ——
    //   续传 GET 发出、帧也到了后端日志, 但页面计数器不涨 = 帧没真正落到 UI,
    //   那正是老陈截图的现象(任务在跑, 页面 step 不动)。
    //   判据(与 15/16/17 同口径, 共用 lib/step-counter):
    //   ① 计数器读得到      —— 读不到 = step 不显示 = 不过
    //   ② 轮/步 >= 刷新前   —— 变小 = 累计被清零 = 不过
    //   ③ 90s 内继续上涨    —— 不涨 = 续传没真推帧 = 不过
    //   基线是刷新前的 counterBefore。刻意放在**续传请求已发出之后**再判:
    //   刷新瞬间页面刚重建, 计数器尚未接上, 那时的读数不作数。
    const counterResume = await waitCounterIncreases(
      page,
      counterBefore.rounds,
      counterBefore.steps,
      90_000
    );
    console.log(
      `[E2E] 刷新后续传中计数器: ${counterResume ? `轮=${counterResume.rounds} 步=${counterResume.steps}` : '(读不到)'}` +
        ` (刷新前 轮=${counterBefore.rounds} 步=${counterBefore.steps})`
    );
    if (!counterResume) {
      throw new Error(
        `[E2E] 刷新后续传中读不到顶栏计数器 —— step 没有正常显示。` +
          counterFailMsg('TaskInfoBar 刷新后未渲染', counterBefore, null) +
          ` —— 不当通过处理`
      );
    }
    expect(counterResume.rounds).toBeGreaterThanOrEqual(counterBefore.rounds);
    expect(counterResume.steps).toBeGreaterThanOrEqual(counterBefore.steps);
    expect(
      counterResume.rounds > counterBefore.rounds ||
        counterResume.steps > counterBefore.steps,
      counterFailMsg(
        '续传请求已发出, 但刷新后计数器一直不涨 —— 帧没落到 UI, 页面看着像卡住',
        counterBefore,
        counterResume
      )
    ).toBeTruthy();

    const reqLine =
      diag.streamReqs.find(
        (l) =>
          l.includes('REQ GET ') &&
          l.includes('/chat/stream/') &&
          l.includes('after_seq=')
      ) ?? '';
    const afterSeqReq = Number(reqLine.match(/after_seq=(\d+)/)?.[1] ?? '-1');
    console.log(`[E2E] 续传请求: after_seq=${afterSeqReq}  <- ${reqLine}`);

    // 6) 断言
    // ① after_seq == 刷新前 lastSeq + 1(前端单基线语义; 后端 query 约束 ge=0)
    expect(afterSeqReq).toBe(lastSeqBefore + 1);

    // ② 续传口径核对 —— 用后端**自己的续传汇总行**, 不扫逐帧
    //    编辑历史 2026-09-30 小欧 - 两次踩坑后定稿:
    //      ① 首版正则 `${taskId}[^\n]*?seq=(\d+)` 要求 task_id 在 seq 之前, 真实格式是
    //         `[SSE] seq=<N> task=<id>`(seq 在前) → 提取恒空;
    //      ② 二版按真实格式 `[SSE] seq=N task=id` 仍提取 0 条 —— 因为**续传阶段后端不再逐帧打
    //         seq DEBUG**, 只在收尾打一行汇总(实测 2964 条逐帧行全部来自刷新前的开流阶段):
    //           [SSE] reader退出(task=..., is_reconnect=True, 起点seq=N, 续传帧数=M,
    //                              已转发=F, 缓冲总长=B, 末类型=final_stats, 含final_stats=True)
    //         故改为解析该汇总行 —— 它是后端对本次续传的权威记账, 比前端侧推算更可信。
    const logBaseAfterReload = logBaseOf(BLOG);
    await chat.waitDone(420_000);
    //    编辑历史 2026-09-30 小欧 - 第三坑(竞态): 该汇总行由**后端 reader 退出时异步写**,
    //    而 waitDone 等的是**前端 UI**(发送钮复现), 两者无因果顺序 → 读完立刻查日志会读早。
    //    实测同一条用例: 340s 那轮读到, 160s 那轮读不到(Received: null)。
    //    改为轮询等待该行出现(最多 60s), 超时才失败并落全量 DIAG。
    const reReconnect = new RegExp(
      `reader退出\\(task=${taskId}, is_reconnect=(\\w+), 起点seq=(\\d+), 续传帧数=(\\d+), ` +
        `已转发=(\\d+), 缓冲总长=(\\d+), 末类型=(\\w+), 含final_stats=(\\w+)\\)`
    );
    let tailAfter = '';
    let mReconnect: RegExpMatchArray | null = null;
    const dlSummary = Date.now() + 60_000;
    while (Date.now() < dlSummary) {
      tailAfter = readLogSince(BLOG, logBaseAfterReload);
      mReconnect = tailAfter.match(reReconnect);
      if (mReconnect) break;
      await page.waitForTimeout(1000);
    }
    if (!mReconnect) {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        tailAfter,
        diag.allFailed,
        getCaseId()
      );
    }
    expect(
      mReconnect,
      '后端日志缺续传汇总行(reader退出 is_reconnect=True)(MUST)'
    ).not.toBeNull();
    const [
      ,
      isReconnect,
      startSeq,
      tailFrames,
      forwarded,
      bufLen,
      lastType,
      hasFs,
    ] = mReconnect as RegExpMatchArray; // 上一行 expect 已断言非 null, 此处仅为满足 TS
    console.log(
      `[E2E] 续传汇总: is_reconnect=${isReconnect} 起点seq=${startSeq} 续传帧数=${tailFrames} ` +
        `已转发=${forwarded} 缓冲总长=${bufLen} 末类型=${lastType} 含final_stats=${hasFs}`
    );

    // ②a 确为续传(非首次开流)
    expect(isReconnect).toBe('True');
    // ②b 起点 seq 与前端请求的 after_seq 一致(前后端单基线语义闭环)
    expect(Number(startSeq)).toBe(afterSeqReq);
    expect(Number(startSeq)).toBe(lastSeqBefore + 1);
    // ②c 续传必须有帧(空 = 续传没生效)
    expect(Number(tailFrames)).toBeGreaterThan(0);
    // ②d 已转发 == 缓冲总长(无缺口: 缓冲里每一帧都转发了, 续传不漏帧)
    expect(Number(forwarded)).toBe(Number(bufLen));
    // ②e 续传把终态补回来了(刷新前只拿到中途帧, 终态必须靠续传送达)
    expect(hasFs).toBe('True');
    expect(lastType).toBe('final_stats');

    // ③ 刷新前已收到的轮次, 恢复后不得丢失
    const roundsAfter = seenRounds(diag.consoleAll, 0);
    const lost = roundsBefore.filter((r) => !roundsAfter.includes(r));
    console.log(
      `[E2E] 恢复后轮次数=${roundsAfter.length} 刷新前=${roundsBefore.length} 丢失=${JSON.stringify(
        lost
      )}`
    );
    expect(lost).toEqual([]);

    // ④ 终态正文完整
    const finalText = await chat.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('近地小行星采矿工程');

    // ⑤ [1] D组 左侧任务列表终态断言
    //   背景: 此前本 case 只断言 SSE 层(续传帧数/含final_stats/末类型), 从未断言 UI 层列表状态 ——
    //   后端终态帧确实补回来了, 但左侧列表可能仍停在「执行中」(老陈截图现象: 左侧还指向、右侧已完成)。
    //   刷新后无 SSE 之外的任何列表刷新信号, 故此处必须显式断言, 否则该缺陷能全绿通过。
    //   判据: 终态帧已由续传送达(hasFs=True/末类型=final_stats 已断言), 则列表 status 必须离开 executing。
    //   给 30s 观察窗 —— 若真靠轮询兜底(当前无), 3s 内也该到; 30s 是宽松上限, 超时即 FAIL(不豁免)。
    const dlStatus = Date.now() + 30_000;
    let statusAfter = await taskStatusInList(page, taskId);
    while (
      Date.now() < dlStatus &&
      (statusAfter === 'executing' || statusAfter === '')
    ) {
      await page.waitForTimeout(500);
      statusAfter = await taskStatusInList(page, taskId);
    }
    console.log(
      `[E2E] 列表status: 刷新前=${statusBefore} 终态后=${statusAfter} (task=${taskId})`
    );
    if (statusAfter === statusBefore && statusAfter === 'executing') {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        tailAfter,
        diag.allFailed,
        getCaseId()
      );
    }
    // 列表不得停在 executing —— 终态帧已送达却仍显示执行中 = D 组缺陷复现
    expect(
      statusAfter,
      `左侧列表 status 卡在 ${statusAfter}(刷新前=${statusBefore}); 终态帧已续传送达但列表未刷新 —— D 组缺陷复现`
    ).not.toBe('executing');
    // 且必须落到真实终态(不猜具体值, 只排除非终态)
    // 2026-10-01 小欧 [1] 纠错: 原列表含 'interrupted' —— 核实后端 storage.py:490-491,
    //   孤儿任务收尾写的是 `status='failed', error_type='task_interrupted'`,
    //   **interrupted 是 error_type 不是 status**, 永不会是 chat_tasks.status 的值。
    //   列进去等于给"不可能发生"开了个口子, 反向放宽判据。已删。
    expect(['completed', 'failed', 'cancelled']).toContain(statusAfter);
    // 2026-10-01 小欧 [1] 自查补漏: 上面那行把 failed/cancelled 也算"合法终态"放过了,
    //   但本 case 全程没点停止、任务是纯文稿, 落到 failed 必是产品问题, 不能就这么绿过去。
    //   与 fre2e_15/16 同口径: failed → 打后端 ERROR 行并显式红, 逼出根因。
    if (statusAfter === 'failed' || statusAfter === 'cancelled') {
      const errLines = tailAfter
        .split('\n')
        .filter((l) => l.includes(taskId) && /ERROR|失败|error|Traceback/i.test(l))
        .slice(-25);
      for (const l of errLines) console.log(`[E2E][DIAG] ${l.slice(0, 220)}`);
      throw new Error(
        `[E2E] 续传后任务终态为 ${statusAfter}(本 case 未点停止, 非正常终态)。` +
          `后端相关日志行数=${errLines.length}，见上方 DIAG`
      );
    }

    // 6) 【北京老陈 2026-10-01 要求】刷新后 step 还在正常显示, 计数器还在正常计数。
    //   本 case 的判据重心是续传帧, 但"帧到了"不等于"页面上看得到 step 在走" ——
    //   若续传只补了终态帧而没把累计计数带回来, 页面会显示 step 很小甚至不显示, 老陈截图
    //   就是这类现象。故补 UI 层判据, 与 15/16/17 同口径(共用 lib/step-counter)。
    // 判据:
    //   ① 刷新后计数器读得到        —— 读不到 = step 不显示 = 不过
    //   ② 轮/步都 >= 刷新前         —— 变小 = 累计被清零/挂错任务 = 不过
    //   ③ 步数 > 0 且 <= 刷新前+本次续传的自然增量(不猜具体值, 只卡"必须至少有步")
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
    // 步数必须为正: 刷新后若 step 显示 0, 说明累计没恢复, 页面等于"从头空白"在跑
    expect(
      counterAfter.steps,
      counterFailMsg(
        '刷新后步数为 0 —— 累计计数没恢复, 页面看起来像从头开始',
        counterBefore,
        counterAfter
      )
    ).toBeGreaterThan(0);

    // 5) 通用区
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      tailAfter,
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });
});
