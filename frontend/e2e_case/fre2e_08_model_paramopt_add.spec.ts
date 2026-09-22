import { test, expect } from '@playwright/test';
import * as fs from 'fs';

/**
 * [62]P5 添加模型参数模板全链路 E2E-01 — 小欧 2026-09-22（重写重跑版）
 *
 * 环境: 真实后端 :8000 + 真实前端 :5173（Vite proxy /api→8000）+ 真实 config.yaml。
 * 前置: 后端/前端已手动启动（本 case 不拉起）。有头浏览器（--headed）。
 *
 * 链路: 预置兄弟 param_options → 弹窗模板区(并集+默认 medium) → 勾选 reasoning_effort → 改 high
 *   → POST /models body 含 high+param_options → config.yaml 落盘(model_params+model_meta)
 *   → 切新模型参数区下拉 value=high（回显）
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试代码文件 —— 本 spec 严禁提交。
 */
const CONFIG_YAML = 'F:\\OmniAgentAs-repair\\config\\config.yaml';
const PROVIDER = 'sensenova';
const SIBLING = 'deepseek-v4-flash'; // 兄弟模型（已有 model_params 含 reasoning_effort）

const stamp = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
};

test.describe('添加模型参数模板全链路 E2E-01 (有头)', () => {
  test('模板区勾选 reasoning_effort=high → 落盘 → 回显下拉', async ({ page, request }) => {
    test.setTimeout(180_000);
    const newModel = `e2e-opt-${stamp()}`;

    // 0) 预置兄弟模型 param_options（PUT /models 合并写 model_meta）——模板区才渲染 Select
    const preseed = await request.put(
      `http://127.0.0.1:8000/api/v1/models/${PROVIDER}/${SIBLING}`,
      {
        data: { param_options: { reasoning_effort: ['low', 'medium', 'high'] } },
      }
    );
    expect(preseed.status()).toBe(200);
    console.log(`[E2E] 步骤0 预置兄弟 param_options ok (status=${preseed.status()})`);

    // 1) 拦截 POST /models
    let postBody: Record<string, unknown> | null = null;
    page.on('request', (req) => {
      if (
        req.method() === 'POST' &&
        req.url().includes('/api/v1/models') &&
        !req.url().includes('/current')
      ) {
        try {
          postBody = req.postDataJSON();
        } catch {
          /* noop */
        }
      }
    });

    // 2) 打开设置页 → 模型 Tab
    await page.goto('http://localhost:5173/settings2');
    await expect(page.locator('.settings-page')).toBeVisible({ timeout: 30_000 });
    const modelTab = page.getByRole('tab', { name: /模\s*型/ }).first();
    await modelTab.click();
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 3) 打开「添加模型」弹窗
    await page.getByRole('button', { name: /添加模型/ }).click();
    const modal = page.getByRole('dialog', { name: '添加模型' });
    await expect(modal).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(800); // 观察弹窗打开

    // 4) Provider 切到 sensenova → 模板区候选重算（兄弟模型有参数才渲染模板区）
    await modal.locator('.ant-select').first().click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: PROVIDER })
      .first()
      .click();
    await expect(modal.getByText('参数模板（勾选即带入新模型）')).toBeVisible({
      timeout: 15_000,
    });
    await page.waitForTimeout(800); // 观察模板区出现

    // 5) 模板区出现 reasoning_effort（并集候选）+ 兄弟有枚举 → Select 默认值 medium
    const tplRow = modal
      .locator('label.ant-checkbox-wrapper')
      .filter({ hasText: 'reasoning_effort' })
      .first()
      .locator('xpath=parent::div');
    await expect(tplRow.locator('.ant-select')).toBeVisible({ timeout: 15_000 });
    await expect(
      tplRow.locator('.ant-select-selection-item, .ant-select-selection-selected-value')
    ).toContainText('medium');
    console.log('[E2E] 步骤5 模板区 reasoning_effort 行已出, 默认 medium');

    // 6) 勾选 reasoning_effort
    await modal
      .locator('label.ant-checkbox-wrapper')
      .filter({ hasText: 'reasoning_effort' })
      .first()
      .click();
    await page.waitForTimeout(800); // 观察勾选后界面

    // 7) 模板区 Select 改为 high
    await tplRow.locator('.ant-select').click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: 'high' })
      .first()
      .click();
    await page.waitForTimeout(800); // 观察改为 high 后界面

    // 8) 填模型名/label → 保存
    const modelInput = modal.getByRole('textbox', { name: /模型名/ });
    await expect(modelInput).toBeVisible({ timeout: 15_000 });
    await modelInput.fill(newModel);
    const labelInput = modal.getByRole('textbox', { name: /显示名/ });
    await labelInput.fill('E2E参数模板模型');
    await modal.locator('.ant-modal-footer button.ant-btn-primary').click();
    console.log('[E2E] 步骤8 已填 模型名/显示名 并点击保存');

    // 9) POST /models body 断言
    await expect
      .poll(
        () => JSON.stringify(postBody ?? null),
        { timeout: 30_000 }
      )
      .toContain('"reasoning_effort"');
    const b = postBody as Record<string, unknown>;
    expect(b.provider).toBe(PROVIDER);
    expect(b.model).toBe(newModel);
    expect(
      (b.default_params as Record<string, unknown>).reasoning_effort
    ).toBe('high');
    const po = (b.param_options as Record<string, string[]>) ?? {};
    expect(po.reasoning_effort).toEqual(['low', 'medium', 'high']);
    console.log(
      `[E2E] 步骤9 POST body 校验通过: provider=${b.provider} model=${b.model} ` +
        `default_params.reasoning_effort=${JSON.stringify((b.default_params as Record<string, unknown>).reasoning_effort)} ` +
        `param_options.reasoning_effort=${JSON.stringify(po.reasoning_effort)}`
    );

    // 10) 弹窗关闭
    await expect(modal).toBeHidden({ timeout: 30_000 });

    // 11) config.yaml 落盘校验
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 15_000 })
      .toContain(`reasoning_effort: high`);
    const cfg = fs.readFileSync(CONFIG_YAML, 'utf8');
    // YAML 序列为多行格式（- low / - medium / - high），非内联 `[low, medium, high]`
    const hasParams = cfg.includes('reasoning_effort: high');
    const hasMeta =
      cfg.includes('param_options') &&
      cfg.includes('- low') &&
      cfg.includes('- medium') &&
      cfg.includes('- high');
    expect(hasParams).toBeTruthy();
    expect(hasMeta).toBeTruthy();
    console.log(
      `[E2E] 步骤11 config.yaml 落盘 ok: model_params.reasoning_effort=high=${hasParams} model_meta.param_options=${hasMeta}`
    );

    // 12) 切到新模型 → 参数区 reasoning_effort 下拉 value=high（回显）
    // 12a) 选择器区模型下拉显示新模型 label（refreshModels select 定位后 paramOptions 已注入）
    await expect
      .poll(
        async () => {
          const sel = page.locator(
            '.ant-select-selection-item, .ant-select-selection-selected-value'
          );
          for (let i = 0; i < (await sel.count()); i += 1) {
            const t = await sel.nth(i).innerText();
            if (t.includes('E2E参数模板模型') || t.includes('e2e-opt-')) {
              return true;
            }
          }
          return false;
        },
        { timeout: 45_000 }
      )
      .toBeTruthy();
    // 12b) 参数区 reasoning_effort 行（②参数区）Select value=high —— 读链组装回显的下拉
    const paramRow = page
      .locator('div')
      .filter({ hasText: 'reasoning_effort' })
      .filter({ has: page.locator('.ant-select') })
      .last();
    await expect
      .poll(
        async () => {
          const v = await paramRow
            .locator('.ant-select-selection-item, .ant-select-selection-selected-value')
            .innerText();
          return v;
        },
        { timeout: 15_000 }
      )
      .toBe('high');
    console.log('[E2E] 步骤12 回显通过: 新模型选中 + 参数区下拉 value=high');
  });
});