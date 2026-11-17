// [46] P2a 本地 E2E 验证（已入库）：真实后端 + 真实数据，验证任务列表先于消息历史渲染
// 2026-11-18 小欧 - 会审整改: ①会话现场发现(原写死开发机 SID) + 任务条数按接口真值断言(原 >10 为魔法值);
//   ②route 延迟注释如实化 —— 本用例注入的是"时序"(只延迟 messages 不改其内容), 断言"任务先出"
//   正是依赖这个时序注入, 不是对真实网络抖动的观测 — 小欧-2026-11-18
import { expect, test } from '@playwright/test';

import { countTasks, listMessageSessions } from './session-fixture';

const MSG_DELAY_MS = 4000;

test('[46] P2a: 任务列表先于消息历史渲染，URL 会话 ID 不被覆盖', async ({
  page,
  request,
}) => {
  // 需要一个既有消息又有任务的会话(否则左列本来就空, 断言"任务先出"无意义)
  const candidates = await listMessageSessions(request);
  test.skip(candidates.length === 0, '当前库没有任何带消息的会话');
  let sid = '';
  let taskTotal = 0;
  for (const c of candidates.slice(0, 10)) {
    taskTotal = await countTasks(request, c.sessionId);
    if (taskTotal > 0) {
      sid = c.sessionId;
      break;
    }
  }
  test.skip(!sid, '候选会话都无任务, 无法验证任务列表先渲染');

  let messagesResponded = false;
  let taskPayload: { tasks?: Array<Record<string, unknown>> } | null = null;
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${sid}/messages`)) {
      messagesResponded = true;
    }
    if (resp.url().includes(`/sessions/${sid}/tasks`)) {
      void resp
        .json()
        .then((j) => {
          taskPayload = j;
        })
        .catch(() => undefined);
    }
  });

  // 时序注入(非数据 Mock): 只把 messages 响应推迟 MSG_DELAY_MS, 内容仍来自真实后端,
  // 用来判定"任务项可见时 messages 是否尚未返回"——即任务列表是否先出。
  await page.route(`**/api/v1/sessions/${sid}/messages**`, async (route) => {
    await new Promise((r) => setTimeout(r, MSG_DELAY_MS));
    await route.continue();
  });

  await page.goto(`/?session_id=${sid}`);

  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  expect(messagesResponded, '任务项出现时 messages 尚未返回').toBe(false);
  // 任务条数与接口真值一致(不写死台数)
  expect(await page.locator('.task-list-item').count()).toBe(taskTotal);

  // 46b 数据契约未被 P2a 破坏：tasks 项仍带 ref_ledger / tool_paths
  await expect.poll(() => taskPayload !== null, { timeout: 20000 }).toBe(true);
  const payload = taskPayload as unknown as {
    tasks: Array<Record<string, unknown>>;
  };
  expect(payload.tasks.length).toBe(taskTotal);
  const first = payload.tasks[0];
  expect(first).toHaveProperty('ref_ledger');
  expect(first).toHaveProperty('tool_paths');

  // messages 最终返回，会话 ID 仍是 URL 指定的那个（未被最近会话覆盖）
  await expect.poll(() => messagesResponded, { timeout: 60000 }).toBe(true);
  expect(page.url()).toContain(sid);
});
