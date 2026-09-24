import { test, expect, type Page } from '@playwright/test';
import * as http from 'http';
import * as fs from 'fs';

/**
 * [68]§6.2 模型库 Tab 全链路 E2E — 小欧 2026-09-25
 *
 * 环境: 真实后端 :8000 + 真实前端 :5173 + 真实 config.yaml + 本地 mock /models。
 * 前置: 后端/前端已手动启动（本 case 不拉起）。有头浏览器（--headed）。
 *
 * 链路(设计 6.2 手工 E2E 自动化落地):
 *   1) 模型库 Tab 加载 → 获取按钮/过滤区/空态可见
 *   2) 获取模型列表（本地 mock 远端）→ 分组标题 + 统计行
 *   3) 三项过滤各自生效：关键词 id / 关键词 owned_by / 仅看免费
 *   4) 勾选未配置模型 → 保存所选计数变化
 *   5) 保存确认弹窗文案 → 确认 → PUT 落盘 → 模型 Tab 出现新模型
 *   6) 取消勾选新模型 → 再保存 → 模型消失且参数区无孤儿键
 *
 * mock 说明: 后端 fetch_remote_models 走 GET {api_base}/models；本 case 起本地
 * http server 返回 OpenAI 形状 {data:[{id,owned_by}]}，api_base 指向 127.0.0.1，
 * 避免无真实 Key 时远程拉取失败导致过滤/保存链路被跳过。
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试代码文件 —— 本 spec 严禁提交。
 *
 * 编辑历史: 2026-09-25 00:15:06 小欧 - 新建：[68]§6.2 模型库 E2E 自动化 — 小欧-2026-09-25
 * 编辑历史: 2026-09-25 00:41:00 小欧 - 强化覆盖：本地 mock /models 打通获取→三项过滤→勾选→
 *   保存→模型Tab出现→取消勾选→无孤儿全链路；补强分组/统计/行数/孤儿键断言 — 小欧-2026-09-25
 */
const CONFIG_YAML = 'F:\\OmniAgentAs-repair\\config\\config.yaml';
const BASE = 'http://127.0.0.1:8000/api/v1';

// mock 远端模型（含 free/非 free、多 owned_by，覆盖 D4 三项过滤）
const SEED_ID = 'e2e-seed-free';
const ALPHA_ID = 'e2e-alpha-pro';
const BETA_ID = 'e2e-beta-free';
const GAMMA_ID = 'e2e-gamma-std';
const PICKLE_ID = 'big-pickle';
const MOCK_DATA = [
  { id: SEED_ID, owned_by: 'e2e-lab' },
  { id: ALPHA_ID, owned_by: 'acme' },
  { id: BETA_ID, owned_by: 'globex' },
  { id: GAMMA_ID, owned_by: 'acme' },
  { id: PICKLE_ID, owned_by: 'local' },
];
const ALL_IDS = MOCK_DATA.map((m) => m.id);

const stamp = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
};

const goto = async (page: Page) => {
  await page.goto(`http://localhost:5173/settings2?t=${Date.now()}`);
  await expect(page.locator('.settings-page')).toBeVisible({ timeout: 30_000 });
};

const tab = async (page: Page, name: RegExp | string) => {
  await page.getByRole('tab', { name }).first().click();
  await page.waitForTimeout(600);
};

// 模型库 Tab 的 Provider Select：限定在「获取模型列表」按钮同排，避免命中顶栏全局模型切换器
const libProviderSelect = (page: Page) =>
  page
    .getByRole('button', { name: /获取模型列表/ })
    .locator('xpath=..')
    .locator('.ant-select-selector');

const pickLibProvider = async (page: Page, pname: string) => {
  const provSel = libProviderSelect(page);
  await provSel.scrollIntoViewIfNeeded();
  await provSel.click();
  await expect(page.locator('.ant-select-dropdown:visible')).toBeVisible({
    timeout: 10_000,
  });
  await page
    .locator('.ant-select-dropdown:visible .ant-select-item')
    .filter({ hasText: pname })
    .first()
    .click();
  await page.waitForTimeout(400);
};

// 列表区可见模型 id 集合（按 mock 全集探测，排除过滤区「仅看免费」复选框）
const visibleIds = async (page: Page): Promise<string[]> => {
  const present: string[] = [];
  for (const id of ALL_IDS) {
    const n = await page.getByText(id, { exact: true }).count();
    if (n > 0) present.push(id);
  }
  return present;
};

const rowCheckbox = (page: Page, id: string) =>
  page
    .locator('.settings-page')
    .getByText(id, { exact: true })
    .first()
    .locator('xpath=..')
    .locator('.ant-checkbox-wrapper')
    .first();

test.describe.configure({ mode: 'serial' });

test.describe('模型库 Tab 全链路 E2E-12 (有头+mock)', () => {
  let mockServer: http.Server;
  let mockPort = 0;

  test.beforeAll(async () => {
    mockServer = http.createServer((req, res) => {
      if ((req.url ?? '').includes('/models')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ data: MOCK_DATA }));
        return;
      }
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'not found' }));
    });
    await new Promise<void>((resolve) => {
      mockServer.listen(0, '127.0.0.1', () => {
        const addr = mockServer.address();
        mockPort = typeof addr === 'object' && addr ? addr.port : 0;
        resolve();
      });
    });
    expect(mockPort).toBeGreaterThan(0);
    console.log(`[E2E] mock /models 监听 127.0.0.1:${mockPort}`);
  });

  test.afterAll(async () => {
    await new Promise<void>((resolve) => {
      mockServer.close(() => resolve());
    });
  });

  test('获取→三项过滤→勾选→保存→模型Tab出现→取消勾选→消失无孤儿', async ({
    page,
    request,
  }) => {
    test.setTimeout(300_000);

    // 0) 预置独立测试 Provider（api_base → 本地 mock）+ seed 模型
    const pname = `e2e-lib-${stamp()}`;
    const apiBase = `http://127.0.0.1:${mockPort}/v1`;
    const add = await request.post(`${BASE}/providers`, {
      data: {
        name: pname,
        label: pname,
        api_base: apiBase,
        api_key: 'mock-key',
        model: '',
        timeout: 60,
        max_retries: 2,
      },
    });
    expect(add.status()).toBe(200);
    console.log(`[E2E] 步骤0 添加 Provider ${pname} api_base=${apiBase}`);

    const am = await request.post(`${BASE}/models`, {
      data: {
        provider: pname,
        model: SEED_ID,
        label: SEED_ID,
        default_params: { temperature: 0.7 },
      },
    });
    expect(am.status()).toBe(200);

    try {
      // 1) 模型库 Tab 加载
      await goto(page);
      await tab(page, /模型库/);
      await expect(page.getByText('── ① 获取 ──')).toBeVisible({
        timeout: 10_000,
      });
      await expect(page.getByText('── ② 过滤 ──')).toBeVisible();
      await expect(page.getByText('── ③ 列表 ──')).toBeVisible();
      await expect(
        page.getByRole('button', { name: /获取模型列表/ })
      ).toBeVisible();
      await expect(page.getByText(/点击「获取模型列表」/)).toBeVisible();
      console.log('[E2E] 步骤1 模型库 Tab 加载 ok');

      await pickLibProvider(page, pname);

      // 2) 获取模型列表（本地 mock 必成功）
      const fetchBtn = page.getByRole('button', { name: /获取模型列表/ });
      expect(await fetchBtn.isDisabled()).toBe(false);
      await fetchBtn.click();
      const stats = page.getByText(/共 5 个模型，已配置 1 个/);
      await expect(stats).toBeVisible({ timeout: 20_000 });
      await expect(page.getByText(/已勾选 1 个/)).toBeVisible();
      await expect(page.locator('.ant-alert-error')).toHaveCount(0);
      console.log('[E2E] 步骤2 获取成功 统计行 ok');

      // 分组标题
      await expect(page.getByText(/已配置（1）/)).toBeVisible();
      await expect(page.getByText(/未配置 · 待挑选（4）/)).toBeVisible();
      console.log('[E2E] 步骤2b 分组标题 ok');

      // 3) 三项过滤各自生效
      const search = page.getByPlaceholder('搜索模型名 / 作者');
      const freeBox = page.getByRole('checkbox', { name: /仅看免费/ });

      // 3a 关键词 id：free → 含 free 的 id
      await search.fill('free');
      await page.waitForTimeout(300);
      let visible = await visibleIds(page);
      expect(visible.sort()).toEqual([SEED_ID, BETA_ID].sort());
      console.log(`[E2E] 步骤3a 关键词 free → ${visible.join(',')}`);

      // 3b 关键词 owned_by：acme → alpha + gamma
      await search.fill('acme');
      await page.waitForTimeout(300);
      visible = await visibleIds(page);
      expect(visible.sort()).toEqual([ALPHA_ID, GAMMA_ID].sort());
      console.log(`[E2E] 步骤3b 关键词 acme → ${visible.join(',')}`);

      // 3b2 owned_by globex → beta
      await search.fill('globex');
      await page.waitForTimeout(300);
      visible = await visibleIds(page);
      expect(visible).toEqual([BETA_ID]);
      console.log(`[E2E] 步骤3b2 关键词 globex → ${visible.join(',')}`);

      // 3c 仅看免费：-free / big-pickle
      await search.fill('');
      await freeBox.check();
      await page.waitForTimeout(300);
      visible = await visibleIds(page);
      expect(visible.sort()).toEqual([SEED_ID, BETA_ID, PICKLE_ID].sort());
      console.log(`[E2E] 步骤3c 仅看免费 → ${visible.join(',')}`);
      await freeBox.uncheck();
      await page.waitForTimeout(200);
      visible = await visibleIds(page);
      expect(visible.length).toBe(5);
      console.log('[E2E] 步骤3 清过滤恢复 5 行 ok');

      // 4) 勾选未配置模型 alpha → 保存计数 1→2
      await expect(
        page.getByRole('button', { name: /保存所选（1）/ })
      ).toBeVisible();
      await rowCheckbox(page, ALPHA_ID).click();
      await expect(
        page.getByRole('button', { name: /保存所选（2）/ })
      ).toBeVisible({ timeout: 5_000 });
      console.log('[E2E] 步骤4 勾选 alpha → 保存所选（2）ok');

      // 5) 保存确认 → PUT 落盘 → 模型 Tab 出现新模型
      await page.getByRole('button', { name: /保存所选（2）/ }).click();
      const confirm = page.locator('.ant-modal-confirm');
      await expect(confirm).toBeVisible({ timeout: 10_000 });
      const content = await confirm.innerText();
      expect(content).toContain('替换模型列表');
      expect(content).toContain('已勾选的 2 个');
      expect(content).toContain('移除');
      console.log(
        `[E2E] 步骤5 确认弹窗: ${content.replace(/\s+/g, ' ').slice(0, 120)}`
      );
      await confirm.locator('.ant-btn-primary').click();
      await page.waitForTimeout(2000);
      await expect
        .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 15_000 })
        .toContain(pname);
      console.log('[E2E] 步骤5 保存落盘 ok');

      // 模型 Tab 出现新模型 alpha
      await tab(page, /模\s*型/);
      const provSel2 = page
        .locator('[data-section="selector"] .ant-select')
        .first();
      await provSel2.scrollIntoViewIfNeeded();
      await provSel2.click();
      await page
        .locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: pname })
        .first()
        .click();
      await page.waitForTimeout(600);
      const modelSel = page
        .locator('[data-section="selector"] .ant-select')
        .nth(1);
      await modelSel.click();
      const dd = page.locator('.ant-select-dropdown:visible');
      await expect(dd).toBeVisible({ timeout: 5_000 });
      await expect(
        dd.locator('.ant-select-item').filter({ hasText: ALPHA_ID }).first()
      ).toBeVisible({ timeout: 10_000 });
      console.log('[E2E] 步骤5b 模型 Tab 出现 alpha 模型 ok');
      page.keyboard.press('Escape');
      await page.waitForTimeout(300);

      // 6) 给 alpha 挂 model_params（制造孤儿清理前置条件）
      const putAlpha = await request.put(
        `${BASE}/models/${encodeURIComponent(pname)}/${encodeURIComponent(ALPHA_ID)}`,
        { data: { default_params: { temperature: 0.7 } } }
      );
      expect([200, 204]).toContain(putAlpha.status());
      const yamlAfterPut = fs.readFileSync(CONFIG_YAML, 'utf8');
      expect(yamlAfterPut).toContain(ALPHA_ID);
      console.log('[E2E] 步骤6 alpha 已挂 default_params ok');

      // 7) 回模型库，取消勾选 alpha，再保存 → alpha 消失 + 无孤儿
      await tab(page, /模型库/);
      await pickLibProvider(page, pname);
      const fetchBtn2 = page.getByRole('button', { name: /获取模型列表/ });
      await fetchBtn2.click();
      await expect(page.getByText(/共 5 个模型/)).toBeVisible({
        timeout: 20_000,
      });
      // 此时 configured = seed+alpha → 已勾选 2
      await expect(page.getByText(/已配置 2 个/)).toBeVisible();
      await rowCheckbox(page, ALPHA_ID).click();
      await expect(
        page.getByRole('button', { name: /保存所选（1）/ })
      ).toBeVisible({ timeout: 5_000 });
      console.log('[E2E] 步骤7 取消 alpha → 保存所选（1）ok');

      await page.getByRole('button', { name: /保存所选（1）/ }).click();
      const confirm2 = page.locator('.ant-modal-confirm');
      await expect(confirm2).toBeVisible({ timeout: 10_000 });
      const content2 = await confirm2.innerText();
      expect(content2).toContain('移除 1 个');
      await confirm2.locator('.ant-btn-primary').click();
      await page.waitForTimeout(2000);
      console.log('[E2E] 步骤7b 移除保存确认 ok');

      // 7c) GET /models：alpha 不在列表；config.yaml 无 alpha 孤儿键
      await expect
        .poll(
          async () => {
            const resp = await request.get(`${BASE}/models`);
            const json = (await resp.json()) as {
              providers?: Array<{
                name: string;
                models?: Array<{ name: string }>;
              }>;
            };
            const p = (json.providers ?? []).find((x) => x.name === pname);
            return (p?.models ?? []).map((m) => m.name);
          },
          { timeout: 15_000 }
        )
        .toEqual([SEED_ID]);

      // yaml 残留诊断：轮询至无 alpha（防写盘竞态），超时则打印命中行
      try {
        await expect
          .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 15_000 })
          .not.toContain(ALPHA_ID);
      } catch (e) {
        const lines = fs.readFileSync(CONFIG_YAML, 'utf8').split(/\r?\n/);
        const hits = lines
          .map((l, i) => `${i + 1}: ${l}`)
          .filter((l) => l.includes(ALPHA_ID));
        console.log(`[E2E] yaml alpha 残留命中:\n${hits.join('\n')}`);
        throw e;
      }
      const yaml = fs.readFileSync(CONFIG_YAML, 'utf8');
      expect(yaml.includes(SEED_ID)).toBe(true);
      console.log(
        '[E2E] 步骤7c 无孤儿：models=[seed] 且 yaml 无 alpha 残留 ok'
      );

      // 7d) 模型 Tab 下拉仅剩 seed，无 alpha
      await tab(page, /模\s*型/);
      const provSel3 = page
        .locator('[data-section="selector"] .ant-select')
        .first();
      await provSel3.scrollIntoViewIfNeeded();
      await provSel3.click();
      await page
        .locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: pname })
        .first()
        .click();
      await page.waitForTimeout(600);
      const modelSel3 = page
        .locator('[data-section="selector"] .ant-select')
        .nth(1);
      await modelSel3.click();
      const dd3 = page.locator('.ant-select-dropdown:visible');
      await expect(dd3).toBeVisible({ timeout: 5_000 });
      await expect(
        dd3.locator('.ant-select-item').filter({ hasText: SEED_ID }).first()
      ).toBeVisible();
      await expect(
        dd3.locator('.ant-select-item').filter({ hasText: ALPHA_ID })
      ).toHaveCount(0);
      page.keyboard.press('Escape');
      console.log('[E2E] 步骤7d 模型 Tab 无 alpha 残留 ok');

      console.log('[E2E] fre2e_12 全链路断言全部通过');
    } finally {
      const del = await request.delete(`${BASE}/providers/${pname}`);
      console.log(`[E2E] 清理 删除 Provider ${pname} → ${del.status()}`);
    }
  });
});
