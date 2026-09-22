import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test('debug input', async ({ page }) => {
  await page.goto(`${BASE}/settings`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(5000);

  // 打印页面 HTML 片段
  const html = await page.evaluate(() => document.querySelector('.ant-card')?.innerHTML?.substring(0, 2000) ?? document.body.innerHTML.substring(0, 2000));
  console.log('HTML:', html);

  // 列出所有 data-settings-key
  const info = await page.evaluate(() => {
    const allKeys = Array.from(document.querySelectorAll('[data-settings-key]')).map(e => e.getAttribute('data-settings-key'));
    return allKeys;
  });
  console.log('All keys:', JSON.stringify(info));

  // 如果有 workspace.project_root，查看 input 详情
  if (info.includes('workspace.project_root')) {
    const inputInfo = await page.evaluate(() => {
      const row = document.querySelector('[data-settings-key="workspace.project_root"]')!;
      const inputs = row.querySelectorAll('input');
      return Array.from(inputs).map((el, i) => ({
        idx: i,
        type: el.type,
        className: el.className,
        disabled: el.disabled,
        readOnly: (el as HTMLInputElement).readOnly,
        value: el.value,
        visible: el.offsetParent !== null,
      }));
    });
    console.log('Inputs:', JSON.stringify(inputInfo));
  }
});
