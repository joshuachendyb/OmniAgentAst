// [历史页清理] 本地 E2E 验证：预览两段式只读，切天数重算，绝不执行删除
import { expect, test } from '@playwright/test';

test('[历史页清理] 清理弹窗预览只读 + 天数切换重算', async ({
  page,
  request,
}) => {
  // 真实后端预览基线（只读）
  const preview30Resp = await request.post('/api/v1/sessions/cleanup/preview', {
    data: { mode: 'older', days: 30 },
  });
  expect(preview30Resp.ok()).toBeTruthy();
  const preview30 = await preview30Resp.json();
  const preview10Resp = await request.post('/api/v1/sessions/cleanup/preview', {
    data: { mode: 'older', days: 10 },
  });
  const preview10 = await preview10Resp.json();
  expect(preview10.count).toBeGreaterThanOrEqual(preview30.count);

  let executed = 0;
  page.on('request', (req) => {
    if (req.url().endsWith('/api/v1/sessions/cleanup')) executed += 1;
  });

  await page.goto('/history');
  await page.getByRole('button', { name: '清理旧会话' }).click();
  await expect(
    page.getByTestId('cleanup-preview-count')
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('cleanup-preview-count')).toContainText(
    `预计清理 ${preview30.count} 个会话`
  );

  // 默认 30 天；切到 10 天后命中数应随真实后端重算
  await page.getByTestId('cleanup-days').click();
  await page.locator('.ant-select-item-option-content', { hasText: '10 天前' }).click();
  await expect(page.getByTestId('cleanup-preview-count')).toContainText(
    `预计清理 ${preview10.count} 个会话`
  );

  // 破坏性端点全程未被调用；确认按钮因未勾选而禁用
  expect(executed).toBe(0);
  const okButton = page.locator('.ant-modal-footer button.ant-btn-primary');
  await expect(okButton).toBeDisabled();

  // 关闭弹窗后再验"空壳会话"入口也能预览
  // antd 两字按钮渲染为"取 消"(中间自动加空格), 用 footer 首位按钮定位
  await page.locator('.ant-modal-footer button').first().click();
  await page.getByRole('button', { name: '清理空壳会话' }).click();
  await expect(
    page.getByTestId('cleanup-preview-count')
  ).toBeVisible({ timeout: 15000 });
  expect(executed).toBe(0);
});
