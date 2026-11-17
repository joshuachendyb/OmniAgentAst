// [46] P2a 本地 E2E 验证（已入库）：真实后端 + 真实数据，验证任务列表先于消息历史渲染
import { expect, test } from '@playwright/test';

const SID = '5926e2ce-9d26-448d-bc7f-85b98b671ce9';
const MSG_DELAY_MS = 4000;

test('[46] P2a: 任务列表先于消息历史渲染，URL 会话 ID 不被覆盖', async ({
  page,
}) => {
  let messagesResponded = false;
  let taskPayload: { tasks?: Array<Record<string, unknown>> } | null = null;
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${SID}/messages`)) {
      messagesResponded = true;
    }
    if (resp.url().includes(`/sessions/${SID}/tasks`)) {
      void resp
        .json()
        .then((j) => {
          taskPayload = j;
        })
        .catch(() => undefined);
    }
  });

  // 只延时 messages 请求，数据仍来自真实后端（无 Mock）；观察 tasks 是否先出
  await page.route(`**/api/v1/sessions/${SID}/messages**`, async (route) => {
    await new Promise((r) => setTimeout(r, MSG_DELAY_MS));
    await route.continue();
  });

  await page.goto(`/?session_id=${SID}`);

  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  expect(messagesResponded, '任务项出现时 messages 尚未返回').toBe(false);
  expect(await page.locator('.task-list-item').count()).toBeGreaterThan(10);

  // 46b 数据契约未被 P2a 破坏：tasks 项仍带 ref_ledger / tool_paths
  await expect.poll(() => taskPayload !== null, { timeout: 20000 }).toBe(true);
  const payload = taskPayload as unknown as {
    tasks: Array<Record<string, unknown>>;
  };
  const first = payload.tasks[0];
  expect(first).toHaveProperty('ref_ledger');
  expect(first).toHaveProperty('tool_paths');

  // messages 最终返回，会话 ID 仍是 URL 指定的那个（未被最近会话覆盖）
  await expect.poll(() => messagesResponded, { timeout: 60000 }).toBe(true);
  expect(page.url()).toContain(SID);
});
