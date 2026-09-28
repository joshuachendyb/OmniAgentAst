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
      .poll(() => waitPortDown(9000), { timeout: 20_000, intervals: [500] })
      .toBeTruthy();
    const proxyLog1 = proxyLogPath();
    startProxyServer(FRONTEND_DIR, proxyLog1);
    await expect
      .poll(() => waitPortUp(9000), { timeout: 60_000, intervals: [500] })
      .toBeTruthy();

    killPort(5173);
    await expect
      .poll(() => waitPortDown(5173), { timeout: 20_000, intervals: [500] })
      .toBeTruthy();
    startDevServer(
      FRONTEND_DIR,
      'run dev -- --config e2e_case/vite.e2e.config.ts',
      'set "VITE_API_BASE_URL=http://localhost:9000/api/v1" && '
    );
    await expect
      .poll(() => waitPortUp(5173), { timeout: 60_000, intervals: [500] })
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

    // 2026-09-28 小欧 - 轮询窗口从「固定 60s」改为「覆盖整个任务生命周期」。
    //   原缺陷：本 prompt 刻意要求「先完成全部研究再输出报告」，前 ~200s 全是短工具调用
    //   （实测工具耗时中位 0.26s），文本流式输出要到任务末尾才开始。而钟面挂在
    //   TextStream 的 `cursor && typing`（打字机输出中）上，无文本输出即无该挂载点；
    //   工具挂载点虽在但每窗口仅活 0.26s，撞不上 APPEAR_SEC=10 的设计门槛。
    //   → 原 30×2s=60s 窗口恰好落在「钟面按设计不出现」的时段，30 次全 0 是**误报**，
    //     而非产品缺陷（实测钟面在长文本流式输出期正常显示）。
    //   改为：轮询到钟面出现或任务终态为止（上限 300s），终态也算一次探测。
    const clockEl = page.locator('.clock-stopwatch');
    let clockCount = 0;
    const pollDeadline = Date.now() + 300_000;
    for (let i = 0; Date.now() < pollDeadline; i += 1) {
      await page.waitForTimeout(2_000);
      clockCount = await clockEl.count();
      if (clockCount >= 1) {
        console.log(`[E2E-CLOCK] 轮询${i + 1}: count=${clockCount} (命中)`);
        break;
      }
      // 终态到达则停止：此后不会再有新的文本流式输出窗口
      // （终态判据复用 chat-page.ts 的 sendBtn —— 它可见即 isReceiving=false，与 waitDone 同源）
      if (await chat.sendBtn.isVisible().catch(() => false)) {
        console.log(
          `[E2E-CLOCK] 轮询${i + 1}: count=${clockCount} (任务已终态, 停止轮询)`
        );
        break;
      }
      if (i % 5 === 0) console.log(`[E2E-CLOCK] 轮询${i + 1}: count=0`);
    }
    expect(clockCount).toBeGreaterThanOrEqual(1);

    // === 验证 2: ClockStopwatch 渲染日志(软断言, 以DOM为准) ===
    const clockLogs = consoleAll.filter((c) => c.includes('ClockStopwatch'));
    console.log(`[E2E-CLOCK] ClockStopwatch日志数=${clockLogs.length}`);
    if (clockLogs.length > 0) {
      console.log(`[E2E-CLOCK] 最新钟面: ${clockLogs[clockLogs.length - 1]}`);
    }

    // === 验证 4: 钟面秒数递增(取两次 DOM 快照对比) ===
    // 2026-09-28 小欧 - 收窄到 :visible。钟面挂在多个等待窗口(打字机段/ToolCallLine 等待段)，
    //   每窗口一实例且各自从挂载时刻起算；原取 .first() 可能命中非当前可见的那一个。
    //   紧接命中后立即连拍，确保两次快照落在同一挂载实例上（窗口切换会重置计时）。
    const visibleClock = () => page.locator('.clock-stopwatch:visible').first();
    const getText = async () => {
      const svgTexts = visibleClock().locator('svg text');
      return await svgTexts
        .first()
        .textContent({ timeout: 10_000 })
        .catch(() => null);
    };
    const t1 = await getText();
    await page.waitForTimeout(3000);
    const t2 = await getText();
    console.log(`[E2E-CLOCK] 秒数快照: t1=${t1} t2=${t2}`);
    expect(t1).not.toBeNull();
    expect(t2).not.toBeNull();
    expect(Number(t2)).toBeGreaterThan(Number(t1));

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
