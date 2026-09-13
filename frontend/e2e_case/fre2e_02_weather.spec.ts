import { test, expect } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  findAdjacentDup,
  getCaseId,
  getTodayLogPath,
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
  const PROMPT =
    '请帮我查询北京今天的天气情况，包括天气状况、当前温度和空气质量，并给出简要的出行建议。请先搜索合适的联网工具，再调用它获取实时数据后回答。';

  test('发消息→真实联网查北京天气→终态正文含天气结论', async ({ page }) => {
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
  });
});
