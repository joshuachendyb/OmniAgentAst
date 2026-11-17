// [46] P1 本地 E2E 验证（已入库）：真实后端 + 真实库，验证 execution_steps 裁剪与思考区保留
import { expect, test } from '@playwright/test';

const SID = '5926e2ce-9d26-448d-bc7f-85b98b671ce9';

test('[46] P1: 首屏不下发 steps 但 thought 保留，include_steps=true 恢复 steps', async ({
  page,
  request,
}) => {
  let firstScreen: { messages?: Array<{ execution_steps?: unknown[]; thought?: string }> } | null =
    null;
  let firstUrl = '';
  page.on('request', (req) => {
    if (req.url().includes(`/sessions/${SID}/messages`)) firstUrl = req.url();
  });
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${SID}/messages`)) {
      void resp
        .json()
        .then((j) => {
          firstScreen = j;
        })
        .catch(() => undefined);
    }
  });

  await page.goto(`/?session_id=${SID}`);
  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  await expect.poll(() => firstScreen !== null, { timeout: 30000 }).toBe(true);

  // 首屏请求未显式要 steps；响应里 execution_steps 全空，思考字段仍随消息下发
  expect(firstUrl).not.toContain('include_steps=true');
  const firstBody = firstScreen as unknown as {
    messages: Array<{ execution_steps?: unknown[]; thought?: string }>;
  };
  expect(
    firstBody.messages.every((m) => (m.execution_steps?.length ?? 0) === 0)
  ).toBe(true);
  expect(firstBody.messages.some((m) => !!m.thought)).toBe(true);

  // 同一真实会话：显式 include_steps=true → steps 恢复
  const withSteps = await request.get(
    `/api/v1/sessions/${SID}/messages?limit=10&offset=0&include_steps=true`
  );
  expect(withSteps.ok()).toBeTruthy();
  const withStepsBody = await withSteps.json();
  expect(withStepsBody.messages.some((m: { execution_steps?: unknown[] }) => (m.execution_steps?.length ?? 0) > 0)).toBe(true);

  // 右栏详情独立链路不受裁剪影响：取一个任务看 steps 端点仍完整
  const tasksResp = await request.get(`/api/v1/sessions/${SID}/tasks`);
  const tasksBody = await tasksResp.json();
  const taskId = tasksBody.tasks[0].task_id;
  const detailResp = await request.get(`/api/v1/chat/execution/task/${taskId}/steps`);
  expect(detailResp.ok()).toBeTruthy();
  const detail = await detailResp.json();
  expect(Array.isArray(detail.steps) ? detail.steps.length : 0).toBeGreaterThan(0);
});
