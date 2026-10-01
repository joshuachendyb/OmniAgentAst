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
 * [63] 第六章 P6「关闭视图 ≠ 停止任务」红线全链路 E2E — 小欧 2026-09-30
 *
 * 环境: 普通会话流 `startNormalUiEnv`(vite dev:5173 + API 经 proxy → :8000)。真实浏览器/后端/LLM/SQLite。
 *
 * 验证目标(第六章 6.3 的 P6, 方法 M5「关闭视图 vs 停止任务分离法」):
 *   分两次操作并分别观察 network 与 DB:
 *     操作① 只关视图(切走) —— 任务继续跑; 零 abort / 零 clear / 零删备份
 *     操作② 再点停止   —— 此时才允许 cancel
 *   红线: `clear()` / abort / 删快照 只允许出现在 ②。
 *
 * 与 fre2e_05 的分工(勿重复造轮子):
 *   fre2e_05 验的是"切历史任务 A ↔ 切回实时 B"的**数据可见性**(isCurrentLive/正文/等待圈)。
 *   本 case 验的是**资源与状态**(是否误 abort、是否误清 Store、DB status 是否被误改), 二者正交。
 *
 * DB 判据来源: 后端 `GET /sessions/{id}/tasks` 的 `tasks[].status`(chat_tasks.status 权威),
 *   经原生 fetch 读(与 check_logs 同体系; 不直连 sqlite, 避免绕过后端封装)。
 *
 * 取证锚点: attachStreamDiag 的 allFailed(abort/ERR_ABORTED 探测) + streamReqs(全量网络)
 *          + 后端当日日志(按 task_id 过滤) + REST tasks 接口。
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试相关代码文件 —— 本 spec 严禁提交。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const API_BASE = 'http://127.0.0.1:8000/api/v1';

// 2026-10-01 小欧 - 本 case 的切走目标页(北京老陈裁定: 4 个前端 case 分派不同切走页面;
//   fre2e_13 用 /settings2, 本 case 用 /history, 覆盖两条不同的切换路径)
// 可用切走页只有 /history 与 /settings2: App.tsx 只注册 `/` `/history` `/settings2` `/login`,
//   /shortcuts、/files、/knowledge 都落到 `path="*"` 兜底渲染 ChatPage = 切了等于没切。
const AWAY_MENU_TEXT = '历史会话';
const AWAY_URL_PATH = '/history';
/** 用它反查 session_id 的唯一片段(必须是 PROMPT 里的原句, 见 resolveSessionIdByPrompt) */
const SESSION_TITLE_MATCH = '近地小行星采矿工程';

const activeTaskId = async (page: Page): Promise<string> => {
  const label = await page
    .locator('.task-list-item.active')
    .first()
    .getAttribute('aria-label');
  return label?.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '';
};

/** 读该会话最新任务的权威 status(chat_tasks.status; 走 REST 不绕后端封装) */
const latestTaskStatus = async (sessionId: string): Promise<string> => {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return `__http_${res.status}`;
  const d = (await res.json()) as {
    tasks?: { task_id: string; status: string }[];
    latest_task_id?: string;
  };
  const list = d.tasks ?? [];
  if (list.length === 0) return '__none__';
  const latest = d.latest_task_id;
  return (list.find((t) => t.task_id === latest) ?? list[list.length - 1])
    .status;
};

/**
 * 用 prompt 片段定位 session_id。
 *
 * 2026-10-01 小欧 — **不能靠 URL 取 session_id**: 会话页 URL 通常**不带** session_id
 * ([63]第八章定案"落到最近会话是常态", goto('/') 后 URL 保持 `/`), 原 `sessionIdFromUrl`
 * 时而拿到值时而拿到空串(fre2e_13 修复假通过时实测为空 → 断言直接红)。
 * 而本 case 的核心判据(切走/切回/停止后查 `chat_tasks.status`)必须要 session_id。
 * 改用后端接口反查: `GET /sessions` 的 `title` 即首条用户消息, 用 PROMPT 的唯一片段匹配,
 * 既能拿到 id 又能确认拿的是**本次**任务的会话(不会串到别的会话)。
 */
const resolveSessionIdByPrompt = async (promptPart: string): Promise<string> => {
  const res = await fetch(`${API_BASE}/sessions?page=1&page_size=50`);
  const data = await res.json();
  const hit = (data.sessions ?? []).find((s: { title?: string }) =>
    (s.title ?? '').includes(promptPart)
  );
  return hit?.session_id ?? '';
};

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

test.describe('[63] P6 红线 · 关视图不等于停止任务', () => {
  test('操作①只切走: 零abort/零clear/status仍executing/后续步骤可见; 操作②点停止: 才cancel', async ({
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

    // 等到 ≥2 轮, 让"操作①"落在任务中段
    const dl = Date.now() + 240_000;
    while (
      Date.now() < dl &&
      seenRounds(diag.consoleAll, frameBase0).length < 2
    ) {
      await page.waitForTimeout(500);
    }
    const taskId = await activeTaskId(page);
    // session_id 靠 prompt 反查(URL 不带, 详见 resolveSessionIdByPrompt 注释)
    const sessionId = await resolveSessionIdByPrompt(SESSION_TITLE_MATCH);
    expect(taskId).toBeTruthy();
    expect(sessionId).toBeTruthy();
    const statusBefore = await latestTaskStatus(sessionId);
    console.log(
      `[E2E] 操作前: task=${taskId} session=${sessionId} status=${statusBefore}`
    );

    // ══ 操作①: 只关视图(切走到历史页), 不点停止 ══
    const reqBase1 = diag.streamReqs.length;
    const consoleBase1 = diag.consoleAll.length;
    const failBase1 = diag.allFailed.length;
    const logBase1 = logBaseOf(BLOG);

    // 2026-10-01 小欧 — **修复假通过**(headed 人工复核, 北京老陈"看不到页面切换"发现):
    //   原实现切走与切回**都点「对话任务」**, 而 [63]第八章(2026-09-30 v1.42/v1.43)已把该项
    //   改为"显式带回当前 session_id" → 两次落点同一个 `/?session_id=<当前>`, **视图从未关闭**。
    //   于是"关视图不停止任务"这条红线根本没被触发, 断言全在同一页面内自然通过。
    //   本 case 切走改用「历史会话」(/history) —— 与 fre2e_13 的 /settings2 分派到不同页面,
    //   避免两个 case 只覆盖同一条切换路径(北京老陈裁定: 4 个 case 分派不同切走页面)。
    //   注: /shortcuts、/files、/knowledge 不能用 —— App.tsx 只注册 `/` `/history` `/settings2`
    //   `/login`, 这三个落到 `path="*"` 兜底渲染 ChatPage, URL 变了但页面没变。
    const urlAtAway = page.url();
    await page
      .locator('.ant-menu-item', { hasText: AWAY_MENU_TEXT })
      .first()
      .click();
    await page.waitForTimeout(6000);
    // 防假通过硬断言: 视图必须真的关闭(URL 变了且落在目标页), 否则后续红线断言全部空转
    const urlAfterAway = page.url();
    console.log(`[E2E] 操作① 切走: ${urlAtAway} -> ${urlAfterAway}`);
    expect(urlAfterAway).not.toBe(urlAtAway);
    expect(urlAfterAway).toContain(AWAY_URL_PATH);

    // ①a 零 abort: allFailed 不得新增 ERR_ABORTED / ABORTED
    const aborts = diag.allFailed
      .slice(failBase1)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 操作① 新增请求失败=${diag.allFailed.length - failBase1} 其中abort=${aborts.length}`
    );
    expect(aborts).toEqual([]);

    // ①b 零 clear: 切走不得触发 clearSteps / clearCompleted
    //    编辑历史 2026-09-30 小欧 - 两处修正:
    //      ① 原 `clearsInConsole` 用 .slice(0) 取全量、`clearsAfterAway` 写成
    //         .slice(len-(len-0)) 等价也是全量 —— 所谓"新增"是废表达式, 恒等于全量。改用真基线。
    //      ② **删掉"STORAGE_KEY 必须还在"这条断言**(首跑即红, 经查证是我的断言写错, 非产品缺陷):
    //         STORAGE_KEY 是**单槽**(只存一个会话的态), 且有两条正当清除路径 ——
    //           useChatPersistence.ts:309 缓存消息无 display_name 即丢弃(在飞任务的用户消息此刻
    //             还没有 display_name, 它随 AI 回复才写入 → 切走必然命中该分支);
    //           useChatSession.ts:534 新建会话时清槽。
    //         二者都是**缓存有效性规则**, 不是 P6 红线所指"删任务备份/掐断任务"。P6 红线是任务级
    //         资源(abort / clearSteps / cancel / DELETE), 那些在下面逐条断言。
    const clearsAfterAway = diag.consoleAll
      .slice(consoleBase1)
      .filter((l) => /clearSteps|clearCompleted/.test(l));
    const storageKeyGone = await page.evaluate(
      () => sessionStorage.getItem('chat_session_state') === null
    );
    console.log(
      `[E2E] 操作① 切走后新增 clear类console=${clearsAfterAway.length}` +
        `(STORAGE_KEY 已消失=${storageKeyGone} — 单槽+缺display_name规则, 非红线, 仅记录)`
    );
    expect(clearsAfterAway).toEqual([]);

    // ①c 零 DELETE /chat/**
    const deletes = diag.streamReqs
      .slice(reqBase1)
      .filter((l) => l.includes('REQ DELETE') && l.includes('/chat/'));
    expect(deletes).toEqual([]);

    // ①d DB status 仍 executing(未被误取消/误改终态)
    const statusAfterAway = await latestTaskStatus(sessionId);
    console.log(
      `[E2E] 操作① 后 status=${statusAfterAway}(操作前=${statusBefore})`
    );
    if (statusBefore === 'executing') {
      expect(statusAfterAway).toBe('executing');
    }

    // ①e 后端日志无该 task 的 cancel/abort 痕迹
    const tailAway = readLogSince(BLOG, logBase1);
    const cancelLines = tailAway
      .split('\n')
      .filter((l) => l.includes(taskId) && /cancel|取消|abort/i.test(l));
    expect(cancelLines).toEqual([]);

    // ①f 切回后任务仍在跑, 后续步骤可见(证明"关视图没停任务"——红线的正面证据)
    const roundsAtAway = seenRounds(diag.consoleAll, frameBase0);
    await page
      .locator('.ant-menu-item', { hasText: '对话任务' })
      .first()
      .click();
    await page.waitForTimeout(3000);
    // 防假通过硬断言: 切回必须真的回到会话页, 且带回原会话(不是新会话)
    const urlAfterBack = page.url();
    console.log(`[E2E] 切回: ${urlAfterAway} -> ${urlAfterBack}`);
    expect(urlAfterBack).not.toBe(urlAfterAway);
    expect(urlAfterBack).toContain(`session_id=${sessionId}`);
    const roundsBack = seenRounds(diag.consoleAll, frameBase0);
    console.log(
      `[E2E] 切回后轮次数=${roundsBack.length}(切走时=${roundsAtAway.length})`
    );
    // 正面证据1: 该运行中任务仍在任务列表里(没被清掉)
    const stillListed = await page
      .locator(`.task-list-item[aria-label*="${taskId}"]`)
      .count();
    console.log(
      `[E2E] 切回后该 task 在列表中的条数=${stillListed}(应>=1, 未被清掉)`
    );
    expect(stillListed).toBeGreaterThanOrEqual(1);
    // 正面证据2: 切走期间已收到的轮次一个都没丢
    const lostRounds = roundsAtAway.filter((r) => !roundsBack.includes(r));
    expect(lostRounds).toEqual([]);
    // 任务未提前终态时, 切回后应仍在接收(停止钮可见)
    if (statusAfterAway === 'executing') {
      await expect(chat.stopBtn).toBeVisible({ timeout: 20_000 });
    }

    // ══ 操作②: 点停止 —— 此时才允许 cancel ══
    const reqBase2 = diag.streamReqs.length;
    if (await chat.stopBtn.isVisible().catch(() => false)) {
      await chat.stopBtn.click();
      await page.waitForTimeout(6000);
    } else {
      console.log('[E2E] 任务已自然终态, 停止按钮不可见 → 跳过操作②(不伪造)');
    }

    const statusAfterStop = await latestTaskStatus(sessionId);
    console.log(`[E2E] 操作② 后 status=${statusAfterStop}`);

    // ②a 若点了停止, 终态必须是终态之一(不得仍 executing)
    expect(['completed', 'failed', 'cancelled', 'executing']).toContain(
      statusAfterStop
    );

    // ②b 停止后 DB 落终态(若曾 executing 则必须已转终态; STOP_RACE 任务已自然完成也算合法终态)
    if (statusAfterAway === 'executing' && statusAfterStop === 'executing') {
      // 停止请求可能仍在飞行, 给一次收敛窗口再判
      await page.waitForTimeout(8000);
      const s2 = await latestTaskStatus(sessionId);
      console.log(`[E2E] 操作② 收敛窗口后再查 status=${s2}`);
      expect(s2).not.toBe('executing');
    }

    // ②c 允许出现 cancel/取消 请求(红线只禁出现在 ①, 此处不设否)
    const cancels = diag.streamReqs
      .slice(reqBase2)
      .filter((l) => /cancel/i.test(l));
    console.log(`[E2E] 操作② 新增 cancel 相关请求=${cancels.length}`);

    // ③ 通用区
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
