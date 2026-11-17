// [46] P0 本地 E2E 验证（已入库）：真实后端 + 真实库，验证首屏请求分页参数与 SQL 窗口契约
// 2026-11-18 小欧 - 会审整改: 会话 ID 与消息条数改为现场发现/现场取真值(原写死某台开发机的
//   SID 与 total=49, 换库即红), 断言全部改成字段间关系(见 session-fixture.ts) — 小欧-2026-11-18
import { expect, test } from '@playwright/test';

import {
  fetchMessages,
  listMessageSessions,
  type MessagesBody,
} from './session-fixture';

// 首屏分页窗口(与 chatHistory.FIRST_SCREEN_MESSAGE_LIMIT 同值)
const FIRST_SCREEN_LIMIT = 50;

test('[46] P0: 首屏 messages 请求带 limit=50，后端 SQL 窗口分页正确', async ({
  page,
  request,
}) => {
  const candidates = await listMessageSessions(request);
  test.skip(
    candidates.length === 0,
    '当前库没有任何带消息的会话, 无法验证分页'
  );
  const sid = candidates[0].sessionId;

  let messagesUrl = '';
  let messagesBody: MessagesBody | null = null;
  page.on('request', (req) => {
    if (req.url().includes(`/sessions/${sid}/messages`))
      messagesUrl = req.url();
  });
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${sid}/messages`)) {
      void resp
        .json()
        .then((j) => {
          messagesBody = j as MessagesBody;
        })
        .catch(() => undefined);
    }
  });

  await page.goto(`/?session_id=${sid}`);
  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  await expect.poll(() => messagesBody !== null, { timeout: 30000 }).toBe(true);

  // 首屏路径带分页参数
  expect(messagesUrl).toContain(`limit=${FIRST_SCREEN_LIMIT}`);
  expect(messagesUrl).toContain('offset=0');
  const body = messagesBody as unknown as { total: number; has_more: boolean };
  const total = body.total;
  expect(total).toBeGreaterThan(0);
  // 是否还有更早只取决于总量与窗口, 不写死具体条数
  expect(body.has_more).toBe(total > FIRST_SCREEN_LIMIT);

  // 直接打真实后端：limit=10 → 窗口收窄, total 仍是全量, has_more 随之变化
  const paged = await fetchMessages(request, sid, 'limit=10&offset=0');
  expect(paged.total).toBe(total);
  expect(paged.has_more).toBe(total > 10);
  const pagedCount = paged.messages?.length ?? 0;
  expect(pagedCount).toBeGreaterThan(0);
  expect(pagedCount).toBeLessThanOrEqual(20);

  // offset 到达 total → 空页, 无负切片/异常
  const empty = await fetchMessages(request, sid, `limit=10&offset=${total}`);
  expect(empty.messages).toEqual([]);
  expect(empty.total).toBe(total);
  expect(empty.has_more).toBe(false);

  // 不带参数 → 后端全量(兼容旧调用方), 条数不少于分页窗口
  const full = await fetchMessages(request, sid);
  expect(full.total).toBe(total);
  expect(full.has_more).toBe(false);
  expect(full.messages?.length ?? 0).toBeGreaterThanOrEqual(pagedCount);
});
