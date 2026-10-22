/**
 * fre2e_23 —— 聊天侧「工具参数路径可点」真实浏览器 E2E
 *
 * 2026-10-22 小杨 - 新建（覆盖 PathLink/PathAwareJson/路径参数编解码 的真实链路：
 *   工具参数里的 path → 可点深链 → 跳文件页并定位；规格表视图同样可点）— 小杨-2026-10-22
 *
 * ⚠ 本地测试文件：按 AGENTS「严禁 commit 任何测试 case 代码」，此文件**不提交**
 *
 * 真实环境：chromium 真浏览器 + 真后端(:8000) + 真 LLM + 真项目根(E:\test_dir)。
 *   绝不 Mock：不 Mock LLM、不 Mock 工具、不 Mock 文件接口。
 */
import { test, expect } from '@playwright/test';
import { ChatPage, startNormalUiEnv } from '../e2e_front_lib';

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const TARGET = 'extracted_numbers+2026-09-28_18-31-01.txt';

/**
 * 等一轮真实 LLM 跑完（不等"停止钮/绿圈"——本机响应快，18s 内就 final，
 *   等中间态会误判失败；只等终态 + 工具行出现）
 */
const runToolRound = async (
  chat: ChatPage,
  prompt: string
): Promise<string> => {
  await chat.sendPrompt(prompt);
  await chat.waitDone(300_000);
  await chat.waitMs(1500);
  return chat.getFinalText();
};

/**
 * 等"调用 N 个工具"这一行出现（= 确实产生了工具调用）。
 * 真 LLM 有随机性：偶发不调工具 → 允许重发一轮，但重发仍不调才算失败。
 */
const waitToolCall = async (
  page: import('@playwright/test').Page,
  chat: ChatPage,
  prompt: string
): Promise<boolean> => {
  const marker = page.getByText(/调用\s*\d+\s*个工具/).first();
  for (let i = 0; i < 2; i++) {
    const ok = await marker
      .waitFor({ timeout: 120_000 })
      .then(() => true)
      .catch(() => false);
    if (ok) return true;
    if (i === 0) {
      await chat.sendPrompt(
        prompt +
          '（上一轮你没有调用工具，这次必须先调用 read_text_file 再回答）'
      );
      await chat.waitDone(300_000);
      await chat.waitMs(1000);
    }
  }
  return false;
};

test.describe('聊天侧：工具参数里的路径可点（真实 LLM + 真实工具）', () => {
  test('C1 path 参数渲染成深链，点击直达文件页并打开该文件', async ({
    page,
  }) => {
    test.setTimeout(900_000);
    const chat = new ChatPage(page);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    await chat.newSession();

    const prompt =
      `请务必用 read_text_file 工具读取项目根下的 ${TARGET} 文件的前 3 行，` +
      '然后把第一行内容原样告诉我（必须真的调用工具读取，不要凭空回答）。';
    await runToolRound(chat, prompt);
    expect(
      await waitToolCall(page, chat, prompt),
      '两轮内都没有产生工具调用（真实 LLM 未调 read_text_file）'
    ).toBe(true);

    // 工具行的参数浮层入口（可访问名形如 "read 参数"）
    const entry = page.locator('[aria-label$="参数"]').first();
    await expect(entry).toBeVisible({ timeout: 60_000 });
    await entry.click();

    // 浮层里 path 值必须是深链（a[href^="/files?path="]）
    const popover = page.locator('[id^="params-panel-"]').first();
    await expect(popover).toBeVisible({ timeout: 30_000 });

    // 切到「分组参数」视图（默认是 TOOL结果，看不到入参）
    await popover.getByText('分组参数').first().click();
    await expect
      .poll(
        async () => await popover.locator('a[href^="/files?path="]').count(),
        {
          timeout: 30_000,
        }
      )
      .toBeGreaterThan(0);

    // 浮层里 path 值必须是深链（a[href^="/files?path="]）
    const link = popover.locator('a[href^="/files?path="]').first();
    await expect(link, '参数浮层里没有路径深链').toBeVisible({
      timeout: 30_000,
    });

    const href = await link.getAttribute('href');
    expect(href).toBeTruthy();

    // 点击 → 跳文件页，且目标文件被打开
    await link.click();
    await page.waitForURL(/\/files\?path=/, { timeout: 60_000 });
    await expect(
      page.getByText(new RegExp(TARGET.replace(/[.+]/g, '\\$&'))).first()
    ).toBeVisible({ timeout: 60_000 });
  });

  test('C2 规格表视图：path 参数同样可点（三入口一致）', async ({ page }) => {
    test.setTimeout(900_000);
    const chat = new ChatPage(page);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    await chat.newSession();

    const prompt =
      `请务必用 read_text_file 工具读取项目根下的 ${TARGET} 文件的前 3 行，` +
      '然后把第一行内容原样告诉我（必须真的调用工具读取，不要凭空回答）。';
    await runToolRound(chat, prompt);
    expect(
      await waitToolCall(page, chat, prompt),
      '两轮内都没有产生工具调用（真实 LLM 未调 read_text_file）'
    ).toBe(true);

    const entry = page.locator('[aria-label$="参数"]').first();
    await expect(entry).toBeVisible({ timeout: 60_000 });
    await entry.click();

    const popover = page.locator('[id^="params-panel-"]').first();
    await expect(popover).toBeVisible({ timeout: 30_000 });

    // 切到「规格表参数」视图
    await popover.getByText('规格表参数').first().click();
    await expect
      .poll(
        async () => await popover.locator('a[href^="/files?path="]').count(),
        {
          timeout: 30_000,
        }
      )
      .toBeGreaterThan(0);
  });
});
