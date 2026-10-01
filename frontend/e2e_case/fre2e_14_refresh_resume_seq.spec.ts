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
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * [63] 第六章 P2「刷新续传」全链路 E2E — 小欧 2026-09-30
 *
 * 环境: 普通会话流 `startNormalUiEnv`(vite dev:5173 + API 经 proxy → :8000)。真实浏览器/后端/LLM/SQLite。
 *
 * 验证目标(第六章 6.1 的 L2 防线 + 6.3 的 P2):
 *   刷新页面(300s 窗口内)自动发 `GET /chat/stream/{id}?after_seq=N` 续传, 拿回刷新期间新步骤。
 *
 * 判据(第六章 M6 seq 单调性校验):
 *   ① 出现带 after_seq 的 GET 续传请求
 *   ② after_seq == 刷新前 lastSeq + 1(前端单基线语义: 已处理最大 seq 的下一个)
 *   ③ 后端续传汇总行 起点seq == 同一 after_seq(前后端口径闭环), 续传帧数 > 0
 *   ④ 已转发 == 缓冲总长(续传不漏帧), 且末类型 = final_stats(终态靠续传送达)
 *   ⑤ 刷新前已收到的轮次, 恢复后不得丢失
 *
 *   注: ③ 不用"逐帧 seq 序列单调"来判 —— 实测续传阶段后端**不再逐帧打 seq DEBUG**
 *   (那 2,964 条逐帧行全部来自刷新前的开流阶段), 只有收尾一行汇总。改用后端权威记账,
 *   比前端侧推算更可信。两次踩坑记录见该段"编辑历史"。
 *
 * 与第六章原文的差异(勿误读):
 *   第六章 P4 写"超 300s → GET 返回 not_found"。现状核实: **后端没有 300 秒硬窗** ——
 *   300s 只是内存缓冲回收(agent_runner.py:792 call_later(300, reclaim_memory_buffer)),
 *   Journal 保留期 7 天(config.yaml:264), 回放终止判据是 producer 60 秒活窗 + 终态事件。
 *   故本 case 只验"300s 窗口内刷新能续传"(L2 本义); 超窗/重启回放由后端 BE-1/BE-2 覆盖。
 *
 * 取证锚点:
 *   - 续传请求与 after_seq: attachStreamDiag.streamReqs(网络面) + 后端日志 `重连请求接收 ... after_seq=N`
 *   - lastSeq: 后端当日日志 `[SSE] seq=<N> task=<task_id>`(DB 权威序号)
 *   - 轮次:    sseParser 帧日志 `轮次=X`
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试相关代码文件 —— 本 spec 严禁提交。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

/** 任务列表 active 项的 task_id */
const activeTaskId = async (
  page: import('@playwright/test').Page
): Promise<string> => {
  const label = await page
    .locator('.task-list-item.active')
    .first()
    .getAttribute('aria-label');
  return label?.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '';
};

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
    console.log(
      `[E2E] 刷新前: task=${taskId} 轮次=${roundsBefore.length} lastSeq=${lastSeqBefore}`
    );

    // 4) 刷新(整页重载, JS 上下文重建 —— 内存 Store 全失, 只能靠持久化 + 续传恢复)
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
      .toBeTruthy();

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
