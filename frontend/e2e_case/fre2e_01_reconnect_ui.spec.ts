import { test, expect } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  getTodayLogPath,
  hasAdjacentDup,
  findAdjacentDup,
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
 * 断线重连 UI 全链路 E2E — 小欧-2026-09-13
 *
 * 真实浏览器(chromium) + 真实后端(uvicorn:8000) + 真实LLM + 真实SQLite。
 *
 * 断流手段(进程分离): 页面由 vite dev(:5173, hmr:false, 永活) 服务, vite proxy '/api' 上游指向
 *   独立后端代理(:9000→8000, e2e_case/api-proxy.ts); 运行时 kill 代理进程(9000)
 *   → 浏览器<->vite(5173) 链路完好(页面永远不 reload), 仅 API 链路 RST → 前端 fetch 流报错(真·断线) →
 *   后端 uvicorn(:8000) 内存任务保持存活 → 重启代理(9000) → 前端 Full-Jitter 退避
 *   → GET /chat/stream/{task_id}?after_seq=lastSeqRef+1 断点续传 → UI 无重复(run-on)
 *   → 终态正文完整; 后端补点A"重连请求接收"日志留痕对账。
 *
 * 架构分层: 本 case（断连专项）独立存在、编排内聚于此文件;
 *   通用设施在 ../e2e_front_lib（process.ts: 进程/端口; stream-diag.ts: SSE诊断+日志对账+run-on; chat-page.ts: POM）。
 * 注: context.setOffline 只拦截新请求, 无法中断 in-flight 的 SSE 流(已实测), 故不用。
 */

test.describe('断线重连 UI 全链路', () => {
  const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
  const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
  const BLOG = getTodayLogPath(BACKEND_DIR);

  test('断连(代理9000)→前端重连→after_seq续传→UI无重复/终态完整', async ({
    page,
  }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed, t0 } =
      attachStreamDiag(page);

    // 环境就绪(进程分离-跨origin): 后端代理B(:9000→8000, 页面API/SSE经VITE_API_BASE_URL直连跨域)
    //   + vite A(:5173, hmr:false, 永活服务页面)
    // 2026-09-13 小欧 方案演进: 断流目标必须是"浏览器直连的进程"才能被fetch感知RST——
    //   经中间代理(如vite http-proxy)中转时, 上游RST被代理静默吞掉挂起(前端无感, 端点活UA);
    //   故页面API基址注入为 http://localhost:9000/api/v1 直连代理B(跨域CORS), 杀B=浏览器直连RST。
    killPort(9000);
    await expect
      .poll(() => waitPortDown(9000), { timeout: 20_000, interval: 500 })
      .toBeTruthy();
    // 编辑历史: 2026-09-13 小欧 - 代理日志按轮落盘(api-proxy-<ts>.log), 断/重启两轮各独立命名 - 小欧-2026-09-13
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

    // 本轮日志基线: 只对账本次运行新增日志(防止匹配到以往轮次遗留的重连记录)
    const logBase = logBaseOf(BLOG);

    const prompt = '请简要描述你在当前开发环境中的进程与端口情况，并给出结论。';
    await chat.sendPrompt(prompt);

    // 1) 流已启动: 等"停止"按钮出现(发送后 isReceiving=true 即切停止)
    //    2026-09-13 小欧: 失败即打全量诊断(定位发送后未进流: 代理跨域拦/POST未达/token问题)
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

    // 2) 等绿圈(已收到 thinking 帧, 内容实质开流), 非强制
    await chat.waitGreenDot(90_000);

    // 3) 等"在途活跃帧"窗口再断: 固定4s断流会偶发断在"流尾部/任务已产完"(final早已转发,
    //    只剩空保活连接) → kill只切空连接, 前端EOF视为自然结束不重连(取证: reader is_reconnect=False 直通final)。
    //    编辑历史: 2026-09-13 小欧 - 轮询最近业务帧(newest非pause console) age<2.5s 才动手, 确保断点撞在数据流动中 - 小欧-2026-09-13
    const busiest = (): number => {
      // [T+Xms] 与当前时刻同为 attach 的 t0(绝对 Date.now)基准
      let t = 0;
      for (const c of consoleAll.slice(-50)) {
        const mt = c.match(/\[T\+(\d+)ms\]/);
        const tt = Number(mt?.[1] || 0);
        if (
          tt &&
          !/onPaused|连接建立|重连|暂停|缓冲|清空|加载|初始化/.test(c)
        ) {
          t = Math.max(t, tt);
        }
      }
      return t;
    };
    const dl3 = Date.now() + 90_000;
    while (Date.now() < dl3) {
      const lastT = busiest();
      if (lastT && Date.now() - (t0 + lastT) < 2500) {
        await page.waitForTimeout(200);
        break;
      }
      await page.waitForTimeout(800);
    }

    // 4) 杀后端代理B(:9000) → 页面<->vite(A)完好, 仅 API 链路 RST → 前端感知断线(页面不 reload)
    killPort(9000);
    await expect
      .poll(() => waitPortDown(9000), { timeout: 20_000, interval: 500 })
      .toBeTruthy();

    // 5) 断言前端检测到断线并进入重连(console 出现 "准备重连"/"重连")
    //    2026-09-13 小欧: 改手动轮询, 失败即打全量诊断(定位"断线未被前端感知"归属: 代理未真断/流未起/vite proxy吞错)
    const detectReconnect = (): boolean =>
      reconnectLogs.some((c) => c.includes('重连'));
    const deadline = Date.now() + 30_000;
    while (!detectReconnect() && Date.now() < deadline) {
      await page.waitForTimeout(500);
    }
    if (!detectReconnect()) {
      printDiag(
        streamReqs,
        reconnectLogs,
        sseErrors,
        consoleAll,
        readLogSince(BLOG, 0),
        allFailed,
        getCaseId()
      );
      throw new Error('[E2E] 前端未进入重连(断线未被感知)');
    }

    // 6) 重启后端代理B(:9000, 后端任务存活, API 链路经代理恢复)
    //    2026-09-13 小欧: vite A(:5173) 全程未杀, 页面永活 → GET#2/3 退避重连续传不被销毁中断,
    //    最贴近真实"网关/反代短暂重启": 恢复后首次 GET 即达后端续传。
    const proxyLog2 = proxyLogPath();
    startProxyServer(FRONTEND_DIR, proxyLog2);
    await expect
      .poll(() => waitPortUp(9000), { timeout: 60_000, interval: 500 })
      .toBeTruthy();

    // 7) 等流结束: "发送"按钮复现(isReceiving=false, done 已处理)
    await chat.waitDone(300_000);

    // 8) 断言至少一次重连且 after_seq 递增续传(轮询等 GET 打进 console)
    const hasAfterSeq = (): boolean =>
      reconnectLogs.some((c) => {
        const m = c.match(/after_seq=(\d+)/);
        return !!m && Number(m[1]) > 0;
      });
    await expect.poll(hasAfterSeq, { timeout: 60_000 }).toBeTruthy();

    // 9) 终态正文完整 + 无同段相邻重复(run-on): 断点续传若重发会造成正文二次拼接。
    //    逐行检测(仅同一文本行内比对): 跨行重复(表格分隔线/列表)不算, 行内无换行的连续重复才是流式拼接特征。
    //    2026-09-13 小欧: 失败即打全量诊断(归因: 产品续传重叠/reload破坏态/LLM输出重复需人工核对正文)
    await page.waitForTimeout(1500);
    const finalText = await chat.getFinalText();
    try {
      expect(hasAdjacentDup(finalText)).toBe(false);
      // 正文非空即有产出
      expect(finalText.trim().length).toBeGreaterThan(30);
    } catch (e) {
      // 编辑历史: 2026-09-13 小欧 - 失败时打印重复片段上下文, 区分"LLM天然重复误报"与"续传重叠真run-on" - 小欧-2026-09-13
      console.log('[run-on] findAdjacentDup 命中列表(前10):');
      findAdjacentDup(finalText)
        .slice(0, 10)
        .forEach((h) => console.log(`[run-on]   ${h}`));
      printDiag(
        streamReqs,
        reconnectLogs,
        sseErrors,
        consoleAll,
        readLogSince(BLOG, logBase),
        allFailed,
        getCaseId()
      );
      throw e;
    }

    // 10) 后端补点A"重连请求接收"日志留痕对账(仅查本轮新增日志, after_seq>0 即真实 HTTP GET 命中重连端点)
    //    编辑历史: 2026-09-13 小欧 - 兜底: readLogSince 起点偏移随日志轮转可能失效致 tail 无匹配,
    //    改用本轮 task id 全文件过滤(防误匹配遗留轮), 消除该偶发红 - 小欧-2026-09-13
    const tail = readLogSince(BLOG, logBase);
    let recon = tail.match(/重连请求接收[^\n]*after_seq=(\d+)/);
    if (!recon) {
      const m = streamReqs
        .map((x) => x.match(/task-([0-9a-f]{32})/)?.[1])
        .find((x) => x);
      if (m) {
        recon = readLogSince(BLOG, 0)
          .split('\n')
          .filter((l) => l.includes(m))
          .join('\n')
          .match(/重连请求接收[^\n]*after_seq=(\d+)/);
      }
    }

    // [DIAG] 无条件输出网络/重连全量诊断(供失败归因, 不参与断言)
    printDiag(
      streamReqs,
      reconnectLogs,
      sseErrors,
      consoleAll,
      tail,
      allFailed,
      getCaseId()
    );

    expect(recon).not.toBeNull();
    expect(Number(recon![1])).toBeGreaterThan(0);

    // 特例保留: 双开关(命令行 KEEP_BROWSER=1 临时 / e2e.config.ts E2E_KEEP_BROWSER_OPEN=true)时完成后挂起不关浏览器(仅单 case 调试, Ctrl+C 结束)
    await keepBrowserOpenIfRequested(page);
  });
});
