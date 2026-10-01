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
 * [63] 第六章 P1「实时切页」全链路 E2E — 小欧 2026-09-30
 *
 * 环境: 普通会话流 `startNormalUiEnv`(页面 vite dev:5173, API 相对路径经 proxy → :8000, 无 9000 代理,
 *   本 case 不含断流)。前置: 后端 :8000 手动启动。真实浏览器 + 真实后端 + 真实 LLM + 真实 SQLite。
 *
 * 验证目标(第六章 6.1 的 L1 防线 + 6.3 的 P1):
 *   切走再切回, step 从断点续增; POST 次数 = 1; taskId 不变; 不重新初始化(F7)。
 *
 * F7 判据说明(与第六章原文的差异, 勿误读):
 *   第六章 6.2 M3 要求"在 useChatInit.initializeSession 入口打 window.__initCount 计数"。
 *   现状: chatStreamStore / useChatInit **未向 window 暴露任何内部探针**(全仓无 window.__chatStream*),
 *   为跑测试而改生产代码暴露内部状态违反"禁止为测试改生产码", 故本 case 改用**网络面等价代理**:
 *   重新初始化必然伴随 ① 二次 `POST /chat/stream`(建新任务) ② 二次 `GET /sessions/{id}/messages`
 *   (loadSession 补历史), 二者都不出现 + taskId 不变 + 轮次续增(非从头) ⇒ 未重新初始化。
 *   另: useChatInit 的 effect 依赖仅 `[urlSessionId]`, 切走切回 URL 未变时该 effect 本就不重跑。
 *
 * 取证锚点:
 *   - 网络面: attachStreamDiag 的 streamReqs(REQ/RES/FAIL 全量)
 *   - 轮次:    sseParser 帧日志 `[HH:MM:SS.mmm] 轮次=X type`(替代已删 DBG-1), 与 fre2e_05 同源
 *   - taskId:  DOM `.task-list-item.active` 的 aria-label="任务 <task_id> <name>"
 *   - lastSeq: 后端当日日志 `[SSE] seq=<N> task=<task_id>`(DB 权威序号)
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试相关代码文件 —— 本 spec 严禁提交。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';

// 2026-10-01 小欧 - 本 case 的切走目标页(北京老陈裁定: 4 个前端 case 分派不同切走页面,
//   本 case 用「设置2版」; 详见 gotoAway 注释里那个假通过的成因)
// 可用切走页只有 /history 与 /settings2: App.tsx 只注册 `/` `/history` `/settings2` `/login`,
//   /shortcuts 与 /files、/knowledge 都落到 `path="*"` 兜底渲染 ChatPage = 切了等于没切。
const AWAY_MENU_TEXT = '设置2版';
const AWAY_URL_PATH = '/settings2';

/** 任务列表 active 项的 task_id(aria-label="任务 <task_id> <name>") */
const activeTaskId = async (page: Page): Promise<string> => {
  const label = await page
    .locator('.task-list-item.active')
    .first()
    .getAttribute('aria-label');
  return label?.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '';
};

/** 从 sseParser 帧日志提取"已出现过的轮次集合"(按出现顺序去重) */
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

/** 统计 streamReqs 里某方法的 chat/stream 请求条数 */
const countStreamReq = (reqs: string[], method: string): number =>
  reqs.filter((l) => l.includes(`REQ ${method} `) && l.includes('/chat/stream'))
    .length;

/** 统计指定路径的 GET 条数(用于"是否二次 loadSession"判据) */
const countGetMessages = (reqs: string[]): number =>
  reqs.filter(
    (l) =>
      l.includes('REQ GET ') &&
      l.includes('/sessions/') &&
      l.includes('/messages')
  ).length;

/** 无限渲染告警检测(P7: useSyncExternalStore 快照未缓存 / setState 死循环) */
const infiniteRenderWarnings = (all: string[]): string[] =>
  all.filter((l) =>
    /Maximum update depth exceeded|getSnapshot should be cached|should be cached to avoid an infinite loop/i.test(
      l
    )
  );

/** 切回"对话任务"页(菜单项; [63]第八章 2026-09-30 起该项带 session_id 回当前会话) */
const gotoChatTask = async (page: Page): Promise<void> => {
  await page.locator('.ant-menu-item', { hasText: '对话任务' }).first().click();
  await page.waitForTimeout(1500);
};

/**
 * 切走到指定菜单页(真切走)。本 case 用「设置2版」(/settings2)。
 *
 * 编辑历史 2026-10-01 小欧 — **修复一个假通过**(headed 人工复核时由北京老陈发现"看不到页面切换"):
 *   原实现切走与切回**都点「对话任务」**, 而 [63]第八章(2026-09-30 v1.42/v1.43)已把该项改为
 *   "显式带回当前 session_id" → 两次落点同一个 `/?session_id=<当前>`, **页面从未离开会话页**。
 *   于是 POST=1 / taskId不变 / 轮次续增 等断言全在同一页面内自然通过, 属**假通过**,
 *   本 case 名为"切走→切回"却从未切走, F1/F2/F5/F7 全部未被验证。
 *   注意 `/shortcuts`、`/files`、`/knowledge` **不能**当切走目标: App.tsx 只注册了
 *   `/` `/history` `/settings2` `/login`, 这三个会落到 `path="*"` 兜底渲染 ChatPage,
 *   URL 变了但页面没变 —— 会重蹈同一覆辙。可用切走页只有 /history 与 /settings2。
 */
const gotoAway = async (page: Page, menuText: string): Promise<void> => {
  await page.locator('.ant-menu-item', { hasText: menuText }).first().click();
  await page.waitForTimeout(1500);
};

test.describe('[63] P1 实时切页 · step 断点续显/不重初始化', () => {
  test('切走→后端续产→切回: POST=1/taskId不变/轮次续增不重不漏/无无限渲染', async ({
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

    // 本轮后端日志基线: 只对账本次运行新增日志(防匹配历史轮次)
    const logBase = logBaseOf(BLOG);

    // 2) 发一条"长活期多步"任务。
    //    编辑历史 2026-09-30 小欧 - 直接复用 fre2e_05 已实测 60s+ 活期的 PROMPT_B 形态(真实工具链四步:
    //    建目录写骨架/联网查参数/读回核对/正文报告)。活期足够长是本 case 的前提 —— 切走切回必须落在
    //    任务运行窗口内, 任务提前终态则"续显"无意义(下方窗口守卫会显式报错而非伪装通过)。
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

    // 3) 等到"已收到 ≥3 轮"再切走(M2 断点续显法: 必须有断点可比)
    const roundsAtSwitch = await (async () => {
      const dl = Date.now() + 240_000;
      while (Date.now() < dl) {
        const rs = seenRounds(diag.consoleAll, frameBase0);
        if (rs.length >= 3) return rs;
        if (await chat.stopBtn.isVisible().catch(() => false)) {
          // 发送后停止钮可见=流已建立, 属正常; 继续等轮次
        }
        await page.waitForTimeout(500);
      }
      return seenRounds(diag.consoleAll, frameBase0);
    })();
    if (roundsAtSwitch.length < 3) {
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
        `[E2E] 窗口错过: 切走前仅收到 ${roundsAtSwitch.length} 轮(<3), 无法验"断点续显"——请重跑以覆盖切走分支`
      );
    }

    const taskId = await activeTaskId(page);
    expect(taskId).toBeTruthy();
    // 2026-10-01 小欧 - 切走前记录会话页 URL 原样。
    //   注意: 会话页 URL **通常不带** session_id —— [63]第八章已定案「落到最近会话是常态」
    //   (goto('/') 后靠 sessionStorage + 5min TTL 落到最近会话, URL 保持 `/`)。
    //   故判据不能用 "URL 含 session_id", 只能用"路径回到会话页根"+"taskId 不变"。
    const urlAtSwitch = page.url();
    console.log(`[E2E] 切走前 URL = ${urlAtSwitch}(不带 session_id 是常态)`);

    // 切走前 lastSeq(DB 权威序号, 从后端日志取)
    // 编辑历史 2026-09-30 小欧 - 改用后端日志真实格式 `[SSE] seq=<N> task=<id>` 单向匹配。
    //   原写法双向各写一遍正则(其中 task_id 在前的那支对真实日志恒不命中), 脆且易再次静默失效 ——
    //   FE-2 首跑即踩这个坑(提取空 → every 恒真 → 假通过), 此处一并收敛为唯一真实格式。
    const tailBefore = readLogSince(BLOG, logBase);
    const seqsBefore = [
      ...tailBefore.matchAll(
        new RegExp(`\\[SSE\\] seq=(\\d+) task=${taskId}`, 'g')
      ),
    ]
      .map((m) => Number(m[1]))
      .filter((n) => Number.isFinite(n));
    const seqBefore = seqsBefore.length ? Math.max(...seqsBefore) : -1;
    console.log(
      `[E2E] 切走前: task=${taskId} 轮次=${roundsAtSwitch.length}(max=${Math.max(
        ...roundsAtSwitch
      )}) lastSeq=${seqBefore}(提取到${seqsBefore.length}条)`
    );
    // lastSeq 取不到就无法验"续增", 显式判失败而非静默降级
    expect(seqBefore).toBeGreaterThanOrEqual(0);

    // 4) 真切走到「设置2版」(/settings2) —— 只切走页面, 不点「停止」按钮
    //    2026-10-01 小欧: 原实现切走也点「对话任务」, 与切回同 URL = 从未切走(假通过), 详见 gotoAway 注释
    //    urlAtSwitch 已在上面(取 taskId 处)记录, 此处直接用
    await gotoAway(page, AWAY_MENU_TEXT);
    // 防假通过硬断言: URL 必须真的变了, 否则说明又切回同一页, 后续断言全部空转
    const urlAfterAway = page.url();
    console.log(`[E2E] 切走: ${urlAtSwitch} -> ${urlAfterAway}`);
    expect(urlAfterAway).not.toBe(urlAtSwitch);
    expect(urlAfterAway).toContain(AWAY_URL_PATH);

    // 5) 等后端继续产出 ≥2 轮(制造"切走期间有新步骤"的前提, M2 核心)
    await page.waitForTimeout(8000);
    const roundsAfterAway = seenRounds(diag.consoleAll, frameBase0);
    const grewAway = roundsAfterAway.length > roundsAtSwitch.length;
    console.log(
      `[E2E] 切走后 8s: 轮次 ${roundsAtSwitch.length} -> ${roundsAfterAway.length} (增长=${grewAway})`
    );
    if (!grewAway) {
      console.log(
        `[WARN] 切走期间未见新轮次(任务可能已终态或后端停滞); 仍继续验"不重初始化", 但"续增"判据将只靠 POST/taskId`
      );
    }

    // 6) 切回「对话任务」(带回 session_id)
    await gotoChatTask(page);
    await page.waitForTimeout(3000);
    // 防假通过硬断言: 切回必须真的回到会话页, 且带回原 session_id(不是新会话)
    const urlAfterBack = page.url();
    console.log(`[E2E] 切回: ${urlAfterAway} -> ${urlAfterBack}`);
    expect(urlAfterBack).not.toBe(urlAfterAway);
    // 判"路径回到会话页", 不能判"URL 含 session_id": 会话页 URL 通常不带 session_id
    // ([63]第八章: 落到最近会话是常态), 带 session_id 只是"菜单显式带回"的那条路径
    expect(new URL(urlAfterBack).pathname).toBe('/');

    // 7) 断言 —— F7(网络面代理) + P1(POST=1/taskId/轮次)
    const postCount = countStreamReq(diag.streamReqs, 'POST');
    const backTaskId = await activeTaskId(page);
    const roundsAfterBack = seenRounds(diag.consoleAll, frameBase0);

    console.log(
      `[E2E] 切回后: POST /chat/stream 次数=${postCount}, taskId=${backTaskId}, ` +
        `轮次数=${roundsAfterBack.length}`
    );

    // ① POST 次数 = 1(第六章 M1/F1/F3 核心判据)
    expect(postCount).toBe(1);

    // ② taskId 不变(未重建任务)
    expect(backTaskId).toBe(taskId);

    // ③ 未二次 loadSession(重新初始化的另一半特征)
    //    说明: /sessions/{id}/user_messages 由轮询/对账亦可能触发, 故只数 /messages 精确路径
    expect(countGetMessages(diag.streamReqs)).toBeLessThanOrEqual(1);

    // ④ 轮次续增不重不漏: 切走前见过的轮次必须仍在, 且集合无重复
    expect(roundsAfterBack.length).toBeGreaterThanOrEqual(
      roundsAtSwitch.length
    );
    const lost = roundsAtSwitch.filter((r) => !roundsAfterBack.includes(r));
    expect(lost).toEqual([]); // 切走期间已收到的步骤不得丢失
    const dupRounds = roundsAfterBack.filter(
      (r, i) => roundsAfterBack.indexOf(r) !== i
    );
    expect(dupRounds).toEqual([]); // 同一轮不得重复渲染

    // ⑤ 若切走期间确实有新步骤, 断言切回后可见(续显)
    if (grewAway) {
      expect(roundsAfterBack.length).toBeGreaterThan(roundsAtSwitch.length);
    }

    // ⑥ P7: 无无限渲染告警(快照引用不稳定 → React 死循环)
    const renderWarns = infiniteRenderWarnings(diag.consoleAll);
    expect(renderWarns).toEqual([]);

    // ⑦ 任务跑至终态, 正文完整(证明切走切回没有掐断任务)
    await chat.waitDone(420_000);
    const finalText = await chat.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);
    expect(finalText).toContain('近地小行星采矿工程');

    // ⑧ 无 ERROR 级后端日志(第六章 6.4 执行检查①: 最高优先级, 有则立即停)
    const tail = readLogSince(BLOG, logBase);
    const errLines = tail
      .split('\n')
      .filter((l) => / - ERROR - /.test(l) && l.includes(taskId));
    if (errLines.length > 0) {
      console.log(`[E2E] 本轮该 task 的 ERROR 日志:\n${errLines.join('\n')}`);
    }
    expect(
      errLines.filter((l) => !/quota_exceeded|配额已用尽/.test(l))
    ).toEqual([]);

    // 通用区: 无条件落全量诊断
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      tail,
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });
});
