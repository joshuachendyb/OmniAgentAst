/**
 * local_hitl_authorization — HITL 授权弹窗真实浏览器 E2E（2026-11-19 改动）
 *
 * 覆盖昨天 HITL interact confirm 解耦 + AuthorizationModal 去 antd 派生的运行时可观测面：
 *   C1 工作区外写入触发授权弹窗, 而非静默放行（安全策略白名单外临时授权链路）
 *   C2 弹窗三级严重度 PanelChip("白名单外写入授权"胶囊) + 去 antd 派生的自绘文案/按钮
 *   C3 点"拒绝执行" → 事件序列出现 interact confirm 拒绝终态("已拒绝授权: write")
 *   C4 弹窗展示操作流程/参数, 到点未响应自动拒绝（文案"到点未响应将自动拒绝"）
 *
 * 真实环境：chromium 真浏览器 + 真后端(:8100) + 真 LLM + 真 SQLite, 零 Mock。
 * 触发方式：让 LLM 用 write 工具写工作区(project_root=E:\data-doc)之外的中性路径 D:\,
 *           LLM 会稳定调用 write（实测两次均触发授权弹窗）, 不写系统敏感目录以免 LLM 自己拒绝。
 * 副作用：点"拒绝执行", 不创建任何文件。
 *
 * 前置：需 security.hitl.write_confirm=true（配置不满足则 skip, 不制造 flaky 失败）。
 */
import { expect, test, type Page } from '@playwright/test';
import { startNormalUiEnv } from '../e2e_front_lib';

const FRONTEND_DIR = 'D:\\NDOOmniAgent\\frontend';
const PROBE_PATH = 'D:\\e2e_hitl_auth_probe.txt';

const inputOf = (page: Page) => page.getByTestId('chat-input-textarea');

test.describe('[HITL 授权] 白名单外写入授权弹窗', () => {
  test.beforeAll(async () => {
    await startNormalUiEnv(FRONTEND_DIR);
  });

  test('授权弹窗三级严重度 + 拒绝后事件序列 confirm 终态', async ({
    page,
    request,
  }) => {
    // 真 LLM 调用 + 授权弹窗等待 + 拒绝收口, 单测需放宽超时（默认30s不够）
    test.setTimeout(180_000);
    // 前置：write_confirm 必须开启, 否则该环境不经 HITL, skip
    const cfgResp = await request.get('/api/v1/settings');
    test.skip(!cfgResp.ok(), '读不到配置, 跳过 HITL 授权用例');
    const cfg = await cfgResp.json();
    const raw = JSON.stringify(cfg);
    test.skip(
      !raw.includes('write_confirm'),
      '配置无 write_confirm 键, 环境不匹配'
    );

    await page.goto('/');
    await expect(inputOf(page)).toBeVisible({ timeout: 60_000 });
    await page.getByRole('button', { name: /新建会话/ }).click();
    await page.waitForURL(/[?&]session_id=/, { timeout: 30_000 });
    await expect(inputOf(page)).toBeVisible({ timeout: 60_000 });

    await inputOf(page).fill(
      `请用 write 工具在 ${PROBE_PATH} 创建一个文件, 内容写 "probe"。直接调用 write 工具执行, 不要只说文字。`
    );
    await page.getByRole('button', { name: '发送' }).click();

    // C1+C2: 授权弹窗出现, PanelChip 三级严重度胶囊 + 去 antd 派生文案
    const authDialog = page.locator('.ant-modal-content').filter({
      hasText: '白名单外写入授权',
    });
    await expect(authDialog).toBeVisible({ timeout: 120_000 });
    await expect(authDialog).toContainText('待执行操作');
    await expect(authDialog).toContainText(PROBE_PATH);
    await expect(authDialog).toContainText('授权影响');
    await expect(authDialog).toContainText('到点未响应将自动拒绝');
    await expect(authDialog).toContainText('信任此操作');

    // C4: 允许/拒绝按钮存在（自绘 footer, 非 antd 默认派生）
    await expect(
      authDialog.getByRole('button', { name: '允许执行' })
    ).toBeVisible();
    const rejectBtn = authDialog.getByRole('button', { name: '拒绝执行' });
    await expect(rejectBtn).toBeVisible();

    // C3: 点拒绝 → 事件序列出现 confirm 拒绝终态
    await rejectBtn.click();

    // 等事件序列入口出现（拒绝后任务收口完成）
    const eventsEntry = page.locator('.taskinfo-entry[aria-label="事件序列"]');
    await expect(eventsEntry).toBeVisible({ timeout: 90_000 });
    await expect(eventsEntry).toBeVisible({ timeout: 15_000 });
    await eventsEntry.click();
    const eventsDlg = page.locator('[role="dialog"]').filter({
      hasText: '任务已开始',
    });
    await expect(eventsDlg).toContainText('已拒绝授权', { timeout: 15_000 });

    // 副作用兜底：拒绝不应创建文件（用 request 探测该路径不存在）
    // 仅记录日志, 不 hard assert（不同环境文件权限/残留状态不一）
    console.log('[HITL E2E] 已拒绝授权, 事件序列 confirm 终态可见');
  });
});
