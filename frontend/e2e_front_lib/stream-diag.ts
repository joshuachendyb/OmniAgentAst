/**
 * e2e_front_lib/stream-diag.ts — chat/stream SSE 流全链路诊断工具（前端 Playwright E2E 公用库）
 * 小欧 2026-09-13（自 reconnect-ui.spec.ts 抽取，仅改导入路径不动业务逻辑）
 *
 * 含：当日后端日志路径/本轮新增日志对账、网络 REQ/RES/FAIL 收集、前端重连 console 收集、
 * run-on 无重复检测、DIAG 诊断输出。任何 chat/stream 流式用例失败归因都可复用。
 */
import { readFileSync } from 'node:fs';
import type { Page } from '@playwright/test';

/** 生成当日后端日志路径 `${backendDir}\logs\app_YYYY-MM-DD.log`（日志文件按日期轮转） */
export const getTodayLogPath = (backendDir: string): string => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${backendDir}\\logs\\app_${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}.log`;
};

/** 取日志文件"字符"基线（用于只对账"本轮新增日志"，防匹配历史轮次遗留记录）；文件不存在返回 -1
 *  编辑历史: 2026-09-13 小欧 - 修复编码错配: 原 readFileSync(logPath).length 返回"字节数"(UTF-8中文3字节/字符),
 *  而 readLogSince 用 String.slice(字符索引) 对齐 → 中文日志多时 base(字节)大于当前字符数 → slice 越界返回空串,
 *  导致后端对账 tail 恒为空(recon 匹配不到 '重连请求接收')。统一改用 utf8 字符索引 - 小欧-2026-09-13 */
export const logBaseOf = (logPath: string): number => {
  try {
    return readFileSync(logPath, 'utf8').length;
  } catch {
    return -1;
  }
};

/** 读取日志文件自基线之后的"本轮新增"片段 */
export const readLogSince = (logPath: string, base: number): string =>
  readFileSync(logPath, 'utf8').slice(Math.max(base, 0));

/** 在 page 上挂 chat/stream 相关监听：网络请求 REQ/RES/FAIL + 前端 SSE console，返回收集数组 */
export const attachStreamDiag = (page: Page): {
  streamReqs: string[];
  reconnectLogs: string[];
  sseErrors: string[];
  consoleAll: string[];
  allFailed: string[];
} => {
  const streamReqs: string[] = [];
  const reconnectLogs: string[] = [];
  const sseErrors: string[] = [];
  const consoleAll: string[] = [];
  const allFailed: string[] = [];
  // 小欧 2026-09-13: 相对毫秒时间戳(自挂载起), 用于还原重连/失败请求时序(定位 GET#2/3 是否真实发起)
  const t0 = Date.now();
  const ts = (): string => `T+${Date.now() - t0}ms`;
  page.on('console', (msg) => {
    const text = msg.text();
    consoleAll.push(`[${ts()}] [${msg.type()}] ${text}`);
    if (text.includes('[SSE]')) {
      if (text.includes('重连') || text.includes('GET')) {
        reconnectLogs.push(text);
      }
      if (/错误|超过|准备|轮询|耗尽|请求错误|终止|失败/.test(text)) {
        sseErrors.push(text);
      }
    }
  });
  // 编辑历史: 2026-09-13 小欧 - 断连E2E取证探针: 捕获页面加载/导航(确认是否reload销毁旧JS timer上下文) - 小欧-2026-09-13
  page.on('framenavigated', (f) => {
    if (f === page.mainFrame()) {
      consoleAll.push(`[${ts()}] [framenavigated] ${f.url()}`);
    }
  });
  // 编辑历史: 2026-09-13 小欧 - beforeunload探针: 定位 reload 的真正触发源(区分 vite full-reload vs 其他) - 小欧-2026-09-13
  page.addInitScript(() => {
    // window 唯一 id: 重生(document 重建)时打印 [BU] docid, 用于鉴别 reload vs 事件误报
    (window as unknown as { __docid?: string }).__docid = Math.random().toString(36).slice(2, 8);
    console.warn(`[BU] document init docid=${(window as unknown as { __docid?: string }).__docid}`);
    window.addEventListener('beforeunload', () => {
      console.warn(`[BU] beforeunload fired docid=${(window as unknown as { __docid?: string }).__docid}`);
    });
  });
  page.on('request', (req) => {
    if (req.url().includes('/chat/stream')) {
      streamReqs.push(`[${ts()}] REQ ${req.method()} ${req.url()}`);
    }
  });
  page.on('response', (res) => {
    if (res.url().includes('/chat/stream')) {
      streamReqs.push(`[${ts()}] RES ${res.status()} ${res.url()}`);
    }
  });
  page.on('requestfailed', (req) => {
    // 编辑历史: 2026-09-13 小欧 - 全URL失败探针(不限于chat/stream), 定位 reload 前"无JS日志"的额外REFUSED真身 - 小欧-2026-09-13
    allFailed.push(`[${ts()}] ${req.method()} ${req.url()} :: ${req.failure()?.errorText}`);
    if (req.url().includes('/chat/stream')) {
      streamReqs.push(`[${ts()}] FAIL ${req.method()} ${req.url()} :: ${req.failure()?.errorText}`);
    }
  });
  return { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed };
};

/**
 * run-on 检测：终态正文是否含"行内无换行的相邻重复"（流式 chunk 二次拼接特征）。
 * 逐行比对（跨行重复如表格分隔线/列表不算），行内 6~30 步长 3 滑动窗口。
 * 编辑历史: 2026-09-13 小欧 - 返回匹配上下文数组: 定位正文相邻重复为"LLM天然重复误报"还是"续传重叠真run-on" - 小欧-2026-09-13
 */
export const findAdjacentDup = (text: string): string[] => {
  const hits: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    for (let k = 6; k <= 30; k += 3) {
      for (let i = 0; i + 2 * k <= line.length; i++) {
        if (line.slice(i, i + k) === line.slice(i + k, i + 2 * k)) {
          const w = Math.min(12, k);
          hits.push(
            JSON.stringify(line.slice(Math.max(0, i - w), Math.min(line.length, i + 3 * k)))
          );
        }
      }
    }
  }
  return hits;
};

/** 判定是否有行内相邻重复（true=有，导致断言失败） */
export const hasAdjacentDup = (text: string): boolean => findAdjacentDup(text).length > 0;

/** [DIAG] 无条件输出网络/重连/后端日志片段诊断（供失败归因，不参与断言） */
export const printDiag = (
  streamReqs: string[],
  reconnectLogs: string[],
  sseErrors: string[],
  consoleAll: string[],
  tail: string,
  allFailed: string[] = [] // 2026-09-13 小欧: 全URL请求失败(定位reload前额外REFUSED) - 小欧-2026-09-13
): void => {
  console.log('\n[DIAG] === streamReqs(chat/stream 网络全量) ===');
  streamReqs.forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === allFailed(全URL请求失败全量) ===');
  allFailed.forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === reconnectLogs(前端SSE重连console) ===');
  reconnectLogs.forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === sseErrors(前端SSE错误/终止console) ===');
  sseErrors.forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === consoleAll(全量,取尾部40) ===');
  consoleAll
    .filter((l) => /SSE|nav|Toast|abort|断|停止|重|轮询|Failed|network|Error|错误|warn/i.test(l))
    .slice(-40)
    .forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === consoleAllRaw(全量,取尾部60不过滤) ===');
  consoleAll
    .slice(-60)
    .forEach((l) => console.log(`[DIAG]   ${l}`));
  console.log('[DIAG] === 后端本轮日志片段(重连相关) ===');
  tail
    .split('\n')
    .filter((l) => /重连|reconnect|final_stats|reader|客户端断开/i.test(l))
    .slice(-15)
    .forEach((l) => console.log(`[DIAG]   ${l}`));
};