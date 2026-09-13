/**
 * e2e_front_lib/index.ts — 前端 Playwright E2E 公用库统一出口（对应后端 e2etests/e2emodel）
 * 小欧 2026-09-13
 *
 * 用例引用（相对路径）：
 *   import { ChatPage, killPort, startDevServer, waitPortUp } from '../../e2e_front_lib';
 *   import { attachStreamDiag, getTodayLogPath, hasAdjacentDup, logBaseOf, printDiag, readLogSince } from '../../e2e_front_lib';
 */
export * from './process';
export * from './stream-diag';
export * from './chat-page';