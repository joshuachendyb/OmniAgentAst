// 编辑历史: 2026-10-06 小欧 - 新建: fre2e_20 安全Tab块2（分类表直出 + 两个说明弹框 + mermaid 流程图）
//   把原先 6 个临时诊断脚本合并成一个正式 case: 覆盖页面结构、分类表行列、两个弹框内容、mermaid 真实渲染。
//   诊断期的 console 输出已并入断言, 不再保留一次性脚本。
// 编辑历史: 2026-10-06 小欧 - 增 2 条回归断言: 分类表字号须 14px(设置页正文档),
//   「目录列表」列不得残留内联 code(灰底碎块)。 — 小欧-2026-10-06
import { test, expect } from '@playwright/test';

test('安全Tab块2: 分类表直出 + 弹框1策略说明 + 弹框2读写判定(mermaid)', async ({
  page,
}) => {
  const errs: string[] = [];
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  page.on('pageerror', (e) => errs.push('PAGEERROR: ' + e.message));

  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  await page.getByText('设置', { exact: false }).first().click();
  await page.waitForTimeout(1200);
  await page.getByText('安全', { exact: true }).first().click();
  await page.waitForTimeout(2000);

  // 块1 四项仍在(原样不动)
  await expect(page.getByText('HTL人工开关')).toBeVisible();
  await expect(page.getByText('危险操作确认')).toBeVisible();
  await expect(page.getByText('自动确认延迟(秒)')).toBeVisible();
  await expect(page.getByText('人工确认超时(秒)')).toBeVisible();

  // 块2 标题 + 分类表直出(4 列 × 5 数据行)
  await expect(
    page.getByText('安全策略说明', { exact: false }).first()
  ).toBeVisible();
  const table = page.locator('table').first();
  await expect(table).toBeVisible();
  await expect(page.getByText('禁区·系统', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('cell', { name: '禁区 + 白名单外的所有路径' })
  ).toBeVisible();
  expect(await table.locator('tbody tr').count()).toBe(5);
  // 4 列都不得被压成逐字竖排(回归: auto 布局下超长单元格会独占宽度)
  const widths = await table.evaluate((t) =>
    Array.from(t.querySelectorAll('tbody tr')[0].querySelectorAll('td')).map(
      (c) => Math.round(c.getBoundingClientRect().width)
    )
  );
  expect(Math.min(...widths)).toBeGreaterThan(100);

  // 两个按钮恒在
  const btn1 = page.getByRole('button', { name: '安全策略说明' });
  const btn2 = page.getByRole('button', { name: '读写判定流程' });
  await expect(btn1).toBeEnabled();
  await expect(btn2).toBeEnabled();

  // 弹框1: 五组齐全 + 路径已插值成真实值
  await btn1.click();
  await page.waitForTimeout(900);
  const m1 = page.locator('.ant-modal-content');
  await expect(m1.getByText('shell 命令执行')).toBeVisible();
  for (const g of [
    'delete 命令执行',
    'HTL 人工确认',
    '信任',
    '沙箱与运行限制',
  ]) {
    await expect(m1.getByText(g, { exact: false }).first()).toBeVisible();
  }
  await m1.getByText('沙箱与运行限制').scrollIntoViewIfNeeded();
  await page.screenshot({
    path: 'tests/output/sec-popup1-policy.png',
    fullPage: true,
  });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(700);

  // 弹框2: mermaid 真实渲染 + 不被代码框包住 + 八步表
  await btn2.click();
  await page.waitForTimeout(4000);
  const m2 = page.locator('.ant-modal-content');
  expect(await m2.locator('.mermaid-block').count()).toBe(1);
  expect(await m2.locator('.mermaid-block svg').count()).toBeGreaterThan(0);
  // 回归: 图不得被 PreBlock 的边框/灰底/400px 限高包成代码框
  const boxed = await m2.locator('.mermaid-block').evaluate((el) => {
    const pre = el.closest('pre');
    return pre ? getComputedStyle(pre).maxHeight : 'none';
  });
  expect(boxed).toBe('none');
  await expect(m2.getByText('八步速查')).toBeVisible();
  await page.screenshot({
    path: 'tests/output/sec-popup2-flow.png',
    fullPage: true,
  });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(700);

  // 2026-10-06 三堂会审回归断言:
  //   ①分类表字号须为设置页正文档(PRIMARY=14px), 缺省 SECONDARY(12px) 会比周围正文小 2px
  //   ②「目录列表」列不得残留内联 code —— 内联 code 各带背景+圆角, 会把该列撑成灰底碎块
  const audit = await page.evaluate(() => {
    const t = document.querySelector('table')!;
    const cell = t.querySelector('tbody tr td:nth-child(2)')!;
    return {
      tableFont: getComputedStyle(t).fontSize,
      codeCount: cell.querySelectorAll('code').length,
    };
  });
  expect(audit.tableFont).toBe('14px');
  expect(audit.codeCount).toBe(0);

  // console 只允许 antd 既有的 findDOMNode deprecation(项目噪音, 与本用例无关)
  expect(
    errs.filter((e) => !e.includes('favicon') && !e.includes('findDOMNode'))
  ).toEqual([]);
});
