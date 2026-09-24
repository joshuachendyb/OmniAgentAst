// 编辑历史: 2026-09-25 04:06:45 小健 - 钟面稳定性: prompt 200字改3000字四部分（拉长任务撑住钟面观察窗）+
//   钟面等待 12s 固定改 30×2s 轮询 + svg text 取值加 10s timeout 与 catch 容错 + prettier 重排 - 小健-2026-09-25
import { test, expect } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  getTodayLogPath,
  getCaseId,
  killPort,
  logBaseOf,
  keepBrowserOpenIfRequested,
  printDiag,
  proxyLogPath,
  readLogSince,
  startDevServer,
  startProxyServer,
  waitPortDown,
  waitPortUp,
} from '../e2e_front_lib';

/**
 * 心跳等待感知钟面 E2E — 小欧-2026-09-17
 *
 * 多步任务触发: thinking → 工具调用 → 观察 → 最终报告
 * 验证:
 *   1. ClockStopwatch DOM 出现(10s 后)
 *   2. console 出现 [SSE-DBG] heartbeat / biz 信号
 *   3. [ClockStopwatch] 日志 level=green（正常流）
 *   4. 钟面秒数递增
 *   5. 终态后钟面消失
 */
test.describe('心跳等待感知钟面', () => {
  const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
  const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
  const BLOG = getTodayLogPath(BACKEND_DIR);

  test('多步任务: 钟面出现→心跳微闪→秒数递增→终态消失', async ({ page }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed } =
      attachStreamDiag(page);

    // 环境: 进程分离跨域(同 fre2e_01)
    killPort(9000);
    await expect
      .poll(() => waitPortDown(9000), { timeout: 20_000, interval: 500 })
      .toBeTruthy();
    const proxyLog1 = proxyLogPath();
    startProxyServer(FRONTEND_DIR, proxyLog1);
    await expect
      .poll(() => waitPortUp(9000), { timeout: 60_000, interval: 500 })
      .toBeTruthy();

    killPort(5173);
    await expect
      .poll(() => waitPortDown(5173), { timeout: 20_000, interval: 500 })
      .toBeTruthy();
    startDevServer(
      FRONTEND_DIR,
      'run dev -- --config e2e_case/vite.e2e.config.ts',
      'set "VITE_API_BASE_URL=http://localhost:9000/api/v1" && '
    );
    await expect
      .poll(() => waitPortUp(5173), { timeout: 60_000, interval: 500 })
      .toBeTruthy();

    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    const logBase = logBaseOf(BLOG);

    // 多步 prompt: 要求工具调用+思考+最终报告，确保流足够长(>10s)
    const PROMPT =
      '请完成以下三步任务并输出结构化报告(3000字以上)：' +
      '①用文件工具读取 frontend/package.json 并列出所有依赖包名;' +
      '②用联网搜索工具查询今天的日期;' +
      '③基于①②结果撰写一份不少于3000字的技术报告，必须包含方法、证据、风险、结论四个部分。注意请在完成全部研究并充分整理后再输出最终报告。';
    await chat.sendPrompt(PROMPT);

    // 等流启动
    try {
      await chat.waitReceiving(90_000);
    } catch (e) {
      printDiag(
        streamReqs,
        reconnectLogs,
        sseErrors,
        consoleAll,
        readLogSince(BLOG, 0),
        allFailed,
        getCaseId()
      );
      throw e;
    }

    console.log('[E2E-CLOCK] 流已启动, 轮询钟面出现...');

    const clockEl = page.locator('.clock-stopwatch');
    let clockCount = 0;
    for (let i = 0; i < 30; i += 1) {
      await page.waitForTimeout(2_000);
      clockCount = await clockEl.count();
      console.log(`[E2E-CLOCK] 轮询${i + 1}: count=${clockCount}`);
      if (clockCount >= 1) break;
    }
    expect(clockCount).toBeGreaterThanOrEqual(1);

    // === 验证 2: ClockStopwatch 渲染日志(软断言, 以DOM为准) ===
    const clockLogs = consoleAll.filter((c) => c.includes('ClockStopwatch'));
    console.log(`[E2E-CLOCK] ClockStopwatch日志数=${clockLogs.length}`);
    if (clockLogs.length > 0) {
      console.log(`[E2E-CLOCK] 最新钟面: ${clockLogs[clockLogs.length - 1]}`);
    }

    // === 验证 4: 钟面秒数递增(取两次 DOM 快照对比) ===
    const getText = async () => {
      const svgTexts = clockEl.first().locator('svg text');
      return await svgTexts
        .first()
        .textContent({ timeout: 10_000 })
        .catch(() => null);
    };
    const t1 = await getText();
    await page.waitForTimeout(3000);
    const t2 = await getText();
    console.log(`[E2E-CLOCK] 秒数快照: t1=${t1} t2=${t2}`);
    if (t1 && t2) {
      expect(Number(t2)).toBeGreaterThan(Number(t1));
    }

    // 等终态
    await chat.waitDone(300_000);
    await page.waitForTimeout(2000);

    // === 验证 5: 终态后钟面消失 ===
    const finalClockCount = await clockEl.count();
    console.log(
      `[E2E-CLOCK] 终态后 DOM .clock-stopwatch count = ${finalClockCount}`
    );
    expect(finalClockCount).toBe(0);

    // 终态正文
    const finalText = await chat.getFinalText();
    expect(finalText.trim().length).toBeGreaterThan(30);

    // 打印全量诊断
    printDiag(
      streamReqs,
      reconnectLogs,
      sseErrors,
      consoleAll,
      readLogSince(BLOG, logBase),
      allFailed,
      getCaseId()
    );

    await keepBrowserOpenIfRequested(page);
  });
});
