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
 * 19 — 会话级 link 开关 + 任务链分组（前端版，对标后端 E2E-P9-08 前三轮）
 * 小欧 2026-10-03（后端 test_p9_08_link_grouping.py 的 UI 投影：开关走真实勾选、
 * 值随消息携带；分组走 TaskListPanel 链号徽标；链根走 tasks 接口 context_root_task_id）
 *
 * 任务 × 开关 × 预期（门5 需直写 DB 造 failed，无前端路径，本文件止于任务3）：
 *   任务 | 开关         | 预期徽标                    | 预期链根
 *   -----+--------------+-----------------------------+------------------
 *    1   | 默认关       | 无徽标（独立成组不编号）    | 自身
 *    2   | 勾选开       | 与任务1同为「链1」          | = 任务1（门2）
 *    3   | 取消勾选关   | 无徽标（自成新组）          | 自身，且任务1/2仍为「链1」
 * 另断言：任务2答出魔数（历史注入生效）；每次发消息后读回后端真源
 * GET /sessions/{id}/messages → link_enabled 与开关一致。
 */
const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
const MAGIC = 'FELINK19';
const SUFFIX = String(Date.now()).slice(-6);
const PROBE = `E:/test_dir/e2e_probe_19_${SUFFIX}.txt`;
const SRC = 'E:/test_dir/test.txt';
const GAP_MS = 5000;

const INPUT_R1 =
  `请完成以下多步任务, 每步都要用真实工具执行, 不要凭记忆作答:` +
  `第1步 读取 ${SRC} 的全文, 统计它的字符数(含空格);` +
  `第2步 新建文件 ${PROBE}, 第一行原样写入固定字符串 ${MAGIC};` +
  `第3步 重新读取 ${PROBE}, 确认第一行内容无误。` +
  `最后请说明你实际调用了哪些工具。`;
const INPUT_R2 =
  `接着刚才的工作继续: 请读取你刚才创建的那个探测文件, ` +
  `把它第一行的内容原样告诉我, 只回答内容本身。`;
const INPUT_R3 = `换个话题: 请用工具读取 ${SRC} 的第一行, 只回答这一行的前20个字符。`;

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

test.describe('[4] 19 会话级 link 开关 + 任务链分组', () => {
  test('关→任务1独立无徽标；开→任务2并入链1且答出魔数；关→任务3独立', async ({
    page,
  }) => {
    test.setTimeout(900_000);
    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await chat.newSession();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);
    const box = page.getByRole('checkbox', { name: '续聊任务' });

    // 默认关
    expect(await box.isChecked()).toBe(false);

    // ══ 任务1（关）：自成一组，无徽标 ══
    await chat.sendPrompt(INPUT_R1);
    await chat.waitDone(300_000);
    const taskId1 = await activeTaskId(page);
    if (!taskId1) throw new Error('[E2E] 读不到任务1 task_id');
    const sessionId = await sessionIdOfTask(taskId1);
    if (!sessionId) throw new Error('[E2E] 反查不到会话');
    expect(await pollTaskStatus(sessionId, taskId1, 300_000)).toBe('completed');
    expect(await badgeOf(page, taskId1)).toBe(null);
    expect(await chainRootOf(sessionId, taskId1)).toBe(taskId1);
    await page.waitForTimeout(GAP_MS);

    // ══ 任务2（开）：并入任务1组 + 答出魔数 ══
    await box.check();
    expect(await box.isChecked()).toBe(true);
    await chat.sendPrompt(INPUT_R2);
    await chat.waitDone(300_000);
    const taskId2 = await activeTaskId(page);
    if (!taskId2 || taskId2 === taskId1)
      throw new Error('[E2E] 任务2 未产生新 task');
    expect(await pollTaskStatus(sessionId, taskId2, 300_000)).toBe('completed');
    expect(await chat.getFinalText()).toContain(MAGIC);
    expect(await badgeOf(page, taskId1)).toBe('链1');
    expect(await badgeOf(page, taskId2)).toBe('链1');
    expect(await chainRootOf(sessionId, taskId2)).toBe(taskId1);
    expect(await readLinkFromBackend(sessionId)).toBe(true);
    await page.waitForTimeout(GAP_MS);

    // ══ 任务3（关）：自成新组，任务1/2 不受影响 ══
    await box.uncheck();
    expect(await box.isChecked()).toBe(false);
    await chat.sendPrompt(INPUT_R3);
    await chat.waitDone(300_000);
    const taskId3 = await activeTaskId(page);
    if (!taskId3 || taskId3 === taskId2)
      throw new Error('[E2E] 任务3 未产生新 task');
    expect(await pollTaskStatus(sessionId, taskId3, 300_000)).toBe('completed');
    expect(await badgeOf(page, taskId3)).toBe(null);
    expect(await chainRootOf(sessionId, taskId3)).toBe(taskId3);
    expect(await badgeOf(page, taskId1)).toBe('链1');
    expect(await readLinkFromBackend(sessionId)).toBe(false);

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
