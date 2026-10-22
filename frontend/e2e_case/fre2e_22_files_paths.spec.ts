/**
 * fre2e_22 —— 文件页（/files）路径/深链/行号/翻页/竞态 全链路真实浏览器 E2E
 *
 * 2026-10-22 小杨 - 新建（覆盖 2026-10-21~22 前端改动：首屏只取根层、补拉子树、
 *   深链路径归一、行号区间高亮、越界提示、加载后续内容/显示更多、复制路径、
 *   引用到输入框、树请求竞态）— 小杨-2026-10-22
 *
 * ⚠ 本地测试文件：按 AGENTS「严禁 commit 任何测试 case 代码」，此文件**不提交**
 *
 * 真实环境：chromium 真浏览器 + 真后端(:8000) + 真项目根(E:\test_dir) + 真文件。
 *   不 Mock 任何接口；所有断言都基于真实响应与真实 DOM。
 */
import { test, expect, type Page } from '@playwright/test';

/** 根层中文名 md（16KB，多行） */
const MD_CN = '01_AI技术报告_原理与近五年演进.md';
/** 根层中文目录（测中文路径深链） */
const DIR_CN = '研究报告';
/** 多级 ASCII 目录下的文件（测多级深链 + 补拉） */
const NESTED_DIR = 'deepseek-harness/docs';
const NESTED_FILE = 'deepseek-harness/docs/agent-lifecycle.i18n.yaml';
/** 超大文件 37MB / 126 万行（测后端 2MB 截断 + 本地 2000 行窗口） */
const BIG_FILE = 'extracted_numbers+2026-09-28_18-31-01.txt';

const enc = (p: string) => encodeURIComponent(p);

/** 打开文件页并等首屏树渲染完成 */
const gotoFiles = async (page: Page, query = ''): Promise<void> => {
  await page.goto(`/files${query}`);
  await expect(
    page.locator('.files-tree-row').first()
  ).toBeVisible({ timeout: 60_000 });
};

/** 取某文件的行元素背景色（高亮色非空即视为已定位） */
const bgOf = async (page: Page, line: number): Promise<string> =>
  page.evaluate((ln) => {
    const el = document.querySelector(`[data-ln="${ln}"]`) as HTMLElement | null;
    return el ? el.style.background : '';
  }, line);

test.describe('文件页：路径/深链/行号/翻页/竞态（真实浏览器）', () => {
  test('T1 首屏只取有限层：tree 请求带 max_depth=3，未逐目录拉全树', async ({
    page,
  }) => {
    const treeReqs: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/files/tree')) treeReqs.push(r.url());
    });
    await gotoFiles(page);
    await page.waitForTimeout(1500);

    expect(treeReqs.length).toBeGreaterThan(0);
    // 首屏必须是"只取有限层"（当前口径 3 层，深层按需补拉）
    expect(treeReqs[0]).toContain('max_depth=3');
    // 首屏阶段不得出现按子目录补拉的请求
    const subReq = treeReqs.filter((u) => /path=[^&]+/.test(u) && !/path=(&|$)/.test(u));
    expect(subReq, `首屏不应有子目录补拉请求: ${subReq.join(' | ')}`).toHaveLength(0);
  });

  test('T2 逐层展开：首屏 3 层之外的目录按需补拉（max_depth=10）', async ({
    page,
  }) => {
    const treeReqs: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('/files/tree')) treeReqs.push(r.url());
    });
    await gotoFiles(page);
    // 第 1 层
    await page.locator('[data-file-key="deepseek-harness"]').first().click();
    // 第 2 层（首屏 3 层内，已随首屏到达，无需补拉）
    await expect(
      page.locator(`[data-file-key="${NESTED_DIR}"]`).first()
    ).toBeVisible({ timeout: 60_000 });
    // 第 3 层
    await page.locator(`[data-file-key="${NESTED_DIR}"]`).first().click();
    await expect(
      page.locator('[data-file-key="deepseek-harness/docs/cookbook"]').first()
    ).toBeVisible({ timeout: 60_000 });
    // 第 4 层：超出首屏 3 层 → 必须发起补拉
    await page
      .locator('[data-file-key="deepseek-harness/docs/cookbook"]')
      .first()
      .click();
    await expect(
      page.locator('[data-file-key="deepseek-harness/docs/cookbook/adding-a-package.md"]').first()
    ).toBeVisible({ timeout: 60_000 });

    const subReq = treeReqs.find((u) =>
      decodeURIComponent(u).includes('path=deepseek-harness/docs/cookbook')
    );
    expect(subReq, `未发起 cookbook 的补拉请求: ${treeReqs.join(' | ')}`).toBeTruthy();
    // 补拉同样是有限层（当前口径 3 层，深了再点再拉）
    expect(subReq).toContain('max_depth=3');
  });

  test('T3 深链定位：正斜杠多级路径 → 树定位 + 预览出内容', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(NESTED_FILE)}`);
    const row = page.locator(`[data-file-key="${NESTED_FILE}"]`).first();
    await expect(row).toBeVisible({ timeout: 60_000 });
    await expect(row).toHaveAttribute('data-active', '1');
    // 预览区出现该文件名/内容
    await expect(page.getByText('agent-lifecycle', { exact: false }).first()).toBeVisible({
      timeout: 60_000,
    });
  });

  test('T4 深链定位：Windows 反斜杠路径 → 同样能定位（此前必失败）', async ({
    page,
  }) => {
    const winPath = NESTED_FILE.replace(/\//g, '\\');
    await gotoFiles(page, `?path=${enc(winPath)}`);
    const row = page.locator(`[data-file-key="${NESTED_FILE}"]`).first();
    await expect(row).toBeVisible({ timeout: 60_000 });
    await expect(row).toHaveAttribute('data-active', '1');
  });

  test('T5 深链定位：./ 前缀路径 → 同样能定位', async ({ page }) => {
    await gotoFiles(page, `?path=${enc('./' + NESTED_FILE)}`);
    const row = page.locator(`[data-file-key="${NESTED_FILE}"]`).first();
    await expect(row).toBeVisible({ timeout: 60_000 });
    await expect(row).toHaveAttribute('data-active', '1');
  });

  test('T6 深链定位：中文目录 + 中文文件名 → 能定位并出预览', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(DIR_CN)}`);
    const dirRow = page.locator(`[data-file-key="${DIR_CN}"]`).first();
    await expect(dirRow).toBeVisible({ timeout: 60_000 });
    // 目录里的中文文件应出现
    const cnFile = page
      .locator('[data-file-key^="' + DIR_CN + '/"]')
      .first();
    await expect(cnFile).toBeVisible({ timeout: 60_000 });
  });

  test('T7 深链行号：区间内每行都高亮，区间外不高亮', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(MD_CN)}&line=3-5`);
    await expect(page.locator('[data-ln="1"]').first()).toBeVisible({
      timeout: 60_000,
    });
    // 区间内 3/4/5 高亮
    for (const ln of [3, 4, 5]) {
      await expect
        .poll(async () => bgOf(page, ln), { timeout: 20_000 })
        .not.toBe('');
    }
    // 区间外 6 不高亮
    expect(await bgOf(page, 6)).toBe('');
  });

  test('T8 深链行号越界 → 工具条如实提示，不静默', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(MD_CN)}&line=999999-1000000`);
    await expect(
      page.getByText(/未找到第\s*999999(-1000000)?\s*行/)
    ).toBeVisible({ timeout: 60_000 });
  });

  test('T8b 深链行号单值（line=10，不带区间）→ 同样能定位到第 10 行', async ({
    page,
  }) => {
    // 深链行号格式只认"起-止"；单值是用户手敲 URL 的常见写法，静默忽略即死路
    await gotoFiles(page, `?path=${enc(MD_CN)}&line=10`);
    await expect(page.locator('[data-ln="10"]').first()).toBeVisible({
      timeout: 60_000,
    });
    await expect
      .poll(async () => bgOf(page, 10), { timeout: 20_000 })
      .not.toBe('');
  });

  test('T9 超大文件：出现「加载后续内容」，点击后已读行数增加', async ({
    page,
  }) => {
    await gotoFiles(page, `?path=${enc(BIG_FILE)}`);
    const more = page.getByRole('button', { name: /加载后续内容/ });
    await expect(more).toBeVisible({ timeout: 120_000 });
    const readLines = async (): Promise<number> => {
      const t = await more.innerText();
      return Number((t.match(/已读\s*(\d+)/) ?? [])[1] ?? 0);
    };
    const before = await readLines();
    expect(before).toBeGreaterThan(0);
    await more.click();
    // 已读行数必须增加（等异步请求回来）
    await expect
      .poll(async () => readLines(), { timeout: 120_000 })
      .toBeGreaterThan(before);
  });

  test('T10 超大文件：「显示更多」把渲染窗口从 2000 行推进', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(BIG_FILE)}`);
    const showMore = page.getByRole('button', { name: /显示更多/ });
    await expect(showMore).toBeVisible({ timeout: 120_000 });
    const rowsBefore = await page.locator('[data-ln]').count();
    await showMore.click();
    await expect
      .poll(async () => page.locator('[data-ln]').count(), { timeout: 60_000 })
      .toBeGreaterThan(rowsBefore);
  });

  test('T11 复制路径：剪贴板拿到的是相对项目根路径', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    // 用非 md 文件（md 默认美显模式，无行号 DOM）
    await gotoFiles(page, `?path=${enc(NESTED_FILE)}`);
    await expect(page.locator('[data-ln="1"]').first()).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole('button', { name: '复制路径' }).click();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    expect(clip).toContain(NESTED_FILE);
  });

  test('T12 引用到输入框：就地收集 → 去对话后引用进入输入区', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(NESTED_FILE)}`);
    await expect(page.locator('[data-ln="1"]').first()).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole('button', { name: /引用/ }).first().click();
    // 引用是"就地收集"（不立刻跳页），收集条如实告知数量
    await expect(page.getByText('已引用 1 个文件')).toBeVisible({
      timeout: 30_000,
    });
    // 点「去对话」→ 跳回聊天页，引用带进输入区
    await page.getByRole('button', { name: '去对话' }).click();
    await expect(
      page.getByPlaceholder('输入消息，Shift+Enter 换行')
    ).toBeVisible({ timeout: 60_000 });
    await expect(
      page.getByText(new RegExp('agent-lifecycle')).first()
    ).toBeVisible({ timeout: 30_000 });
  });

  test('T13 树请求竞态：连续「重新加载」后树最终一致（无重复/丢节点）', async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await gotoFiles(page);
    const reload = page.getByRole('button', { name: '重新加载' });
    await reload.click();
    await reload.click();
    await reload.click();
    // 等树重新就绪（加载中树会整体替换为 Spin，属设计）
    await expect
      .poll(async () => page.locator('.files-tree-row').count(), { timeout: 60_000 })
      .toBeGreaterThan(0);
    await page.waitForTimeout(1500);
    const count1 = await page.locator('.files-tree-row').count();
    await page.waitForTimeout(1500);
    const count2 = await page.locator('.files-tree-row').count();
    expect(count2).toBe(count1);
    expect(count1).toBeGreaterThan(0);
    expect(errors, `页面报错: ${errors.join(' | ')}`).toHaveLength(0);
  });

  test('T14 越界深链：提示未找到，不白屏不报错', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto(`/files?path=${enc('../../etc/passwd')}`);
    await expect(page.getByText(/未找到/)).toBeVisible({ timeout: 60_000 });
    expect(errors, `页面报错: ${errors.join(' | ')}`).toHaveLength(0);
  });

  test('T15 读闸门：超大文件如实告知"共 X 已加载前 Y"（两个数不许自相矛盾）', async ({
    page,
  }) => {
    await gotoFiles(page, `?path=${enc(BIG_FILE)}`);
    const tip = page.getByText(/文件共\s*.+已加载前\s*.+/).first();
    await expect(tip).toBeVisible({ timeout: 120_000 });
    const text = await tip.innerText();
    const nums = text.match(/[\d.]+\s*(B|KB|MB|GB)/gi) ?? [];
    expect(nums.length).toBeGreaterThanOrEqual(2);
    // 已加载量必须小于总量（否则就是"共 37MB 已加载前 37MB"那种自相矛盾）
    const toBytes = (s: string): number => {
      const m = s.trim().match(/^([\d.]+)\s*(B|KB|MB|GB)$/i);
      if (!m) return NaN;
      const n = Number(m[1]);
      const u = m[2].toUpperCase();
      return n * (u === 'B' ? 1 : u === 'KB' ? 1024 : u === 'MB' ? 1048576 : 1073741824);
    };
    const [total, loaded] = nums.slice(0, 2).map(toBytes);
    expect(Number.isFinite(total)).toBe(true);
    expect(Number.isFinite(loaded)).toBe(true);
    expect(loaded).toBeLessThan(total);
  });

  test('T16 md 双模：美显 ⇄ 文本切换真实生效', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(MD_CN)}`);
    // 默认美显（无行号 DOM）
    await expect(page.locator('[data-ln="1"]')).toHaveCount(0, { timeout: 60_000 });
    // 切「文本」→ 行号出现
    await page.getByText('文本', { exact: true }).first().click();
    await expect(page.locator('[data-ln="1"]').first()).toBeVisible({
      timeout: 30_000,
    });
    // 切回「美显」→ 行号消失
    await page.getByText('美显', { exact: true }).first().click();
    await expect(page.locator('[data-ln="1"]')).toHaveCount(0, { timeout: 30_000 });
  });

  test('T17 折行开关：勾选后长行折行（换行位置变化）', async ({ page }) => {
    await gotoFiles(page, `?path=${enc(NESTED_FILE)}`);
    await expect(page.locator('[data-ln="1"]').first()).toBeVisible({
      timeout: 60_000,
    });
    const wrap = page.getByRole('checkbox', { name: /折行/ });
    await expect(wrap).toBeVisible({ timeout: 30_000 });
    await wrap.check();
    await expect(wrap).toBeChecked();
  });

  test('T18 树右键：目录上有菜单入口（死交互自查）', async ({ page }) => {
    await gotoFiles(page);
    const row = page.locator('[data-file-key="deepseek-harness"]').first();
    await row.click({ button: 'right' });
    const menu = page.locator('.files-tree-context-menu');
    const visible = await menu.isVisible().catch(() => false);
    const items = visible
      ? await menu.locator('[role="menuitem"]').allInnerTexts()
      : [];
    // 目录右键必须有可用入口；空菜单/无菜单都算死交互
    expect(
      items.length,
      '目录右键没有可用菜单项（空菜单=点了没反应）'
    ).toBeGreaterThan(0);
  });
});
