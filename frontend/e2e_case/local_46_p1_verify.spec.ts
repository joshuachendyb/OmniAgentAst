// [46] P1 本地 E2E 验证（已入库）：真实后端 + 真实库，验证 execution_steps/thought 裁剪与详情链路恢复
// 2026-11-18 小欧 - 会审整改: ①会话改现场发现(原写死开发机 SID); ②按现行口径断言 —— 首屏
//   include_steps=false 时 steps 与 thought 都收口不下发(V16), 显式 true 才恢复, 原"首屏 thought 仍下发"
//   的断言与整改后契约相反 — 小欧-2026-11-18
import { expect, test } from '@playwright/test';

import {
  fetchMessages,
  listMessageSessions,
  type MessagesBody,
} from './session-fixture';

test('[46] P1: 首屏不下发 steps/thought，include_steps=true 恢复 steps 与 thought', async ({
  page,
  request,
}) => {
  // 挑一个"确实有步骤可对照"的会话: 详情模式能取到 execution_steps 与任务级步骤
  const candidates = await listMessageSessions(request);
  test.skip(
    candidates.length === 0,
    '当前库没有任何带消息的会话, 无法验证裁剪'
  );
  let sid = '';
  for (const c of candidates.slice(0, 10)) {
    const probe = await fetchMessages(
      request,
      c.sessionId,
      'limit=20&offset=0&include_steps=true'
    );
    if (
      !(probe.messages ?? []).some((m) => (m.execution_steps?.length ?? 0) > 0)
    )
      continue;
    sid = c.sessionId;
    break;
  }
  test.skip(!sid, '候选会话均无 execution_steps, 无法验证裁剪');

  let firstScreen: MessagesBody | null = null;
  let firstUrl = '';
  page.on('request', (req) => {
    if (req.url().includes(`/sessions/${sid}/messages`)) firstUrl = req.url();
  });
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${sid}/messages`)) {
      void resp
        .json()
        .then((j) => {
          firstScreen = j as MessagesBody;
        })
        .catch(() => undefined);
    }
  });

  await page.goto(`/?session_id=${sid}`);
  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  await expect.poll(() => firstScreen !== null, { timeout: 30000 }).toBe(true);

  // 首屏显式裁剪: 请求带 include_steps=false, 响应里 steps 与 thought 全空(减包目标兑现)
  expect(firstUrl).toContain('include_steps=false');
  const firstBody = firstScreen as unknown as MessagesBody;
  const firstMsgs = firstBody.messages ?? [];
  expect(firstMsgs.length).toBeGreaterThan(0);
  expect(firstMsgs.every((m) => (m.execution_steps?.length ?? 0) === 0)).toBe(
    true
  );
  expect(firstMsgs.every((m) => !m.thought)).toBe(true);

  // 同一真实会话: 显式 include_steps=true → steps 与 thought 一并恢复
  const withSteps = await fetchMessages(
    request,
    sid,
    'limit=20&offset=0&include_steps=true'
  );
  expect(withSteps.total).toBe(firstBody.total);
  expect(
    (withSteps.messages ?? []).some((m) => (m.execution_steps?.length ?? 0) > 0)
  ).toBe(true);
  expect((withSteps.messages ?? []).some((m) => !!m.thought)).toBe(true);

  // 右栏详情独立链路不受裁剪影响: 该会话某任务的任务级步骤仍完整
  const tasksResp = await request.get(`/api/v1/sessions/${sid}/tasks`);
  const tasksBody = (await tasksResp.json()) as {
    tasks?: Array<{ task_id: string }>;
  };
  const taskId = tasksBody.tasks?.[0]?.task_id;
  test.skip(!taskId, '该会话无任务, 无法验证任务级步骤链路');
  const detailResp = await request.get(
    `/api/v1/chat/execution/task/${taskId}/steps`
  );
  expect(detailResp.ok()).toBeTruthy();
  const detail = (await detailResp.json()) as { steps?: unknown[] };
  expect(detail.steps?.length ?? 0).toBeGreaterThan(0);
});
