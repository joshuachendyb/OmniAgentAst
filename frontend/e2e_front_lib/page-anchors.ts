import type { Page } from '@playwright/test';

/**
 * 页面锚点读取(左侧任务列表 / 地址栏) —— 小欧 2026-10-01
 *
 * 【为什么抽到 lib】
 *   fre2e_15 / 16 / 17 三个 case 都要读同一个左侧任务列表的 active task_id,
 *   原先各抄一份完全相同的实现(共 3 份)。选择器一改就得改三处, 漏一处就某个 case
 *   悄悄读空串 → 断言假红或假绿。锚点口径必须唯一。
 */

/**
 * 左侧任务列表当前选中项的 task_id。
 *
 * 锚点: `.task-list-item.active` 的 `aria-label="任务 ${task_id} ${status}"`
 *       (TaskListPanel 渲染, 见 2026-09-13 建库时的锚点记录)
 * 读不到(列表还没渲染/无 active 项) → 空串, 由调用方显式判红, **不返回占位 id**。
 */
export const activeTaskId = async (page: Page): Promise<string> => {
  const label = await page
    .locator('.task-list-item.active')
    .first()
    .getAttribute('aria-label');
  return label?.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '';
};

/** 指定 task 在左侧列表里的 status(TaskListPanel: aria-label="任务 ${id} ${status}") */
export const taskStatusInList = async (
  page: Page,
  taskId: string
): Promise<string> => {
  const label = await page
    .locator(`.task-list-item[aria-label^="任务 ${taskId} "]`)
    .first()
    .getAttribute('aria-label');
  return label?.match(/^任务 (\S+) (\S+)$/)?.[2] ?? '';
};

/**
 * 该会话在左侧列表里的全部 task_id。
 *
 * **仅作软证据**: 列表可能只渲染最近 N 条, 拿它做"某 task 必须存在"的硬断言会假失败
 * (任务明明在 DB 里)。要硬断言"某 task 在这个会话里", 用 REST /sessions/{id}/tasks。
 */
export const allTaskIdsInList = async (page: Page): Promise<string[]> => {
  const labels = await page
    .locator('.task-list-item')
    .evaluateAll((els) => els.map((e) => e.getAttribute('aria-label') ?? ''));
  return labels
    .map((l) => l.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '')
    .filter(Boolean);
};

/**
 * 从地址栏取 session_id。
 *
 * 注意: 会话页 URL **常常不带** session_id([63]第八章定案"落到最近会话是常态"),
 * 菜单回跳靠 sessionStorage 回落。所以本函数返回空串是**正常情况**, 不代表出错 ——
 * 需要 session_id 判 DB 状态时, 改用「按 prompt 片段反查」或「进会话时就先记下 id」。
 */
export const sessionIdFromUrl = (page: Page): string =>
  new URL(page.url()).searchParams.get('session_id') ?? '';