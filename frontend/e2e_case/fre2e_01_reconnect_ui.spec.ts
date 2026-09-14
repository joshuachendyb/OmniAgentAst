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
    const { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed } =
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

    // 编辑历史: 2026-09-14 小欧 - 断连窗口健壮性修复(两次连败, 快模型下任务50s即终态):
    //   busy原始用consoleAll末尾50条判活跃, 2000步经渲染洪水(DBG-3b/4d逐step一条)经Playwright事件队列
    //   背压滞后, "看着新鲜"的时间戳在任务已自然完成后误判活跃→kill空连接→前端EOF当自然结束不重连;
    //   改busiest只认真实业务帧([ACTION]/thought-start等, 剔除DBG渲染) + isFinalArrived守卫(终态到不kill)
    //   + 换多工具长任务prompt拉长任务窗口, 三重保障断连窗口可重复命中 - 小欧-2026-09-14
    const PROMPT =
      '请依次完成三项研究并输出一份结构化报告(300字以上,含标题/Markdown列表/结论段)：' +
      '①用文件工具统计 backend/app 目录下 .py 文件数量, 并找出其中含 "TODO" 注释的全部文件路径;' +
      '②用联网搜索工具查询北京今天的天气(含温度/空气质量);' +
      '③将①②研究结果汇总为最终报告。注意请在完成全部研究后才输出最终报告, 不要提前收尾。';
    await chat.sendPrompt(PROMPT);

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

    // 2) 等绿圈(已收到 thinking 帧) —— 非强制锚点, 见下注
    // 编辑历史: 2026-09-14 小欧 - 弃用绿圈锚点: 实测本任务绿圈(T~45s)是"收尾锚点"非"开流锚点"
    //   (LLM先跑完1078步工具调用, 最后才产thinking+报告), waitGreenDot 阻塞到45s+固定延后=距final仅3s
    //   → 断连窗口必错失; 正式锚点改回 waitReceiving(停止按钮=流已建立, T~11s) + 固定4s断(余量33s) - 小欧-2026-09-14
    // await chat.waitGreenDot(90_000);

    // 3) 确定"在途活跃"断点: waitReceiving 返回(停止按钮已现=流已建立/SSE已连, 实测T~11s),
    //    之后固定等4s即断 → 断点落 T~15s 数据流中段(final实测T~48s, 余量33s), 避开"断在流尾部"(final
    //    早已转发只剩空保活连接, kill只切空连接, 前端EOF视为自然结束不重连)。
    //    编辑历史: 2026-09-13 小欧 - 原先"固定4s断流"会偶发断在流尾部; 后改"最近业务帧 age<2.5s"才动手 - 小欧-2026-09-13
    //    编辑历史: 2026-09-14 小欧 - 放弃console活跃帧采样与绿圈锚点(实测任务1697步console几乎全是DBG-3b
    //      渲染洪水,真业务帧仅T+17.8s一条→busiest恒错过; 绿圈在收尾段才出现), 回归 waitReceiving 锚点固定4s断 - 小欧-2026-09-14
    const isFinalArrived = (): boolean =>
      consoleAll.some(
        (c) =>
          c.includes('[收到final终态]') ||
          c.includes('[SSE] 流正常结束') ||
          c.includes('AI流式完成') ||
          c.includes('AI响应完成 END')
      );
    await page.waitForTimeout(4000);

    // 3.5) 窗口守卫: 断点前任务已自然终态 → 不可执行断连语义, 走终态验证并明示"窗口错过"需重跑(诚实, 不伪装已测断连)
    //     编辑历史: 2026-09-14 小欧 - 新增: 快模型下任务50s即终态的根因兜底 - 小欧-2026-09-14
    if (isFinalArrived()) {
      // 编辑历史: 2026-09-14 小欧 - 错过窗口时先落全量DIAG再throw(取证本轮console时间线), 便于归因任务时长/帧到达滞后 - 小欧-2026-09-14
      printDiag(
        streamReqs,
        reconnectLogs,
        sseErrors,
        consoleAll,
        readLogSince(BLOG, logBase),
        allFailed,
        getCaseId()
      );
      await chat.waitDone(60_000);
      const ft = await chat.getFinalText();
      expect(ft.trim().length).toBeGreaterThan(30);
      throw new Error(
        '[E2E] 断连窗口错过: 任务在 kill 前已自然完成(final已收), 重连语义未执行——请重跑本条以覆盖断连分支'
      );
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
