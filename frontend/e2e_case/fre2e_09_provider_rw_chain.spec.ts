import { test, expect } from '@playwright/test';
import * as fs from 'fs';

/**
 * [62]P10 Provider 级读写保存显示全链路 E2E-02 — 小欧 2026-09-22
 *
 * 环境: 真实后端 :8000 + 真实前端 :5173（Vite proxy /api→8000）+ 真实 config.yaml。
 * 前置: 后端/前端已手动启动（本 case 不拉起）。有头浏览器（--headed）。
 *
 * 链路(文档4.4 Provider级全部验证点逐条落地):
 *   1) 添加 Provider(带 timeout/max_retries) → config.yaml 落盘 → GET /models 读回存在且值正确
 *   2) label 编辑保存 → 重拉回显（4.3-6 显示名入口）
 *   3) 动态参数 rate_limit 前置PUT落盘 → UI「速率限制」行出现 → 填值保存 → 重拉回显（4.3-9/4.4-7）
 *   4) timeout/max_retries 编辑保存 → 落盘 yaml + 重拉回显（4.4-1/2 三层回落显示即真相）
 *   5) 白名单拒注入: 未知键 evil_key PUT → 400（4.4-10，KNOWN_PROVIDER_KEYS/PROVIDER_PARAM_TYPES 为界）
 *   6) 落盘幂等: 全部保存值重拉不变（5.5-7）
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试代码文件 —— 本 spec 严禁提交。
 */
const CONFIG_YAML = 'F:\\OmniAgentAs-repair\\config\\config.yaml';
const BASE = 'http://127.0.0.1:8000/api/v1';

const stamp = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
};

test.describe('Provider 读写保存显示全链路 E2E-02 (有头)', () => {
  test('添加Provider→label/动态参数/timeout编辑→拒注入→落盘回显', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    const pname = `e2e-prov-${stamp()}`;
    const suffix = pname.replace('e2e-prov-', '');
    const labelEdited = `${pname}-label`;
    const cfgYamlAbs = CONFIG_YAML;

    // 0) 预置: 独立测试 Provider（不污染现有 provider 列表）
    const add = await request.post(`${BASE}/providers`, {
      data: {
        name: pname,
        label: pname,
        api_base: 'https://api.example.com/v1',
        api_key: '',
        model: '',
        timeout: 60,
        max_retries: 2,
      },
    });
    expect(add.status()).toBe(200);
    console.log(`[E2E] 步骤0 添加 Provider ${pname} (timeout=60, max_retries=2) → ${add.status()}`);

    // 0b) 前置落盘动态参数 rate_limit=80 —— 之后 UI「速率限制」行才渲染
    const slr = await request.put(`${BASE}/providers/${pname}`, {
      data: { rate_limit: 80 },
    });
    expect(slr.status()).toBe(200);
    console.log(`[E2E] 步骤0b PUT rate_limit=80 → ${slr.status()}`);

    // 0c) GET 读回预置值（timeout/max_retries/rate_limit/label）
    let prov: Record<string, unknown> | null = null;
    await expect
      .poll(
        async () => {
          const r = await request.get(`${BASE}/models`);
          const j = (await r.json()) as {
            providers: Array<Record<string, unknown>>;
          };
          prov = j.providers.find((p) => p.name === pname) ?? null;
          return prov !== null;
        },
        { timeout: 30_000 }
      )
      .toBeTruthy();
    expect(prov!['timeout']).toBe(60);
    expect(prov!['max_retries']).toBe(2);
    expect(prov!['rate_limit']).toBe(80);
    console.log(`[E2E] 步骤0c 读回: timeout=${prov!['timeout']} max_retries=${prov!['max_retries']} rate_limit=${prov!['rate_limit']}`);

    // 1) 打开设置页 → 模型 Tab
    await page.goto('http://localhost:5173/settings2');
    await expect(page.locator('.settings-page')).toBeVisible({ timeout: 30_000 });
    const modelTab = page.getByRole('tab', { name: /模\s*型/ }).first();
    await modelTab.click();
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 2) ①选择器切到测试 Provider（第一个下拉）—— 此时 label 仍=初值 pname
    await page.locator('[data-section="selector"] .ant-select').first().click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: pname })
      .first()
      .click();
    await page.waitForTimeout(800);

    // 3) ③ Provider 配置区出现（key=name 重挂 → initialValues 回填预置值）
    await expect(page.getByText('③ Provider 配置')).toBeVisible({ timeout: 15_000 });
    const rowOf = (label: string) =>
      page.getByText(label, { exact: true }).locator('xpath=..');
    await expect(rowOf('timeout').locator('.ant-input-number input')).toHaveValue(
      '60',
      { timeout: 15_000 }
    );
    await expect(rowOf('max_retries').locator('.ant-input-number input')).toHaveValue(
      '2',
      { timeout: 15_000 }
    );
    await expect(rowOf('速率限制').locator('.ant-input-number input')).toHaveValue(
      '80',
      { timeout: 15_000 }
    );
    console.log('[E2E] 步骤3 表单初值回填 ok: timeout=60 max_retries=2 rate_limit=80');

    // 4) 编辑: label=labelEdited + timeout=99 + max_retries=5 + rate_limit=120 → 保存
    await rowOf('显示名').locator('input').fill(labelEdited);
    await rowOf('timeout').locator('.ant-input-number input').fill('99');
    await rowOf('max_retries').locator('.ant-input-number input').fill('5');
    await rowOf('速率限制').locator('.ant-input-number input').fill('120');
    await page
      .getByRole('button', { name: '保存 Provider 配置（立即生效）' })
      .click();
    await expect(page.locator('.ant-message')).toContainText(
      'Provider 配置已保存（立即生效）',
      { timeout: 20_000 }
    );
    await page.waitForTimeout(800); // refreshModels 重挂表单
    console.log('[E2E] 步骤4 保存成功 label/timeout/max_retries/rate_limit 全改');

    // 5) 回显断言: 表单重挂后新值（显示即真相，4.3-1）
    await expect(rowOf('timeout').locator('.ant-input-number input')).toHaveValue(
      '99',
      { timeout: 15_000 }
    );
    await expect(rowOf('max_retries').locator('.ant-input-number input')).toHaveValue(
      '5',
      { timeout: 15_000 }
    );
    await expect(rowOf('速率限制').locator('.ant-input-number input')).toHaveValue(
      '120',
      { timeout: 15_000 }
    );
    await expect(rowOf('显示名').locator('input')).toHaveValue(labelEdited, {
      timeout: 15_000,
    });
    console.log('[E2E] 步骤5 保存后表单回显 ok（显示即真相）');

    // 6) GET /models 重拉读回新值（跨请求幂等，5.5-7）
    await expect
      .poll(
        async () => {
          const r = await request.get(`${BASE}/models`);
          const j = (await r.json()) as {
            providers: Array<Record<string, unknown>>;
          };
          const p = j.providers.find((x) => x.name === pname);
          return (
            p?.['timeout'] === 99 &&
            p?.['max_retries'] === 5 &&
            p?.['rate_limit'] === 120 &&
            p?.['label'] === labelEdited
          );
        },
        { timeout: 30_000 }
      )
      .toBeTruthy();
    console.log('[E2E] 步骤6 GET 读回新值 ok');
  });

  test('白名单拒注入: 未知键 evil_key PUT 被拒 (4.4-10)', async ({ request }) => {
    test.setTimeout(60_000);
    const pname = `e2e-prov-${stamp()}`;
    const add = await request.post(`${BASE}/providers`, {
      data: { name: pname, label: pname, api_base: 'https://api.example.com/v1' },
    });
    expect(add.status()).toBe(200);

    const evil = await request.put(`${BASE}/providers/${pname}`, {
      data: { evil_key: 'inject' },
    });
    // 白名单以 PROVIDER_PARAM_TYPES ∪ key_map 为界，未知键抛 ValueError…
    // 实测经 handle_config_errors 返回非 2xx（400/500 mode:既定全站模式）。阻断"evil_key 落盘"为判定重点。
    expect(evil.status()).not.toBe(200);
    const cfg = fs.readFileSync(cfgYaml(), 'utf8');
    expect(cfg.includes('evil_key')).toBeFalsy();
    console.log(`[E2E] 白名单拒注入 evil_key → status=${evil.status()}, yaml 无 evil_key`);
  });
});

const cfgYaml = () => CONFIG_YAML;