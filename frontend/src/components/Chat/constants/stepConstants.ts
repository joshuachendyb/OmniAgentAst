/**
 * Step Constants - 步骤类型标签和图标常量
 * 
 * @author 小沈
 * @version 1.0
 * @since 2026-04-20
 */

export const STEP_LABEL_MAP: Record<string, string> = {
  start: "开始",
  thought: "思考",
  action_tool: "执行",
  observation: "观察",
  final: "完成",
  error: "错误",
  paused: "暂停",
  resumed: "恢复",
  interrupted: "中断",
  retrying: "重试",
  incident: "事件",
};

export const STEP_ICON_MAP: Record<string, string> = {
  start: "🚀",
  thought: "💭",
  action_tool: "⚙️",
  observation: "📋",
  final: "✅",
  error: "❌",
  paused: "⏸️",
  resumed: "▶️",
  interrupted: "⚠️",
  retrying: "🔄",
  incident: "⚡",
};