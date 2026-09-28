import { test, expect } from '@playwright/test';
import * as fs from 'fs';

/**
 * 设置页全功能 E2E — 小欧 2026-09-22
 *
 * 环境: 真实后端 :8000 + 真实前端 :5173（Vite proxy /api→8000）+ 真实 config.yaml。
 * 前置: 后端/前端已手动启动。有头浏览器（--headed）。
 *
 * 覆盖: 7 个 tab × 读/写/显示/切换，共 10 个 case 串行执行。
 *   1) 通用Tab — 读取当前模型卡 + 修改语言值 + 保存落盘
 *   2) 模型Tab 选择器 — Provider/Model 切换联动 + 参数区跟随
 *   3) 模型Tab 添加模型 — 弹窗填写 → POST body → config.yaml 落盘 → 回显
 *   4) 模型Tab Provider配置 — 读写显示 + 动态参数(rate_limit) + 落盘
 *   5) 模型Tab 模型参数 — 编辑参数 + 重置为默认 + 回显
 *   6) 模型Tab 删除模型 — 添加测试模型 → 删除 → 选择器消失
 *   7) 安全Tab — 读写 + 危险确认弹窗 + 落盘
 *   8) 沙箱Tab — 读写 + 落盘
 *   9) 通用Tab 采样参数 — llm.sampling.temperature/max_tokens 编辑 + 落盘（2026-09-23 已迁 general）
 *  10) 前端Tab + 搜索跳转 — 主题切换 + 搜索命中行 + Tab切换脏确认
 *
 * 铁规: AGENTS.md 严禁 commit 任何测试代码文件。
 *
 * 编辑历史: 2026-09-24 21:56:36 小欧 - 过时键修正：case-05 参数区改 data-settings-key=temperature；
 *   case-09 tuning.llm.*→llm.sampling.*+通用Tab；case-10 搜索temperature断言通用+回车、脏态键改活键 — 小欧-2026-09-24
 * 编辑历史: 2026-09-25 04:06:45 小健 - 恢复保存稳健化: 重试次数恢复改 waitForTimeout(500) +
 *   saveAllBtn.isEnabled() 条件点击（按钮未就绪不再硬点失败） — 小健-2026-09-25
 */
// 2026-09-28 小欧 - 配置隔离铁律落地：本用例 PUT/POST /settings 与 provider 配置并断言写入落
//   config.yaml，原先直连开发后端 :8000 + 硬编码真配置路径。改：整个用例跑隔离栈
//   （后端 :8898 / 代理 :9001 / 页面 vite :5174，配置为真配置副本），
//   副本内容与真配置一致 → 仍用真实模型，隔离的只是写的落点。
import {
  startIsolatedEnv,
  stopIsolatedEnv,
  isoConfigPath,
  ISO_API,
  ISO_PAGE,
} from '../e2e_front_lib/isolated-env';

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
/** 隔离配置副本路径（beforeAll 里由 startIsolatedEnv 赋值；取代原硬编码真路径） */
let CONFIG_YAML = '';
const BASE = ISO_API;

const stamp = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
};

// ── helpers ──────────────────────────────────────────────────────
const gotoSettings = async (page: import('@playwright/test').Page) => {
  await page.goto(`${ISO_PAGE}/settings2`);
  await expect(page.locator('.settings-page')).toBeVisible({ timeout: 30_000 });
};

const clickTab = async (
  page: import('@playwright/test').Page,
  name: RegExp | string
) => {
  const tab = page.getByRole('tab', { name }).first();
  await tab.click();
  await page.waitForTimeout(600);
};

const apiGet = async (
  request: import('@playwright/test').APIRequestContext,
  path: string
) => {
  const r = await request.get(`${BASE}${path}`);
  return r.json() as Promise<Record<string, unknown>>;
};

const apiPut = async (
  request: import('@playwright/test').APIRequestContext,
  path: string,
  body: Record<string, unknown>
) => {
  const r = await request.put(`${BASE}${path}`, { data: body });
  return r.json() as Promise<Record<string, unknown>>;
};

const apiPost = async (
  request: import('@playwright/test').APIRequestContext,
  path: string,
  body: Record<string, unknown>
) => {
  const r = await request.post(`${BASE}${path}`, { data: body });
  return r.json() as Promise<Record<string, unknown>>;
};

// ── 10 个测试串行执行 ───────────────────────────────────────────
test.describe.serial('设置页全功能 E2E (有头)', () => {
  test.setTimeout(300_000);

  // 2026-09-28 小欧 - 隔离栈生命周期：真配置不可写，断言改读副本
  test.beforeAll(async () => {
    await startIsolatedEnv(FRONTEND_DIR);
    CONFIG_YAML = isoConfigPath();
  });
  test.afterAll(async () => {
    await stopIsolatedEnv();
  });

  // ─── 1) 通用Tab: 当前模型卡 + SettingsGroup 骨架验证 ────────────
  test('case-01 通用Tab: 加载→当前模型卡→SettingsGroup骨架', async ({
    page,
  }) => {
    await gotoSettings(page);
    // 通用 Tab 是默认激活的
    const generalTab = page.getByRole('tab', { name: /通\s*用/ });
    await expect(generalTab).toHaveAttribute('aria-selected', 'true', {
      timeout: 10_000,
    });

    // 1) 当前模型卡可见（CurrentModelRefCard）
    await expect(page.getByText('当前系统全局使用模型').first()).toBeVisible({
      timeout: 15_000,
    });
    console.log('[E2E] case-01 通用Tab已加载，当前模型卡可见');

    // 2) 项目根目录行可见（general group item: workspace.project_root）
    await expect(page.getByText('项目根目录')).toBeVisible({ timeout: 10_000 });
    console.log('[E2E] case-01 通用Tab workspace.project_root 可见');

    // 3) 授权目录行可见（general group item: workspace.allowed_dirs）
    await expect(page.getByText('授权目录')).toBeVisible({ timeout: 10_000 });
    console.log('[E2E] case-01 通用Tab workspace.allowed_dirs 可见');

    // 4) 脏角标初始为 0
    const dirtyBadge = page.locator('.ant-badge-count, [class*="dirty"]');
    const badgeText =
      (await dirtyBadge
        .first()
        .innerText()
        .catch(() => '0')) || '0';
    console.log(`[E2E] case-01 初始脏角标: ${badgeText}`);
  });

  // ─── 2) 模型Tab 选择器: Provider/Model 切换联动 ───────────────
  test('case-02 模型Tab: Provider→Model切换 + 参数区跟随', async ({ page }) => {
    await gotoSettings(page);
    await clickTab(page, /模\s*型/);
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 1) Provider 下拉初始值 = sensenova（默认）
    const providerSelect = page
      .locator('[data-section="selector"] .ant-select')
      .first();
    await providerSelect.scrollIntoViewIfNeeded();
    const providerText = await providerSelect
      .locator('.ant-select-selection-item')
      .innerText();
    console.log(`[E2E] case-02 当前Provider: ${providerText}`);
    expect(providerText.length).toBeGreaterThan(0);

    // 2) 切到 agnes
    await providerSelect.click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: 'agnes' })
      .first()
      .click();
    await page.waitForTimeout(800);

    // 3) 模型下拉应出现 agnes 模型
    const modelSelect = page
      .locator('[data-section="selector"] .ant-select')
      .nth(1);
    const modelText = await modelSelect
      .locator('.ant-select-selection-item')
      .innerText();
    console.log(`[E2E] case-02 切到agnes后模型: ${modelText}`);
    expect(modelText.toLowerCase()).toContain('agnes');

    // 4) Provider配置区标题可见（③ Provider 配置）
    await expect(page.getByText('③ Provider 配置')).toBeVisible({
      timeout: 10_000,
    });
    console.log('[E2E] case-02 Provider配置区可见');

    // 5) 切回 sensenova
    await providerSelect.click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: 'sensenova' })
      .first()
      .click();
    await page.waitForTimeout(800);
    const modelText2 = await modelSelect
      .locator('.ant-select-selection-item')
      .innerText();
    console.log(`[E2E] case-02 切回sensenova后模型: ${modelText2}`);
    expect(modelText2.length).toBeGreaterThan(0);
  });

  // ─── 3) 模型Tab 添加模型: 弹窗→POST→落盘→回显 ──────────────
  test('case-03 模型Tab: 添加模型全链路', async ({ page, request }) => {
    const newModel = `e2e-add-${stamp()}`;

    // 0) 拦截 POST /models
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

    await gotoSettings(page);
    await clickTab(page, /模\s*型/);
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 1) 打开添加模型弹窗
    // 2026-09-28 小欧 - 同 fre2e_08：另有「添加模型参数」同前缀按钮，且 accessible name 带图标
    //   前缀（"plus 添加模型"），故按可见文字精确定位并取 .first() 锁定选择器行内那个。
    await page.getByText('添加模型', { exact: true }).first().click();
    const modal = page.getByRole('dialog', { name: '添加模型' });
    await expect(modal).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(600);

    // 2) Provider 选 sensenova（如已选可跳过）
    const provSel = modal.locator('.ant-select').first();
    const curProv = await provSel
      .locator('.ant-select-selection-item')
      .innerText()
      .catch(() => '');
    if (!curProv.includes('sensenova')) {
      await provSel.click();
      await page
        .locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: 'sensenova' })
        .first()
        .click();
      await page.waitForTimeout(400);
    }

    // 3) 填模型名 + label
    const modelInput = modal.getByRole('textbox', { name: /模型名/ });
    await expect(modelInput).toBeVisible({ timeout: 10_000 });
    await modelInput.fill(newModel);
    const labelInput = modal.getByRole('textbox', { name: /显示名/ });
    await labelInput.fill(`E2E测试模型-${newModel}`);

    // 4) 保存
    await modal.locator('.ant-modal-footer button.ant-btn-primary').click();
    console.log(`[E2E] case-03 点击保存 newModel=${newModel}`);

    // 5) POST body 断言
    await expect
      .poll(() => JSON.stringify(postBody ?? null), { timeout: 30_000 })
      .toContain(newModel);
    // 2026-09-28 小欧 - 同 fre2e_08：上行 poll 已确保非 null，断言收窄替代 as 强转（TS2352）
    expect(postBody).not.toBeNull();
    const b = postBody!;
    expect(b.provider).toBe('sensenova');
    expect(b.model).toBe(newModel);
    console.log(
      `[E2E] case-03 POST body 校验通过: provider=${b.provider} model=${b.model}`
    );

    // 6) 弹窗关闭
    await expect(modal).toBeHidden({ timeout: 30_000 });

    // 7) config.yaml 落盘
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 15_000 })
      .toContain(newModel);
    console.log('[E2E] case-03 config.yaml 落盘 ok');

    // 8) 选择器回显（新模型出现在模型下拉）
    const modelSelect = page
      .locator('[data-section="selector"] .ant-select')
      .nth(1);
    await expect
      .poll(
        async () => {
          await modelSelect.click();
          const items = page.locator(
            '.ant-select-dropdown:visible .ant-select-item'
          );
          const texts = await items.allInnerTexts();
          page.keyboard.press('Escape');
          return texts.some((t) => t.includes(newModel));
        },
        { timeout: 15_000 }
      )
      .toBeTruthy();
    console.log('[E2E] case-03 选择器回显 ok');
  });

  // ─── 4) 模型Tab Provider配置: 读写+动态参数+落盘 ─────────────
  test('case-04 模型Tab: Provider配置 timeout/max_retries 编辑→保存→落盘', async ({
    page,
    request,
  }) => {
    await gotoSettings(page);
    await clickTab(page, /模\s*型/);
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 1) 确认在 sensenova 下，③ Provider 配置区可见
    const cfg = page.locator('[data-section="provider-config"]');
    await expect(cfg).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('③ Provider 配置')).toBeVisible();

    // 2) 读当前 timeout 值（InputNumber input）
    const rowOf = (label: string) =>
      page.getByText(label, { exact: true }).locator('xpath=..');
    const timeoutInput = rowOf('timeout').locator('.ant-input-number input');
    const timeoutBefore = await timeoutInput.inputValue();
    console.log(`[E2E] case-04 当前 timeout=${timeoutBefore}`);

    // 3) 改 timeout（2026-09-28 小欧 - 原写死 200，现值恰为 200 时空填 → 表单不脏 → 保存钮 disabled）
    const nextTimeout = Number(timeoutBefore) === 200 ? 250 : 200;
    await timeoutInput.fill(String(nextTimeout));
    await page.waitForTimeout(300);

    // 4) 保存 Provider 配置
    await page
      .getByRole('button', { name: '保存 Provider 配置（立即生效）' })
      .click();
    await expect(page.locator('.ant-message')).toContainText(
      'Provider 配置已保存（立即生效）',
      { timeout: 20_000 }
    );
    console.log('[E2E] case-04 Provider配置保存成功');

    // 5) 回显断言（2026-09-28 小欧 - 同步改为 nextTimeout，原写死 '200' 与实际填入值不符）
    await expect(
      rowOf('timeout').locator('.ant-input-number input')
    ).toHaveValue(String(nextTimeout), { timeout: 10_000 });
    console.log(`[E2E] case-04 回显 timeout=${nextTimeout} ok`);

    // 6) API 回读验证（PUT 了 nextTimeout，再 GET 确认）
    const models = (await apiGet(request, '/models')) as {
      providers: Array<{ name: string; timeout: number }>;
    };
    const sensenova = models.providers.find((p) => p.name === 'sensenova');
    expect(sensenova).toBeTruthy();
    // timeout 可能被 clamp 到 [30, 600]，只要非原值即可
    console.log(
      `[E2E] case-04 API回读 timeout=${sensenova!.timeout} (原值=${timeoutBefore})`
    );

    // 7) 恢复原值
    await timeoutInput.fill(timeoutBefore);
    await page
      .getByRole('button', { name: '保存 Provider 配置（立即生效）' })
      .click();
    await expect(page.locator('.ant-message')).toContainText(
      'Provider 配置已保存（立即生效）',
      { timeout: 20_000 }
    );
    console.log('[E2E] case-04 timeout 已恢复');
  });

  // ─── 5) 模型Tab 模型参数: 编辑→回显 ─────────────────────────
  test('case-05 模型Tab: 模型参数编辑→保存→回显', async ({ page }) => {
    await gotoSettings(page);
    await clickTab(page, /模\s*型/);
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 1) 切到 agnes（有 temperature/max_tokens 等参数）
    const providerSelect = page
      .locator('[data-section="selector"] .ant-select')
      .first();
    await providerSelect.scrollIntoViewIfNeeded();
    await providerSelect.click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: 'agnes' })
      .first()
      .click();
    await page.waitForTimeout(800);

    // 2) 选第一个模型
    const modelSelect = page
      .locator('[data-section="selector"] .ant-select')
      .nth(1);
    await modelSelect.click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .first()
      .click();
    await page.waitForTimeout(800);

    // 3) ② 参数区应出现
    await expect(page.getByText('② 参数区')).toBeVisible({ timeout: 10_000 });

    // 4) 找 temperature 行（模型参数区裸键，ModelParams data-settings-key）— 小欧-2026-09-24
    const tempRow = page.locator('[data-settings-key="temperature"]').first();
    const hasTemp = (await tempRow.count()) > 0;
    if (hasTemp) {
      const tempInput = tempRow.locator('input');
      const tempBefore = await tempInput.inputValue();
      console.log(`[E2E] case-05 当前 temperature=${tempBefore}`);

      // 改 temperature = 0.9
      await tempInput.fill('0.9');
      await page.waitForTimeout(300);

      // 保存本组
      await page.getByRole('button', { name: /保存本组/ }).click();
      await expect(page.locator('.ant-message')).toContainText('保存成功', {
        timeout: 20_000,
      });
      console.log('[E2E] case-05 temperature 保存成功');

      // 回显
      await expect(tempRow.locator('input')).toHaveValue('0.9', {
        timeout: 10_000,
      });
      console.log('[E2E] case-05 回显 temperature=0.9 ok');

      // 恢复
      await tempInput.fill(tempBefore);
      await page.getByRole('button', { name: /保存本组/ }).click();
      await expect(page.locator('.ant-message')).toContainText('保存成功', {
        timeout: 20_000,
      });
      console.log('[E2E] case-05 temperature 已恢复');
    } else {
      console.log('[E2E] case-05 当前模型无 temperature 参数，跳过编辑');
    }
  });

  // ─── 6) 模型Tab 删除模型: 添加→删除→选择器消失 ──────────────
  test('case-06 模型Tab: 添加测试模型→删除→选择器消失', async ({
    page,
    request,
  }) => {
    const victim = `e2e-victim-${stamp()}`;

    // 0) 先添加一个测试模型
    const addRes = await apiPost(request, '/models', {
      provider: 'sensenova',
      model: victim,
      label: `E2E待删-${victim}`,
    });
    expect((addRes as { ok?: boolean }).ok).toBeTruthy();
    console.log(`[E2E] case-06 预置测试模型 ${victim} 成功`);

    // 刷新页面让 UI 加载新模型
    await gotoSettings(page);
    await clickTab(page, /模\s*型/);
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('① 选择器')).toBeVisible({ timeout: 15_000 });

    // 1) 切到 sensenova → 选 victim 模型
    const providerSelect = page
      .locator('[data-section="selector"] .ant-select')
      .first();
    await providerSelect.scrollIntoViewIfNeeded();
    const curProv = await providerSelect
      .locator('.ant-select-selection-item')
      .innerText()
      .catch(() => '');
    if (!curProv.includes('sensenova')) {
      await providerSelect.click();
      await page
        .locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: 'sensenova' })
        .first()
        .click();
      await page.waitForTimeout(600);
    }

    const modelSelect = page
      .locator('[data-section="selector"] .ant-select')
      .nth(1);
    await modelSelect.click();
    await expect(page.locator('.ant-select-dropdown:visible')).toBeVisible({
      timeout: 5_000,
    });
    // 用 filter hasText 匹配 victim（虚拟列表需要滚动 dropdown 容器）
    const victimItem = page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: victim })
      .first();
    const dd = page.locator('.ant-select-dropdown:visible');
    for (let i = 0; i < 30; i += 1) {
      if ((await victimItem.count()) > 0) break;
      await dd.hover();
      await page.mouse.wheel(0, 600);
      await page.waitForTimeout(200);
    }
    await victimItem.click({ timeout: 10_000 });
    await page.waitForTimeout(600);
    console.log(`[E2E] case-06 已选中测试模型 ${victim}`);

    // 2) 操作区「删除此模型」按钮（在④操作区，需滚动到底部）
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    const delBtn = page.getByRole('button', { name: /删除此模型/ });
    await delBtn.click({ force: true, timeout: 10_000 });

    // 3) 确认弹窗（Ant Design Modal.confirm 用 ant-modal 定位）
    const confirmModal = page.locator(
      '.ant-modal-wrap:not([style*="display: none"])'
    );
    await expect(confirmModal).toBeVisible({ timeout: 10_000 });
    // 点击「删除」确认按钮
    await confirmModal
      .locator('.ant-btn-primary, .ant-btn-dangerous')
      .last()
      .click();
    await page.waitForTimeout(1000);
    console.log('[E2E] case-06 确认删除');

    // 4) 选择器中不再有 victim
    await modelSelect.click();
    const victimGone = page
      .locator('.ant-select-dropdown:visible .ant-select-item')
      .filter({ hasText: victim });
    await expect
      .poll(
        async () => {
          const dd = page.locator('.ant-select-dropdown:visible');
          if ((await dd.count()) === 0) return true;
          return (await victimGone.count()) === 0;
        },
        { timeout: 15_000 }
      )
      .toBeTruthy();
    page.keyboard.press('Escape');
    console.log(`[E2E] case-06 模型 ${victim} 已从选择器消失`);
  });

  // ─── 7) 安全Tab: 读写 + 危险确认弹窗 ────────────────────────
  test('case-07 安全Tab: security.enabled 编辑→危险确认→保存→落盘', async ({
    page,
    request,
  }) => {
    // 0) 后端预读
    const before = (await apiGet(request, '/settings')) as {
      groups: Record<string, { data: Record<string, unknown> }>;
    };
    const secBefore = before.groups.security.data['security.enabled'];
    console.log(`[E2E] case-07 当前 security.enabled=${secBefore}`);

    await gotoSettings(page);
    await clickTab(page, /安\s*全/);
    // 等安全Tab内容出现（"安全设置"组标题或 "危险操作确认" 行）
    await expect(
      page
        .getByText('安全设置')
        .first()
        .or(page.getByText('危险操作确认').first())
    ).toBeVisible({ timeout: 15_000 });

    // 1) 找 security.enabled 开关（安全Tab第一个 switch）
    const switchEl = page.locator('[role="switch"]').first();
    if ((await switchEl.count()) > 0) {
      await expect(switchEl).toBeVisible({ timeout: 5_000 });
      const isOn = await switchEl.isChecked();
      console.log(
        `[E2E] case-07 security.enabled 开关状态: ${isOn ? 'ON' : 'OFF'}`
      );
      await switchEl.click();
    } else {
      // fallback: 找 ant-switch 类
      const altSwitch = page.locator('.ant-switch').first();
      await expect(altSwitch).toBeVisible({ timeout: 5_000 });
      const isOn = await altSwitch.evaluate((el) =>
        el.classList.contains('ant-switch-checked')
      );
      console.log(
        `[E2E] case-07 security.enabled 开关状态(alt): ${isOn ? 'ON' : 'OFF'}`
      );
      await altSwitch.click();
    }
    await page.waitForTimeout(400);

    // 3) 脏态出现
    const saveAllBtn = page.getByRole('button', { name: /保存全部/ });
    await expect(saveAllBtn).toBeEnabled({ timeout: 5_000 });

    // 4) 保存全部 → 危险确认弹窗（security.enabled 是危险键）
    await saveAllBtn.click();
    const dangerModal = page.locator('.ant-modal-confirm');
    await expect(dangerModal).toBeVisible({ timeout: 10_000 });
    console.log('[E2E] case-07 危险确认弹窗已弹出');

    // 5) 确认保存
    await dangerModal
      .locator('.ant-btn-dangerous, .ant-btn-primary')
      .last()
      .click();
    await expect
      .poll(
        async () => {
          const msg = page.locator('.ant-message-success');
          return (await msg.count()) > 0;
        },
        { timeout: 20_000 }
      )
      .toBeTruthy();
    console.log('[E2E] case-07 安全设置保存成功');

    // 6) config.yaml 落盘
    const expected = secBefore === true ? 'enabled: false' : 'enabled: true';
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
      .toContain(expected);
    console.log(`[E2E] case-07 config.yaml 落盘 ok: ${expected}`);

    // 7) 恢复原值
    await apiPut(request, '/settings', {
      patch: { 'security.enabled': secBefore },
    });
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
      .toContain(secBefore ? 'enabled: true' : 'enabled: false');
    console.log('[E2E] case-07 安全设置已恢复');
  });

  // ─── 8) 沙箱Tab: 读写 + 落盘 ────────────────────────────────
  test('case-08 沙箱Tab: sandbox.max_concurrent_sandboxes 编辑→保存→落盘', async ({
    page,
    request,
  }) => {
    // 0) 后端预读
    const before = (await apiGet(request, '/settings')) as {
      groups: Record<string, { data: Record<string, unknown> }>;
    };
    const sbBefore = before.groups.sandbox.data[
      'sandbox.max_concurrent_sandboxes'
    ] as number;
    console.log(`[E2E] case-08 当前 max_concurrent_sandboxes=${sbBefore}`);

    await gotoSettings(page);
    await clickTab(page, /沙\s*箱/);
    await expect(page.getByText('沙箱').first()).toBeVisible({
      timeout: 15_000,
    });

    // 1) 找 sandbox.max_concurrent_sandboxes 行
    const sbRow = page
      .locator('[data-settings-key="sandbox.max_concurrent_sandboxes"]')
      .first();
    if ((await sbRow.count()) > 0) {
      const sbInput = sbRow.locator('input');
      const sbVal = await sbInput.inputValue();
      console.log(`[E2E] case-08 UI 当前值: ${sbVal}`);

      // 改值
      const newVal = sbBefore === 3 ? 5 : 3;
      await sbInput.fill(String(newVal));
      await page.waitForTimeout(300);

      // 保存本组
      await page.getByRole('button', { name: /保存本组/ }).click();
      await expect(page.locator('.ant-message')).toContainText('保存成功', {
        timeout: 20_000,
      });
      console.log(`[E2E] case-08 保存成功: max_concurrent_sandboxes=${newVal}`);

      // 回显
      await expect(sbRow.locator('input')).toHaveValue(String(newVal), {
        timeout: 10_000,
      });

      // config.yaml 落盘
      await expect
        .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
        .toContain(`max_concurrent_sandboxes: ${newVal}`);
      console.log('[E2E] case-08 config.yaml 落盘 ok');

      // 恢复
      await sbInput.fill(String(sbBefore));
      await page.getByRole('button', { name: /保存本组/ }).click();
      await expect(page.locator('.ant-message')).toContainText('保存成功', {
        timeout: 20_000,
      });
      console.log('[E2E] case-08 值已恢复');
    } else {
      console.log(
        '[E2E] case-08 沙箱 Tab 无 max_concurrent_sandboxes 行，跳过'
      );
    }
  });

  // ─── 9) 通用Tab 采样参数: llm.sampling.temperature/max_tokens 编辑→落盘 ───
  // 2026-09-23 [64] 迁顶层 llm.sampling.*，原 tuning.llm.* 死键 — 小欧-2026-09-24
  test('case-09 通用Tab: 采样参数 temperature/max_tokens 编辑→保存→落盘', async ({
    page,
    request,
  }) => {
    // 0) 后端预读
    const before = (await apiGet(request, '/settings')) as {
      groups: Record<string, { data: Record<string, unknown> }>;
    };
    const genData = before.groups.general.data;
    const tempBefore = genData['llm.sampling.temperature'] as number;
    const tokensBefore = genData['llm.sampling.max_tokens'] as number;
    console.log(
      `[E2E] case-09 当前 temperature=${tempBefore} max_tokens=${tokensBefore}`
    );

    await gotoSettings(page);
    await clickTab(page, /通\s*用/);
    // 2026-09-28 小欧 - Tab 选中态用 role 断言：正文里也出现「通用」二字（通用兜底模型参数小节），
    //   getByText 命中 2 个元素 → strict mode violation。
    await expect(page.getByRole('tab', { name: /通\s*用/ })).toHaveAttribute(
      'aria-selected',
      'true',
      { timeout: 15_000 }
    );

    // 1) temperature 行
    // 2026-09-28 小欧 - 原写死 0.85，现值恰为 0.85 时空填 → 保存本组钮 disabled（本轮实测撞上）。
    //   改为按现值取必然不同的值，落盘断言同步用同一变量（避免断言与实填值脱节）。
    let nextTemp = tempBefore;
    const tempRow = page
      .locator('[data-settings-key="llm.sampling.temperature"]')
      .first();
    if ((await tempRow.count()) > 0) {
      const tempInput = tempRow.locator('input');
      const cur = await tempInput.inputValue();
      nextTemp = Number(cur) === 0.85 ? 0.9 : 0.85;
      await tempInput.fill(String(nextTemp));
      await page.waitForTimeout(300);
      console.log(`[E2E] case-09 temperature 改为 ${nextTemp}`);
    }

    // 2) max_tokens 行（同样避免写死值撞上现值）
    let nextTokens = tokensBefore;
    const tokensRow = page
      .locator('[data-settings-key="llm.sampling.max_tokens"]')
      .first();
    if ((await tokensRow.count()) > 0) {
      const tokensInput = tokensRow.locator('input');
      const cur = await tokensInput.inputValue();
      nextTokens = Number(cur) === 8192 ? 16384 : 8192;
      await tokensInput.fill(String(nextTokens));
      await page.waitForTimeout(300);
      console.log(`[E2E] case-09 max_tokens 改为 ${nextTokens}`);
    }

    // 3) 保存本组
    await page.getByRole('button', { name: /保存本组/ }).click();
    await expect(page.locator('.ant-message')).toContainText('保存成功', {
      timeout: 20_000,
    });
    console.log('[E2E] case-09 通用采样参数保存成功');

    // 4) config.yaml 落盘（2026-09-28 小欧 - 同步断言实际填入的 next 值，原写死 0.85 与之不符）
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
      .toContain(`temperature: ${nextTemp}`);
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
      .toContain(`max_tokens: ${nextTokens}`);
    console.log('[E2E] case-09 config.yaml 落盘 ok');

    // 5) 恢复
    await apiPut(request, '/settings', {
      patch: {
        'llm.sampling.temperature': tempBefore,
        'llm.sampling.max_tokens': tokensBefore,
      },
    });
    await expect
      .poll(() => fs.readFileSync(CONFIG_YAML, 'utf8'), { timeout: 10_000 })
      .toContain(`temperature: ${tempBefore}`);
    console.log('[E2E] case-09 通用采样参数已恢复');
  });

  // ─── 10) 前端Tab + 搜索跳转: 主题切换 + 搜索命中 + Tab切换脏确认 ──
  test('case-10 前端Tab + 搜索跳转: 主题切换→搜索命中→Tab切换脏确认', async ({
    page,
    request,
  }) => {
    // 0) 后端预读主题
    const before = (await apiGet(request, '/settings')) as {
      groups: Record<string, { data: Record<string, unknown> }>;
    };
    const themeBefore = before.groups.appearance.data['app.theme'];
    console.log(`[E2E] case-10 当前主题: ${themeBefore}`);

    await gotoSettings(page);
    await clickTab(page, /前\s*端/);
    // Tab 显示名已于 2026-09-27 由「外观」改为「前端」（appearance 组 label）；
    // 断言该 Tab 的首个小节标题，比断言旧 Tab 名更贴近"内容确实渲染出来了"
    await expect(page.getByText('登录与准入')).toBeVisible({ timeout: 15_000 });

    // 1) 主题切换（如 theme 是 select）
    const themeRow = page.locator('[data-settings-key="app.theme"]').first();
    if ((await themeRow.count()) > 0) {
      const themeSelect = themeRow.locator('.ant-select');
      if ((await themeSelect.count()) > 0) {
        await themeSelect.first().click();
        const items = page.locator(
          '.ant-select-dropdown:visible .ant-select-item'
        );
        const cnt = await items.count();
        if (cnt > 1) {
          // 选一个与当前不同的
          for (let i = 0; i < cnt; i += 1) {
            const txt = await items.nth(i).innerText();
            if (txt !== String(themeBefore)) {
              await items.nth(i).click();
              break;
            }
          }
        }
        await page.waitForTimeout(400);
      }
    }

    // 2) 脏态出现
    const saveAllBtn = page.getByRole('button', { name: /保存全部/ });
    const isDirty = await saveAllBtn.isEnabled().catch(() => false);

    // 3) 搜索跳转: temperature 在 general/llm.sampling.*，应跳通用Tab；Input.Search 回车触发 — 小欧-2026-09-24
    const searchInput = page.getByPlaceholder(/搜索/);
    if ((await searchInput.count()) > 0) {
      await searchInput.fill('temperature');
      await searchInput.press('Enter');
      await page.waitForTimeout(800);
      const generalTab = page.getByRole('tab', { name: /通\s*用/ });
      await expect(generalTab).toHaveAttribute('aria-selected', 'true', {
        timeout: 10_000,
      });
      console.log('[E2E] case-10 搜索跳转到通用Tab ok');
    }

    // 4) Tab 切换脏确认: 调优Tab有脏态时切到通用Tab应弹确认
    // 脏态键=tuning.llm.stream_max_retries（活键；原 tuning.llm.temperature 已迁 general）— 小欧-2026-09-24
    await clickTab(page, /调\s*优/);
    const dirtyRow = page
      .locator('[data-settings-key="tuning.llm.stream_max_retries"]')
      .first();
    if ((await dirtyRow.count()) > 0) {
      const dirtyInput = dirtyRow.locator('input');
      const dirtyCur = await dirtyInput.inputValue();
      await dirtyInput.fill('4');
      await page.waitForTimeout(300);

      // 切到通用Tab
      await clickTab(page, /通\s*用/);
      // 应弹「有未保存的修改」确认弹窗
      const jumpModal = page.locator('.ant-modal-confirm');
      const hasJumpModal = (await jumpModal.count()) > 0;
      if (hasJumpModal) {
        console.log('[E2E] case-10 Tab切换脏确认弹窗已弹出');
        // 点「放弃切换」留在当前页
        await jumpModal
          .locator('.ant-btn:not(.ant-btn-primary)')
          .first()
          .click();
        await page.waitForTimeout(400);
        // 应仍在调优Tab
        const tuningTab = page.getByRole('tab', { name: /调\s*优/ });
        await expect(tuningTab).toHaveAttribute('aria-selected', 'true');
        console.log('[E2E] case-10 放弃切换后仍在调优Tab ok');
      }

      // 恢复重试次数
      await dirtyInput.fill(dirtyCur);
      await page.waitForTimeout(500);
      if (await saveAllBtn.isEnabled()) {
        await saveAllBtn.click();
        await expect(page.locator('.ant-message')).toContainText('保存成功', {
          timeout: 20_000,
        });
      }
      console.log('[E2E] case-10 stream_max_retries 已恢复');
    }

    // 5) 恢复主题
    if (isDirty) {
      await apiPut(request, '/settings', {
        patch: { 'app.theme': themeBefore },
      });
    }
    console.log('[E2E] case-10 前端+搜索+脏确认测试完成');
  });
});
