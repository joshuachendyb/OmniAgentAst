import { test, expect } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  findAdjacentDup,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  printDiag,
  readLogSince,
  runChatFlow,
  startNormalUiEnv,
} from '../e2e_front_lib';

/**
 * 查天气 UI 全链路 E2E — 小欧-2026-09-13
 *
 * 真实浏览器(chromium) + 真实后端(uvicorn:8000) + 真实LLM + 真实SQLite。
 * 场景: 查询北京实时天气（联网类）。后端无专用天气工具, 依赖 UniversalAgent 的动态工具注入:
 *   FUNDAMENTAL.searchtool(FILE已注入) 命中"联网/搜索"关键词 → 自动注入 NETWORK 整类
 *   (httpget/searchweb/fetchpage) → LLM 再调用真实联网工具取数并总结。
 *
 * 环境(普通会话流): 默认 vite dev(:5173) 服务页面, 前端 API 默认基址直连后端 :8000(跨域CORS放行)。
 *
 * 架构分层: 本 case 独立、场景内聚; 通用设施(环境/会话流)在 ../e2e_front_lib。
 */
test.describe('查天气 UI 全链路', () => {
  const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
  const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
  const BLOG = getTodayLogPath(BACKEND_DIR);
  // ============================================================
  // 特例区 ① prompt —— 新普通 case 只需替换本行(场景输入); 以下均库通用调用
  // 编辑历史: 2026-09-13 小欧 - 特例区标注, 便于照模板生成新case - 小欧-2026-09-13
  // ============================================================
  // 2026-10-01 小欧 [1] 升级为多步带工具任务(北京老陈指示: 每个 case 必须多步, 纯问答测不出问题)。
  //   原 prompt 单轮一句"查北京天气 → 搜工具 → 调用 → 回答", 联网工具往往一次命中即出 final,
  //   步骤链只有 1-2 环, 右栏步骤/轮次/等待圈都单薄, 切流·续传·帧连续性这类判据拿不到数据。
  //   现要求 5 步多轮取数(定位工具→查天气→查空气质量→落盘核对→综合出行建议),
  //   与其余用例的工具链各不相同(只联网不落盘 vs 落盘 vs 只读 vs 建+写+查)。
  const PROMPT =
    '请完成一份"北京今日出行天气简报"，需覆盖天气状况、气温区间、空气质量与出行建议。请严格按以下五步实际操作（不要停留在思考层面）：' +
    '第一步：先判断需要哪一类联网工具（天气查询 vs 空气质量查询 vs 通用网页搜索），说明各自适用场景；' +
    '第二步：用天气类联网工具查询北京今天的天气状况与实时温度；' +
    '第三步：用空气质量类联网工具（或通用搜索）查询北京今日的空气质量指数与等级；' +
    '第四步：新建一个临时工作目录 fe02_weather，在其中创建一份 markdown 文件，' +
    '把第二步与第三步查到的真实数值（温度、天气现象、AQI、等级）逐项写入，并读回该文件核对是否写全；' +
    '第五步：在对话中给出不少于300字的出行建议正文，必须引用你上面查到的真实数值，' +
    '并明确给出"穿衣/出行/防护"三类具体建议。';

  test('发消息→真实联网多步查北京天气→终态正文含天气结论', async ({ page }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);

    // 环境: 杀残留5173→起默认 vite dev(:5173)→等就绪; 前端API直连:8000(跨域CORS放行), 无9000代理
    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    const logBase = logBaseOf(BLOG);
    const text = await runChatFlow(chat, PROMPT, {
      diag,
      waitDoneTimeout: 420_000,
    });
    const tail = readLogSince(BLOG, logBase);

    // ============================================================
    // 特例区 ② 断言 —— 新普通 case 只需替换本段(按场景校验终态正文)
    // 编辑历史: 2026-09-13 小欧 - 特例区标注, 便于照模板生成新case - 小欧-2026-09-13
    // ============================================================
    // 断言1: 正文非空有产出
    expect(text.trim().length).toBeGreaterThan(30);
    // 断言2: 主题结论命中(北京 + 天气/温度/℃/天气现象词)
    const hitTheme =
      text.includes('北京') && /天气|温度|气温|℃|晴|雨|多云|阴/.test(text);
    if (!hitTheme) {
      console.log(
        '[E2E] 正文未命中主题关键词(前300字):',
        text.trim().slice(0, 300)
      );
    }
    expect(hitTheme).toBe(true);
    // 断言3(软): 行内相邻重复仅提示不 fail —— hasAdjacentDup 专查断连续传重叠, 普通会话无拼接来源,
    //   LLM 手写报告天然重复表述会误报, 故折为 [DIAG] 提示供人工核对
    const dupHits = findAdjacentDup(text);
    if (dupHits.length > 0) {
      console.log('[DIAG] run-on 命中提示(普通会话不fail, LLM天然重复?):');
      dupHits.slice(0, 5).forEach((h) => console.log(`[DIAG]   ${h}`));
    }

    // ============================================================
    // 通用区 ③ 诊断输出(库 printDiag, 不参与断言, 失败归因用) —— 非特例, 新 case 保留即可
    // ============================================================
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      tail,
      diag.allFailed,
      getCaseId()
    );
    tail
      .split('\n')
      .filter((l) => l.includes('[tool_executor]'))
      .slice(-8)
      .forEach((l) => console.log(`[TOOL]  ${l.trim()}`));

    // 特例保留: 双开关(命令行 KEEP_BROWSER=1 临时 / e2e.config.ts E2E_KEEP_BROWSER_OPEN=true)时完成后挂起不关浏览器(仅单 case 调试, Ctrl+C 结束)
    await keepBrowserOpenIfRequested(page);
  });
});
