// [46] P0 本地 E2E 验证（已入库）：真实后端 + 真实库，验证首屏请求分页参数与 SQL 窗口契约
import { expect, test } from '@playwright/test';

const SID = '5926e2ce-9d26-448d-bc7f-85b98b671ce9';

test('[46] P0: 首屏 messages 请求带 limit=50，后端 SQL 窗口分页正确', async ({
  page,
  request,
}) => {
  let messagesUrl = '';
  let messagesBody: { total?: number; has_more?: boolean; messages?: unknown[] } | null =
    null;
  page.on('request', (req) => {
    if (req.url().includes(`/sessions/${SID}/messages`)) messagesUrl = req.url();
  });
  page.on('response', (resp) => {
    if (resp.url().includes(`/sessions/${SID}/messages`)) {
      void resp
        .json()
        .then((j) => {
          messagesBody = j;
        })
        .catch(() => undefined);
    }
  });

  await page.goto(`/?session_id=${SID}`);
  await expect(page.locator('.task-list-item').first()).toBeVisible({
    timeout: 20000,
  });
  await expect.poll(() => messagesBody !== null, { timeout: 30000 }).toBe(true);

  // 首屏路径带分页参数；会话总对数 49 <= 50 时 has_more=false 属正确
  expect(messagesUrl).toContain('limit=50');
  expect(messagesUrl).toContain('offset=0');
  const body = messagesBody as unknown as {
    total: number;
    has_more: boolean;
  };
  expect(body.total).toBe(49);
  expect(body.has_more).toBe(false);

  // 直接打真实后端：limit=10 → 最近 10 对(最多 20 气泡)，total 仍为全量 49
  const pageResp = await request.get(
    `/api/v1/sessions/${SID}/messages?limit=10&offset=0`
  );
  expect(pageResp.ok()).toBeTruthy();
  const paged = await pageResp.json();
  expect(paged.total).toBe(49);
  expect(paged.has_more).toBe(true);
  expect(paged.messages.length).toBeGreaterThan(0);
  expect(paged.messages.length).toBeLessThanOrEqual(20);

  // offset 越界 → 空页，无异常
  const emptyResp = await request.get(
    `/api/v1/sessions/${SID}/messages?limit=10&offset=100`
  );
  expect(emptyResp.ok()).toBeTruthy();
  const empty = await emptyResp.json();
  expect(empty.messages).toEqual([]);
  expect(empty.total).toBe(49);
  expect(empty.has_more).toBe(false);

  // 不带参数 → 全量兼容旧调用方(气泡数大于分页窗口)
  const fullResp = await request.get(`/api/v1/sessions/${SID}/messages`);
  const full = await fullResp.json();
  expect(full.total).toBe(49);
  expect(full.has_more).toBe(false);
  expect(full.messages.length).toBeGreaterThanOrEqual(paged.messages.length);
});
