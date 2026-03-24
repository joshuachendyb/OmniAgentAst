/**
 * 步骤样式工具 - 统一管理所有步骤类型的视觉样式
 *
 * 功能：提供统一的getStepStyle函数，支持TypeScript类型检查
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-03-24
 */

// 步骤类型定义
export type StepType = 
  | 'thought' 
  | 'start' 
  | 'final' 
  | 'error' 
  | 'interrupted' 
  | 'paused' 
  | 'resumed' 
  | 'retrying'
  | 'observation' 
  | 'action_tool' 
  | 'chunk' 
  | 'report';

// 颜色方案接口
interface ColorScheme {
  bg1: string;          // 渐变起始颜色
  bg2: string;          // 渐变结束颜色
  border: string;       // 边框颜色
  text: string;         // 文字颜色
  label: string;        // 视觉标签（用于调试和辅助理解）
  priority: 'primary' | 'secondary' | 'accent';  // 视觉优先级
}

// 基础样式（所有步骤共享）
const baseStyle = {
  borderRadius: 8,
  padding: "10px 14px",
  marginTop: 6,
  fontSize: 13,
  lineHeight: 1.8,
};

// 精细化颜色方案映射 - 每个步骤都有独特的视觉语义
const colorSchemes: Record<StepType, ColorScheme> = {
  // ===== 思考类（橙色系）- 表示思考和警告 =====
  thought: {
    bg1: "#fff7e6",      // 浅橙色
    bg2: "#fffbe6",      // 更浅的橙色
    border: "#ffd591",   // 橙色边框
    text: "#d46b08",     // 橙色文字
    label: "思考",
    priority: "secondary",
  },
  interrupted: {
    bg1: "#fff2e8",      // 比thought更深的橙色
    bg2: "#fff",         // 白色背景
    border: "#ffbb96",   // 深橙色边框
    text: "#d4380d",     // 深橙色文字
    label: "中断",
    priority: "primary",
  },

  // ===== 信息类（蓝色系）- 表示进行中的操作 =====
  start: {
    bg1: "#e6f7ff",      // 浅蓝色
    bg2: "#f0f8ff",      // 更浅的蓝色
    border: "#91d5ff",   // 蓝色边框
    text: "#1890ff",     // 蓝色文字
    label: "开始",
    priority: "primary",
  },
  retrying: {
    bg1: "#e6f7ff",      // 与start相同的浅蓝色
    bg2: "#f9f0ff",      // 带点紫色的背景
    border: "#91d5ff",   // 蓝色边框
    text: "#1d39c4",     // 深蓝色文字（与start区分）
    label: "重试",
    priority: "secondary",
  },
  action_tool: {
    bg1: "#e6f7ff",      // 浅蓝色
    bg2: "#f0f5ff",      // 带点紫色的浅蓝色
    border: "#69c0ff",   // 深蓝色边框（比start更深）
    text: "#096dd9",     // 深蓝色文字
    label: "执行",
    priority: "primary",
  },

  // ===== 完成类（绿色系）- 表示成功和完成 =====
  final: {
    bg1: "#f6ffed",      // 浅绿色
    bg2: "#f5f5f5",      // 浅灰色背景
    border: "#b7eb8f",   // 绿色边框
    text: "#52c41a",     // 绿色文字
    label: "完成",
    priority: "primary",
  },
  resumed: {
    bg1: "#f6ffed",      // 与final相同的浅绿色
    bg2: "#f0f5ff",      // 带点蓝色的背景
    border: "#b7eb8f",   // 绿色边框
    text: "#389e0d",     // 深绿色文字（与final区分）
    label: "恢复",
    priority: "secondary",
  },
  observation: {
    bg1: "#e6ffed",      // 比final更深的绿色
    bg2: "#f5fff5",      // 浅绿色背景
    border: "#73d13d",   // 深绿色边框
    text: "#237804",     // 深绿色文字
    label: "观察",
    priority: "secondary",
  },
  report: {
    bg1: "#f6ffed",      // 与final相同的浅绿色
    bg2: "#f5f5f5",      // 浅灰色背景
    border: "#b7eb8f",   // 绿色边框
    text: "#52c41a",     // 绿色文字
    label: "报告",
    priority: "secondary",
  },

  // ===== 错误类（红色系）- 表示错误和失败 =====
  error: {
    bg1: "#fff1f0",      // 浅红色
    bg2: "#fff",         // 白色背景
    border: "#ffa39e",   // 红色边框
    text: "#cf1322",     // 红色文字
    label: "错误",
    priority: "primary",
  },

  // ===== 暂停类（灰色系）- 表示暂停和等待 =====
  paused: {
    bg1: "#fafafa",      // 浅灰色
    bg2: "#f5f5f5",      // 更浅的灰色
    border: "#d9d9d9",   // 灰色边框
    text: "#595959",     // 灰色文字
    label: "暂停",
    priority: "secondary",
  },

  // ===== 内容类（紫色系）- 表示内容片段 =====
  chunk: {
    bg1: "#f9f0ff",      // 浅紫色
    bg2: "#f5f5ff",      // 带点蓝色的紫色
    border: "#d3adf7",   // 紫色边框
    text: "#722ed1",     // 紫色文字
    label: "片段",
    priority: "primary",
  },
};

/**
 * 获取步骤样式 - 主函数
 * @param stepType 步骤类型
 * @param isPrimary 是否为主信息（影响视觉层次）
 * @returns 样式对象
 */
export const getStepStyle = (stepType: StepType, isPrimary: boolean = true) => {
  const scheme = colorSchemes[stepType] || colorSchemes.start;
  
  // 基础样式
  const style = {
    ...baseStyle,
    background: `linear-gradient(135deg, ${scheme.bg1} 0%, ${scheme.bg2} 100%)`,
    border: `1px solid ${scheme.border}`,
    color: scheme.text,
  };

  // 如果是次要信息，调整视觉层次
  if (!isPrimary) {
    return {
      ...style,
      fontSize: 12,
      color: `${scheme.text}cc`,  // 降低不透明度
      fontWeight: 'normal',
    };
  }

  return style;
};

/**
 * 获取步骤标签（用于调试）
 * @param stepType 步骤类型
 * @returns 视觉标签
 */
export const getStepLabel = (stepType: StepType): string => {
  return colorSchemes[stepType]?.label || "未知";
};

/**
 * 检查步骤类型是否有效
 * @param stepType 步骤类型
 * @returns 是否有效
 */
export const isValidStepType = (stepType: string): stepType is StepType => {
  return stepType in colorSchemes;
};

/**
 * 获取所有步骤类型
 * @returns 步骤类型数组
 */
export const getAllStepTypes = (): StepType[] => {
  return Object.keys(colorSchemes) as StepType[];
};

/**
 * 获取步骤优先级
 * @param stepType 步骤类型
 * @returns 优先级（primary/secondary/accent）
 */
export const getStepPriority = (stepType: StepType): 'primary' | 'secondary' | 'accent' => {
  return colorSchemes[stepType]?.priority || 'secondary';
};
