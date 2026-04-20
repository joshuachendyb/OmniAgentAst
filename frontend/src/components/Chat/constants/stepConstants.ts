/**
 * 步骤常量定义
 * 【小强实现 2026-04-20】阶段1：提取labelMap/iconMap为常量，避免每次渲染重复创建
 */

// 步骤类型标签映射
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
} as const;

// 步骤类型图标映射
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
} as const;

// 步骤类型数组（用于遍历）
export const STEP_TYPES = Object.keys(STEP_LABEL_MAP) as Array<keyof typeof STEP_LABEL_MAP>;

// 内容区域基础样式
export const CONTENT_BASE_STYLE: React.CSSProperties = {
  color: "#333",
  wordBreak: "break-word",
  fontSize: 13,
  lineHeight: 1.8,
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
} as const;

// 步骤容器样式
export const STEP_CONTAINER_STYLE: React.CSSProperties = {
  marginBottom: 8,
  marginRight: 30,
  padding: "8px 12px",
  borderRadius: 8,
  background: "rgba(0,0,0,0.02)",
  transition: "all 0.2s ease",
} as const;

// 步骤容器hover样式
export const STEP_CONTAINER_HOVER_STYLE = {
  background: "rgba(0,0,0,0.04)",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
} as const;

// 步骤容器离开样式
export const STEP_CONTAINER_LEAVE_STYLE = {
  background: "rgba(0,0,0,0.02)",
  boxShadow: "none",
} as const;
