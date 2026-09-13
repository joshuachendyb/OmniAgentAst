/**
 * e2e_front_lib/normal-chat.ts — 普通功能会话流通用设施（前端 Playwright E2E 公用库）
 * 小欧 2026-09-13
 *
 * 适用场景: 非断流专项的 发一条消息 → 等流启动 → 等流终止 → 取终态正文 型 UI 全链路用例
 *   （查天气 / 查股票行情 / 查文件目录分析 等 fre2e_* 普通 case）。
 *
 * 与断连 case 环境差异: 不需要 9000 后端代理、不需要注入 VITE_API_BASE_URL ——
 *   页面由默认 vite dev(:5173, `npm run dev`) 服务，前端 API 默认基址为
 *   `http://localhost:8000/api/v1`（getApiBaseUrl 对未注入环境自动按 hostname:8000 组装）直连后端，
 *   后端 CORSMiddleware 已放行 http://localhost:5173（见 backend/app/constants.py DEFAULT_CORS_ORIGINS）。
 *
 * 失败归因: 复用 attachStreamDiag/printDiag 全链路诊断（网络 REQ/RES/FAIL + 前端 SSE console）。
 */
import { ChatPage } from './chat-page';
import { DiagBundle, getCaseId, printDiag } from './stream-diag';
import { ensureDevServer } from './process';

// 编辑历史: 2026-09-13 小欧 - 初创(3个普通功能UI用例复用): 起默认vite dev环境 + 一条消息流到终态 - 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 v2 - 复用优先转发 ensureDevServer(通用过程已在 process.ts):
//   5173 已有活的前端服务(vite dev)则直接复用, 不 kill+冷启动(省白屏几秒~十几秒); 无服务才由通用函数启动。
//   断连 case(fre2e_01) 例外仍自启专用 config(hmr:false)——其进程隔离方案须独占5173, 不复用。 - 小欧-2026-09-13
/** 普通会话流环境(复用优先): 5173 已有 vite dev 活服务则直接复用, 否则自动启动(`npm run dev` 默认config)并等就绪。
 *  仅服务于页面来源, API 由前端默认基址直连后端 :8000(跨域CORS放行), 不起9000代理/不注入VITE_API_BASE_URL。 */
export const startNormalUiEnv = async (frontendDir: string): Promise<void> => {
  await ensureDevServer(5173, frontendDir, 'run dev');
};

// 编辑历史: 2026-09-13 小欧 - 新增: 一条消息流到终态并取正文, 失败打全量DIAG - 小欧-2026-09-13
/** 普通会话流主流程: sendPrompt → 等流启动(停止钮) → 等绿圈(非强制) → 等流终止(发送钮) → 取终态正文。
 *  任一步失败 printDiag 全量网络/console 取证后抛错。 */
export const runChatFlow = async (
  chat: ChatPage,
  prompt: string,
  opts: { diag?: DiagBundle; waitDoneTimeout?: number } = {}
): Promise<string> => {
  const diag = opts.diag;
  const doneTimeout = opts.waitDoneTimeout ?? 300_000;
  try {
    await chat.sendPrompt(prompt);
    await chat.waitReceiving(90_000);
    await chat.waitGreenDot(90_000);
    await chat.waitDone(doneTimeout);
    await chat.waitMs(1500);
    return await chat.getFinalText();
  } catch (e) {
    if (diag) {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        '',
        diag.allFailed,
        getCaseId()
      );
    }
    throw e;
  }
};
