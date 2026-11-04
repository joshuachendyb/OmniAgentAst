/**
 * e2e_front_lib/index.ts — 前端 Playwright E2E 公用库统一出口（对应后端 e2etests/e2emodel）
 * 小欧 2026-09-13
 *
 * 用例引用（相对路径）：
 *   import { ChatPage, killPort, startDevServer, waitPortUp } from '../../e2e_front_lib';
 *   import { attachStreamDiag, getTodayLogPath, hasAdjacentDup, logBaseOf, printDiag, readLogSince } from '../../e2e_front_lib';
 *
 * 编辑历史: 2026-09-13 小欧 - 新增 normal-chat(普通会话流环境/主流程, 供查天气/股票/目录分析等普通case复用) - 小欧-2026-09-13
 * 编辑历史: 2026-09-26 小欧 - 新增 auth 导出: injectAuthToken(页面加载前预置访问口令),
 *   后端 12 个 router 已挂 token 鉴权, 前端 8 个 E2E 不带口令会集体 401; token 取环境变量 OMNIAGENT_ACCESS_TOKEN - 小欧-2026-09-26
 */
export * from './process';
export * from './stream-diag';
export * from './chat-page';
export * from './normal-chat';
// 访问口令注入（E2E 统一入口，不逐个用例改）
export * from './auth';
// 顶栏「轮数/步骤数」计数器读取(fre2e_14/15/16/17 共用, 口径必须一致) - 小欧 2026-10-01
export * from './step-counter';
// 后端任务状态读取(按 task_id 精确查, 统一"不回落最新任务"语义) - 小欧 2026-10-01
export * from './task-status';
// 页面锚点(左侧任务列表 active/task 读取 + 地址栏 session_id) - 小欧 2026-10-01
export * from './page-anchors';
