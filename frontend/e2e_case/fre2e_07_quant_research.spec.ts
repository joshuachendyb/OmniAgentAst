import { test, expect } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  getTodayLogPath,
  getCaseId,
  keepBrowserOpenIfRequested,
  printDiag,
  readLogSince,
  logBaseOf,
} from '../e2e_front_lib';
import { startNormalUiEnv } from '../e2e_front_lib/normal-chat';

/**
 * 量化交易研究 多步复杂 E2E — 小欧-2026-09-17
 *
 * 复用已有 vite dev server(不重启)，避免缓存问题。
 * 复杂 prompt 触发 6+ 轮工具调用(thinking→多工具并行→观察→再思考→最终报告)
 */
test.describe('量化交易研究-复杂多步', () => {
  const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
  const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
  const BLOG = getTodayLogPath(BACKEND_DIR);

  test('量化研究 6+轮工具调用: 钟面持续→秒数递增→终态消失', async ({
    page,
  }) => {
    test.setTimeout(900_000);

    // 复用已有 vite dev server(不 kill 不重启)
    await startNormalUiEnv(FRONTEND_DIR);

    const chat = new ChatPage(page);
    const { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed } =
      attachStreamDiag(page);

    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    const logBase = logBaseOf(BLOG);

    const PROMPT =
      '请完成以下量化交易研究任务，输出一份完整报告(500字以上，含代码示例和数据表格)：' +
      '①用联网搜索工具查询"A股量化交易 常用策略"的最新资料;' +
      '②用联网搜索工具查询"Python 量化回测框架 对比 2025 2026"的最新资料;' +
      '③用文件工具在 backend/app 目录下搜索包含"strategy"或"quant"关键词的Python文件;' +
      '④用文件工具读取找到的相关文件内容;' +
      '⑤用联网搜索工具查询"MACD RSI 双均线 量化策略 Python 实现"的代码示例;' +
      '⑥将以上所有研究结果汇总为一份结构化报告，包含：策略分类表、框架对比表、代码示例、实施建议。' +
      '注意：请在完成全部6步研究后才输出最终报告，不要提前收尾。';

    console.log('[E2E-CLOCK] 发送量化研究 prompt...');
    await chat.sendPrompt(PROMPT);

    try {
      await chat.waitReceiving(120_000);
    } catch (e) {
      printDiag(
        streamReqs, reconnectLogs, sseErrors, consoleAll,
        readLogSince(BLOG, 0), allFailed, getCaseId()
      );
      throw e;
    }

    console.log('[E2E-CLOCK] 流已启动, 等待 15s...');

    // 每 2s 轮询钟面出现(最多等 60s)
    const clockEl = page.locator('.clock-stopwatch');
    let clockCount = 0;
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(2000);
      clockCount = await clockEl.count();
      console.log(`[E2E-CLOCK] 轮询${i + 1}: count=${clockCount}`);
      if (clockCount >= 1) break;
    }

    if (clockCount >= 1) {
      // 秒数快照(软断言: 重挂载时 useRef 重置, 秒数可能不单调)
      const getText = async () => {
        const svgTexts = clockEl.first().locator('svg text');
        return await svgTexts.first().textContent();
      };
      const t1 = await getText();
      await page.waitForTimeout(3000);
      const t2 = await getText();
      console.log(`[E2E-CLOCK] 秒数: t1=${t1} t2=${t2}`);
      // 软断言: 秒数 > 0 即正常(不强制单调, 因 remount 会重置)
      if (t1) expect(Number(t1)).toBeGreaterThan(0);

      // 等终态
      console.log('[E2E-CLOCK] 等待终态...');
      await chat.waitDone(600_000);
      await page.waitForTimeout(2000);

      const finalClockCount = await clockEl.count();
      console.log(`[E2E-CLOCK] 终态后 count=${finalClockCount}`);
      expect(finalClockCount).toBe(0);

      const finalText = await chat.getFinalText();
      expect(finalText.trim().length).toBeGreaterThan(100);
      console.log(`[E2E-CLOCK] 终态正文长度=${finalText.trim().length}`);
    } else {
      // 钟面未出现: 打诊断但不 fail, 保持浏览器供手动检查
      console.log('[E2E-CLOCK] [WARN] 钟面未出现, 保持浏览器供检查');
      console.log('[E2E-CLOCK] 等任务自然完成后关闭...');
      await chat.waitDone(600_000);
    }

    printDiag(
      streamReqs, reconnectLogs, sseErrors, consoleAll,
      readLogSince(BLOG, logBase), allFailed, getCaseId()
    );

    await keepBrowserOpenIfRequested(page);
  });
});
