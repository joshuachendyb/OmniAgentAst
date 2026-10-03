import { test, expect } from '@playwright/test';
import {
  ChatPage,
  activeTaskId,
  attachStreamDiag,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  pollTaskStatus,
  printDiag,
  readLogSince,
  sessionIdOfTask,
  startNormalUiEnv,
  API_BASE,
} from '../e2e_front_lib';

/**
 * 19 — 会话级 link 开关 + 任务链分组（前端版，对标后端 E2E-P9-08）
 * 小欧 2026-10-03（后端 test_p9_08_link_grouping.py 的 UI 投影：开关走真实勾选、
 * 值随消息携带；分组走 TaskListPanel 链号徽标；链根走 tasks 接口 context_root_task_id）
 * -- 更新: 2026-10-03 北京老陈要求 10 个任务不同 link 组合 → R1/R2 取自 P9-08 原文。
 * -- 更新: 2026-10-03 北京老陈要求任务必须模拟真实任务模式 → T3~T10 均为
 *    "读→写→回读核对→简答"三步以上真实工具链（照 R1 形状缩小），不用一句话单步任务。
 *
 * 任务 × 开关 × 预期组（开=并入上一任务所在组，关=自成新组；组由链根定）：
 *   任务 | 开关 | 输入                  | 预期组     | 链根 | 徽标
 *   -----+------+-----------------------+------------+------+------------------
 *    1   | 关   | R1(读统计写验)        | A={T1..T3} | 自身 | 与T2/T3同文案
 *    2   | 开   | R2(读探测行)          | A          | =T1  | 与T1/T3同文案
 *    3   | 开   | 读探第二行+统计+写验  | A          | =T1  | 与T1/T2同文案
 *    4   | 关   | 读源行1+日期+写验     | C={T4..T7} | 自身 | 与T5/T6/T7同文案
 *    5   | 开   | 读源行2+天气+写验     | C          | =T4  | 与T4/T6/T7同文案
 *    6   | 开   | 读源行3+目录+写验     | C          | =T4  | 与T4/T5/T7同文案
 *    7   | 开   | 核t5t6+汇总写验       | C          | =T4  | 与T4/T5/T6同文案
 *    8   | 关   | 读源行2+新闻+写验     | E={T8,T9}  | 自身 | 与T9同文案
 *    9   | 开   | 读t8+追加日期写验    | E          | =T8  | 与T8同文案
 *    10  | 关   | 读源行1+统计+写验     | G={T10}    | 自身 | 无（独立不成链）
 * 另断言：任务2答出魔数（历史注入生效）；每次发消息后读回后端真源
 * GET /sessions/{id}/messages → link_enabled 与开关一致。
 */
const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const MAGIC = 'MAGIC-8808';
const SUFFIX = String(Date.now()).slice(-6);
const PROBE = `E:/test_dir/p9_08_probe_19_${SUFFIX}.txt`;
const SRC = 'E:/test_dir/test.txt';
const GAP_MS = 5000;

// R1/R2 逐字取自后端 backend/e2etests/test_p9_08_link_grouping.py
// (INPUT_R1/R2)，魔数/源文件与后端同源；文件名后缀随机(防任务2靠扫目录猜中)。
const INPUT_R1 =
  `请完成以下多步任务, 每步都要用真实工具执行, 不要凭记忆作答:` +
  `第1步 读取 ${SRC} 的全文, 统计它的字符数(含空格)与行数;` +
  `第2步 新建文件 ${PROBE}, 第一行原样写入固定字符串 ${MAGIC}, 30遍,每一行5个` +
  `文档尾巴写入第1步统计到的字符数与行数;` +
  `第3步 重新读取 ${PROBE}, 确认两行内容与写入一致。` +
  `最后请说明你实际调用了哪些工具。`;
const INPUT_R2 =
  `接着刚才的工作继续: 请读取你刚才创建的那个探测文件, ` +
  `把它第一行的内容原样告诉我` +
  `只回答前3行行内容本身, ` +
  `列表查询这个文档在那个目录多大时间等文档信息`;
// T3~T10 输入定义(每个都是读→加工→写→回读核对→简答的真实多步链)。
// T3/T7/T9 用历史(开), 其余换话题独立成题(内容不影响分组, 只影响历史是否可用)。
const INPUT_R3 =
  `继续前面探测文件的工作: ` +
  `第1步读取 ${PROBE} 的第二行; ` +
  `第2步统计 ${PROBE} 的总行数与字符数(含空格); ` +
  `第3步新建文件 ${PROBE}.v.txt, 第一行写入第二行内容, 尾巴写入统计的行数与字符数; ` +
  `第4步读回 ${PROBE}.v.txt 核对一致后, 告诉我第二行是什么。` +
  `要求: 每步都必须真实调用工具, 回答简短。`;
const INPUT_R4 =
  `换个话题, 请完成以下多步任务, 每步都要用真实工具执行: ` +
  `第1步用工具读取${SRC}的第1行; ` +
  `第2步查询今天是几号、星期几; ` +
  `第3步新建文件 E:/test_dir/e2e_19_t4_${SUFFIX}.txt, 写入该行前20个字符与日期星期; ` +
  `第4步读回核对后, 只回答该行前20个字符与日期。`;
const INPUT_R5 =
  `请完成以下多步任务, 每步都要用真实工具执行: ` +
  `第1步用工具读取${SRC}的第2行; ` +
  `第2步查询本地天气如何; ` +
  `第3步新建文件 E:/test_dir/e2e_19_t5_${SUFFIX}.txt, 写入该行前20个字符与天气; ` +
  `第4步读回核对后, 只回答该行前20个字符与天气。`;
const INPUT_R6 =
  `请完成以下多步任务, 每步都要用真实工具执行: ` +
  `第1步用工具读取${SRC}的第3行; ` +
  `第2步列出 E:/test_dir 目录里有哪些文件(含大小时间); ` +
  `第3步新建文件 E:/test_dir/e2e_19_t6_${SUFFIX}.txt, 写入该行前20个字符与目录条数; ` +
  `第4步读回核对后, 只回答该行前20个字符与目录条数。`;
const INPUT_R7 =
  `接着前面的核对工作继续: ` +
  `第1步读回 E:/test_dir/e2e_19_t5_${SUFFIX}.txt 与 E:/test_dir/e2e_19_t6_${SUFFIX}.txt; ` +
  `第2步新建文件 E:/test_dir/e2e_19_t7_${SUFFIX}.txt, 把两文件第一行拼成一行写入; ` +
  `第3步读回核对后, 告诉我拼成的这一行是什么。` +
  `要求: 每步都必须真实调用工具, 回答简短。`;
const INPUT_R8 =
  `换个话题, 请完成以下多步任务, 每步都要用真实工具执行: ` +
  `第1步用工具读取${SRC}的第2行; ` +
  `第2步查询今天有什么新闻热点; ` +
  `第3步新建文件 E:/test_dir/e2e_19_t8_${SUFFIX}.txt, 写入该行前20个字符与一条新闻标题; ` +
  `第4步读回核对后, 只回答该行前20个字符与新闻标题。`;
const INPUT_R9 =
  `继续刚才 t8 文件的工作: ` +
  `第1步读回 E:/test_dir/e2e_19_t8_${SUFFIX}.txt; ` +
  `第2步在该文件末尾追加一行今天的日期; ` +
  `第3步读回全文核对后, 告诉我文件现在共有几行。` +
  `要求: 每步都必须真实调用工具, 回答简短。`;
const INPUT_R10 =
  `换个话题, 请完成以下多步任务, 每步都要用真实工具执行: ` +
  `第1步用工具读取${SRC}的第1行, 统计它的字符数(含空格); ` +
  `第2步新建文件 E:/test_dir/e2e_19_t10_${SUFFIX}.txt, 写入该行前20个字符与字符数; ` +
  `第3步读回核对后, 只回答前20个字符与字符数。`;

async function readLinkFromBackend(sessionId: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error(`[E2E] 读真源失败 HTTP=${res.status}`);
  const d = (await res.json()) as { link_enabled?: unknown };
  return d.link_enabled;
}

async function chainRootOf(sessionId: string, taskId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) throw new Error(`[E2E] 读任务列表失败 HTTP=${res.status}`);
  const d = (await res.json()) as {
    tasks?: { task_id: string; context_root_task_id?: string }[];
  };
  const hit = (d.tasks ?? []).find((t) => t.task_id === taskId);
  if (!hit) throw new Error(`[E2E] 任务 ${taskId} 不在会话列表`);
  if (!hit.context_root_task_id)
    throw new Error(
      `[E2E] 任务 ${taskId} 无 context_root_task_id —— 后端未下发分组键`
    );
  return hit.context_root_task_id;
}

async function badgeOf(
  page: import('@playwright/test').Page,
  taskId: string
): Promise<string | null> {
  const item = page.locator(`.task-list-item[aria-label*="${taskId}"]`).first();
  await expect(item).toHaveCount(1);
  const badge = item.getByText(/^链\d+$/);
  if ((await badge.count()) === 0) return null;
  return badge.first().innerText();
}

// 等本轮新 task 出现（DB 权威：读 tasks 接口取未知 id）。
// 不用 activeTaskId（读 UI 列表 .active 选中态）：任务完成后列表刷新有窗口期，
// 此时读到旧 id/空串会被误判"没产生新任务"（实测 T8 翻车，后端 task 行正常建成）。
async function waitNewTaskId(
  sessionId: string,
  known: string[],
  timeoutMs = 30_000
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
    if (res.ok) {
      const d = (await res.json()) as { tasks?: { task_id: string }[] };
      const fresh = (d.tasks ?? [])
        .map((t) => t.task_id)
        .find((id) => !known.includes(id));
      if (fresh) return fresh;
    }
    if (Date.now() > deadline)
      throw new Error('[E2E] 30s 内后端未出现新 task —— 发送没建任务');
    await new Promise((r) => setTimeout(r, 1000));
  }
}

test.describe('[4] 19 会话级 link 开关 + 任务链分组(10 任务组合)', () => {
  test('关/开开/关/开开开/关开/关：4 组划分正确', async ({ page }) => {
    test.setTimeout(1_800_000);
    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await chat.newSession();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);
    const box = page.getByRole('checkbox', { name: '续聊任务' });

    expect(await box.isChecked()).toBe(false);

    const plan: { input: string; link: boolean }[] = [
      { input: INPUT_R1, link: false },
      { input: INPUT_R2, link: true },
      { input: INPUT_R3, link: true },
      { input: INPUT_R4, link: false },
      { input: INPUT_R5, link: true },
      { input: INPUT_R6, link: true },
      { input: INPUT_R7, link: true },
      { input: INPUT_R8, link: false },
      { input: INPUT_R9, link: true },
      { input: INPUT_R10, link: false },
    ];

    const taskIds: string[] = [];
    let sessionId = '';
    for (let i = 0; i < plan.length; i += 1) {
      if (plan[i].link) await box.check();
      else await box.uncheck();
      expect(await box.isChecked()).toBe(plan[i].link);
      await chat.sendPrompt(plan[i].input);
      await chat.waitDone(300_000);
      let tid: string;
      if (!sessionId) {
        const first = await activeTaskId(page);
        if (!first) throw new Error('[E2E] 任务1 读不到 task_id');
        sessionId = await sessionIdOfTask(first);
        if (!sessionId) throw new Error('[E2E] 反查不到会话');
        tid = first;
      } else {
        tid = await waitNewTaskId(sessionId, taskIds);
      }
      if (taskIds.includes(tid))
        throw new Error(`[E2E] 任务${i + 1} id 重复: ${tid}`);
      taskIds.push(tid);
      expect(await pollTaskStatus(sessionId, tid, 300_000)).toBe('completed');
      // 任务2 靠注入的历史答出魔数(当场断言, 此时正文即本任务回答)
      if (i === 1) expect(await chat.getFinalText()).toContain(MAGIC);
      expect(await readLinkFromBackend(sessionId)).toBe(plan[i].link);
      if (i < plan.length - 1) await page.waitForTimeout(GAP_MS);
    }
    const [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10] = taskIds;

    // 链根断言（权威）：开并入上一任务所在组，关自成新组
    expect(await chainRootOf(sessionId, t1)).toBe(t1);
    for (const t of [t2, t3]) expect(await chainRootOf(sessionId, t)).toBe(t1);
    expect(await chainRootOf(sessionId, t4)).toBe(t4);
    for (const t of [t5, t6, t7])
      expect(await chainRootOf(sessionId, t)).toBe(t4);
    expect(await chainRootOf(sessionId, t8)).toBe(t8);
    expect(await chainRootOf(sessionId, t9)).toBe(t8);
    expect(await chainRootOf(sessionId, t10)).toBe(t10);

    // 徽标断言（相对关系，不锁绝对编号）：同组同文案，单点无徽标
    const bA = await badgeOf(page, t1);
    expect(bA).not.toBe(null);
    expect(await badgeOf(page, t2)).toBe(bA);
    expect(await badgeOf(page, t3)).toBe(bA);
    const bC = await badgeOf(page, t4);
    expect(bC).not.toBe(null);
    expect(bC).not.toBe(bA);
    for (const t of [t5, t6, t7]) expect(await badgeOf(page, t)).toBe(bC);
    const bE = await badgeOf(page, t8);
    expect(bE).not.toBe(null);
    expect(bE).not.toBe(bA);
    expect(bE).not.toBe(bC);
    expect(await badgeOf(page, t9)).toBe(bE);
    expect(await badgeOf(page, t10)).toBe(null);

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
