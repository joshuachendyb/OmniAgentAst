/**
 * Step Constants - 步骤类型标签和图标常量
 *
 * @author 小沈
 * @version 1.0
 * @since 2026-04-20
 */
// 编辑历史: 2026-09-07 小欧 - 4.4.1旧case清零: 删STEP_LABEL_MAP/STEP_ICON_MAP的cancelled条目(取消收尾单一由final+cancelled承担)
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计文档[76] 6.12): 加merged文案'已并入'+图标'↪' — 小欧-2026-09-28

export const STEP_LABEL_MAP: Record<string, string> = {
  start: '开始',
  thought: '思考',
  action: '执行',
  observation: '观察',
  chunk: '回复',
  final: '完成',
  error: '错误',
  paused: '暂停',
  resumed: '恢复',
  retrying: '重试',
  merged: '已并入', // 2026-09-28 小欧: 注入应答语义(非重试)
  rate_limit: '限流',
};

export const STEP_ICON_MAP: Record<string, string> = {
  start: '🚀',
  thought: '💭',
  action: '⚙️',
  observation: '📋',
  chunk: '💬',
  final: '✅',
  error: '❌',
  paused: '⏸️',
  resumed: '▶️',
  retrying: '🔄',
  merged: '↪', // 2026-09-28 小欧
  rate_limit: '🚧',
};
