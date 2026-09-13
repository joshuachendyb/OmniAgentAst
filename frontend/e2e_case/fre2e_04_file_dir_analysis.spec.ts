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
 * 查文件目录分析 UI 全链路 E2E — 小欧-2026-09-13
 *
 * 真实浏览器(chromium) + 真实后端(uvicorn:8000) + 真实LLM + 真实SQLite。
 * 场景: 分析 F:\OmniAgentAs-repair 项目目录结构（listdir/find 等 FILE 工具默认已注入 UniversalAgent）。
 *
 * 环境(普通会话流): 默认 vite dev(:5173) 服务页面, 前端 API 默认基址直连后端 :8000(跨域CORS放行),
 *   不起 9000 代理/不注入 VITE_API_BASE_URL(与断连 case 的进程分离环境差异, 见 normal-chat.ts)。
 *
 * 架构分层: 本 case 独立、场景内聚; 通用设施(环境/会话流)在 ../e2e_front_lib。
 */
test.describe('查文件目录分析 UI 全链路', () => {
  const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend';
  const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
  const BLOG = getTodayLogPath(BACKEND_DIR);
  // ============================================================
  // 特例区 ① prompt —— 新普通 case 只需替换本行(场景输入); 以下均库通用调用
  // 编辑历史: 2026-09-13 小欧 - 特例区标注, 便于照模板生成新case - 小欧-2026-09-13
  // ============================================================
  const PROMPT =
    '请分析 F:\\OmniAgentAs-repair 项目的目录结构：用工具列出根目录内容，并统计 backend 目录下 .py 文件与 frontend 目录下 .ts 文件的数量，最后总结项目的主要模块组成。';

  test('发消息→真实目录分析→终态正文含结构统计', async ({ page }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);

    // 环境: 杀残留5173→起默认 vite dev(:5173)→等就绪; 前端API直连:8000(跨域CORS放行), 无9000代理
    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    const logBase = logBaseOf(BLOG);
    const text = await runChatFlow(chat, PROMPT, { diag });
    const tail = readLogSince(BLOG, logBase);

    // ============================================================
    // 特例区 ② 断言 —— 新普通 case 只需替换本段(按场景校验终态正文)
    // 编辑历史: 2026-09-13 小欧 - 特例区标注, 便于照模板生成新case - 小欧-2026-09-13
    // ============================================================
    // 断言1: 正文非空有产出
    expect(text.trim().length).toBeGreaterThan(30);
    // 断言2: 主题结论命中(项目目录/模块 + 统计语义)
    const hitTheme =
      /backend|frontend|OmniAgentAs/.test(text) &&
      /个|文件|目录|模块/.test(text);
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
