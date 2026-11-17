// [46] P3 本地 E2E 诊断（已入库）：量同源 /api 经 Vite 代理的真实延迟
import { expect, test } from '@playwright/test';

test('[46] P3: 同源 /api/v1/health 经 Vite 代理延迟测量', async ({ page }) => {
  await page.goto('/');
  const measure = async () =>
    page.evaluate(async () => {
      const t0 = performance.now();
      const r = await fetch('/api/v1/health', { cache: 'no-store' });
      await r.text();
      return performance.now() - t0;
    });
  const first = await measure();
  const second = await measure();
  console.log(`[P3] vite-proxy health latency: ${first.toFixed(1)}ms / ${second.toFixed(1)}ms`);
  expect(first).toBeGreaterThan(0);
});
