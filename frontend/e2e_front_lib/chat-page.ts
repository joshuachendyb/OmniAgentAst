/**
 * e2e_front_lib/chat-page.ts — 聊天页页面对象（POM，前端 Playwright E2E 公用库）
 * 小欧 2026-09-13（自 reconnect-ui.spec.ts 抽取，定位器与流程保持一致）
 *
 * 后续所有 UI 用例的入口：进页/发消息/等流启/等流终/取正文。
 */
import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export class ChatPage {
  readonly input = this.page.getByPlaceholder('输入消息，Shift+Enter 换行');
  readonly sendBtn = this.page.getByRole('button', { name: '发送' });
  readonly stopBtn = this.page.getByRole('button', { name: '停止' });
  readonly greenDot = this.page.locator('span.waiting-cursor[aria-label="等待下一个思考内容"]');

  constructor(private readonly page: Page) {}

  /** 打开聊天首页 */
  async gotoChat(): Promise<void> {
    await this.page.goto('/');
  }

  /** 输入并发送一条消息（发送后 isReceiving=true，页面切"停止"按钮） */
  async sendPrompt(prompt: string): Promise<void> {
    await this.input.fill(prompt);
    await this.sendBtn.click();
  }

  /** 等流已启动："停止"按钮可见 */
  async waitReceiving(timeout = 90_000): Promise<void> {
    await expect(this.stopBtn).toBeVisible({ timeout });
  }

  /** 等绿圈（已收 thinking 帧、实质开流）；非强制，等不到仅 catch 忽略 */
  async waitGreenDot(timeout = 90_000): Promise<void> {
    await expect(this.greenDot).toBeVisible({ timeout }).catch(() => {});
  }

  /** 等流结束："发送"按钮复现（isReceiving=false，done 已处理） */
  async waitDone(timeout = 300_000): Promise<void> {
    await expect(this.sendBtn).toBeVisible({ timeout });
  }

  /** 取页面终态正文 */
  async getFinalText(): Promise<string> {
    return this.page.evaluate(() => document.body.innerText);
  }
}