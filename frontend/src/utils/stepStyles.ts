/**
 * 步骤样式工具 - 统一管理所有步骤类型的视觉样式
 *
 * 功能：提供统一的样式函数，支持TypeScript类型检查
 * 设计原则：视觉层次清晰、颜色语义明确、分行规则统一
 *
 * @author 小强
 * @version 2.0.1
 * @since 2026-03-24
 */

import React from 'react';

// ==================== 类型定义 ====================

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

// 视觉优先级
export type StepPriority = 'primary' | 'secondary' | 'accent';

// 分行模式
export type LayoutMode = 'inline' | 'block' | 'inline-with-details';

// 颜色方案接口
interface ColorScheme {
  bg1: string;          // 渐变起始颜色
  bg2: string;          // 渐变结束颜色
  border: string;       // 边框颜色
  text: string;         // 主文字颜色
  textSecondary: string; // 次要文字颜色
  label: string;        // 视觉标签
  priority: StepPriority;
  layout: LayoutMode;   // 分行模式
}

// 字体大小规范
export const FontSize = {
  // 主要内容字体
  PRIMARY: 14,          // 主标题、重要信息（final、error主要内容）
  SECONDARY: 13,        // 普通内容（thought、start描述）
  TERTIARY: 12,         // 辅助信息（时间戳、ID）
  SMALL: 11,            // 微小信息（标签、徽章）
  CAPTION: 10,          // 注释文字
  
  // 特殊字体
  CODE: 12,             // 代码/路径
  EMOJI: 14,            // 表情符号大小
} as const;

// 字重规范
export const FontWeight = {
  BOLD: 600,            // 标题、重要标签
  MEDIUM: 500,          // 次要标题
  REGULAR: 400,         // 普通文字
  LIGHT: 300,           // 辅助文字
} as const;

// 颜色常量（用于非步骤元素）
export const Colors = {
  // 文字颜色层次
  TEXT: {
    PRIMARY: '#262626',     // 主要文字
    SECONDARY: '#595959',   // 次要文字
    TERTIARY: '#8c8c8c',    // 辅助文字
    DISABLED: '#bfbfbf',    // 禁用状态
    INVERSE: '#fff',        // 反色文字
  },
  
  // 背景颜色层次
  BG: {
    PRIMARY: '#fff',        // 主背景
    SECONDARY: '#fafafa',   // 次要背景
    TERTIARY: '#f5f5f5',    // 第三背景
    HOVER: '#f0f0f0',       // 悬停背景
  },
  
  // 边框颜色
  BORDER: {
    LIGHT: '#f0f0f0',
    DEFAULT: '#d9d9d9',
    STRONG: '#8c8c8c',
  },
  
  // 功能颜色
  SUCCESS: '#52c41a',
  WARNING: '#faad14',
  ERROR: '#ff4d4f',
  INFO: '#1890ff',
} as const;

// ==================== 步骤配置 ====================

// 精细化颜色方案映射 - 每个步骤都有独特的视觉语义和分行规则
const colorSchemes: Record<StepType, ColorScheme> = {
  // ===== 思考类（橙色系）- 表示思考和警告 =====
   thought: {
     bg1: "#fff7e6",
     bg2: "#fffbe6",
     border: "#ffd591",
     text: "#ad4e00", // 改为更深橙色，提高可读性
     textSecondary: "#8c6e2f",
     label: "💭 分析",
     priority: "secondary",
     layout: "block",  // 思考内容需要换行显示
   },
  interrupted: {
    bg1: "#fff2e8",
    bg2: "#fff",
    border: "#ffbb96",
    text: "#d4380d",
    textSecondary: "#ad4e26",
    label: "⚠️ 中断",
    priority: "primary",
    layout: "block",  // 中断信息需要醒目显示
  },

  // ===== 信息类（蓝色系）- 表示进行中的操作 =====
  start: {
    bg1: "#e6f7ff",
    bg2: "#f0f8ff",
    border: "#91d5ff",
    text: "#0050b3", // 改为更深蓝色，提高可读性
    textSecondary: "#003a8c",
    label: "🚀 开始",
    priority: "primary",
    layout: "inline-with-details",  // 标题一行，详情可以展开
  },
  retrying: {
    bg1: "#e6f7ff",
    bg2: "#f9f0ff",
    border: "#91d5ff",
    text: "#1d39c4",
    textSecondary: "#597ef7",
    label: "🔄 重试",
    priority: "secondary",
    layout: "inline",  // 重试信息简短，一行显示
  },
  action_tool: {
    bg1: "#e6f7ff",
    bg2: "#f0f5ff",
    border: "#69c0ff",
    text: "#003a8c", // 改为更深蓝色，提高可读性
    textSecondary: "#0050b3",
    label: "⚙️ 执行",
    priority: "primary",
    layout: "inline-with-details",  // 工具名一行，参数可展开
  },

  // ===== 完成类（绿色系）- 表示成功和完成 =====
  final: {
    bg1: "#f6ffed",
    bg2: "#f5f5f5",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#52c41a",
    label: "✅ 完成",
    priority: "primary",
    layout: "block",  // 完成信息可能较长，需要换行
  },
  resumed: {
    bg1: "#f6ffed",
    bg2: "#f0f5ff",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#237804", // 【老杨修复 2026-03-25】提升对比度：#73d13d → #237804 (WCAG 4.5:1)
    label: "▶️ 恢复",
    priority: "secondary",
    layout: "inline",  // 恢复信息简短，一行显示
  },
  observation: {
    bg1: "#e6ffed",
    bg2: "#f5fff5",
    border: "#73d13d",
    text: "#237804",
    textSecondary: "#389e0d",
    label: "📋 观察",
    priority: "secondary",
    layout: "inline-with-details",  // 观察摘要一行，详细可展开
  },
  report: {
    bg1: "#f6ffed",
    bg2: "#f5f5f5",
    border: "#b7eb8f",
    text: "#52c41a",
    textSecondary: "#237804", // 【老杨修复 2026-03-25】提升对比度：#73d13d → #237804 (WCAG 4.5:1)
    label: "📊 报告",
    priority: "secondary",
    layout: "inline",  // 报告标签和路径一行显示，不分行
  },

  // ===== 错误类（红色系）- 表示错误和失败 =====
  error: {
    bg1: "#fff1f0",
    bg2: "#fff",
    border: "#ffa39e",
    text: "#cf1322",
    textSecondary: "#a8071a", // 【老杨修复 2026-03-25】提升对比度：#ff6b6b → #a8071a (WCAG 6.2:1)
    label: "❌ 错误",
    priority: "primary",
    layout: "block",  // 错误信息需要醒目显示
  },

  // ===== 暂停类（灰色系）- 表示暂停和等待 =====
  paused: {
    bg1: "#fafafa",
    bg2: "#f5f5f5",
    border: "#d9d9d9",
    text: "#595959",
    textSecondary: "#8c8c8c",
    label: "⏸️ 暂停",
    priority: "secondary",
    layout: "inline",  // 暂停信息简短，一行显示
  },

  // ===== 内容类（紫色系）- 表示内容片段 =====
  chunk: {
    bg1: "#f9f0ff",
    bg2: "#f5f5ff",
    border: "#d3adf7",
    text: "#722ed1",
    textSecondary: "#531dab", // 【老杨修复 2026-03-25】提升对比度：#b37feb → #531dab (WCAG 5.8:1)
    label: "📝 内容",
    priority: "primary",
    layout: "block",  // 内容片段需要换行显示
  },
};

// ==================== 核心函数 ====================

/**
 * 获取步骤容器样式
 * @param stepType 步骤类型
 * @param isPrimary 是否为主信息
 * @returns CSS样式对象
 */
export const getStepStyle = (stepType: StepType | string, isPrimary: boolean = true) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  const baseStyle = {
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: isPrimary ? FontSize.SECONDARY : FontSize.TERTIARY,
    lineHeight: 1.8,
  };
  
  const style = {
    ...baseStyle,
    background: `linear-gradient(135deg, ${scheme.bg1} 0%, ${scheme.bg2} 100%)`,
    border: `1px solid ${scheme.border}`,
    color: scheme.text,
  };

  return style;
};

/**
 * 获取标题样式（用于步骤标题行）
 * @param stepType 步骤类型
 * @returns CSS样式对象
 */
export const getStepTitleStyle = (stepType: StepType | string) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  return {
    fontWeight: FontWeight.BOLD,
    color: scheme.text,
    fontSize: FontSize.SECONDARY,
    marginBottom: 4,
  };
};

/**
 * 获取主要内容样式（用于步骤主内容）
 * @param stepType 步骤类型
 * @param variant 内容变体
 * @returns CSS样式对象
 */
export const getStepContentStyle = (
  stepType: StepType | string, 
  variant: 'primary' | 'secondary' | 'detail' = 'primary'
) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  const variants = {
    primary: {
      fontSize: FontSize.SECONDARY,
      color: scheme.text,
      fontWeight: FontWeight.REGULAR,
    },
    secondary: {
      fontSize: FontSize.TERTIARY,
      color: scheme.textSecondary,
      fontWeight: FontWeight.REGULAR,
    },
    detail: {
      fontSize: FontSize.SMALL,
      color: Colors.TEXT.TERTIARY,
      fontWeight: FontWeight.LIGHT,
    },
  };
  
  return variants[variant];
};

/**
 * 获取标签样式（用于步骤标签显示）
 * @param stepType 步骤类型
 * @returns CSS样式对象
 */
export const getStepLabelStyle = (stepType: StepType | string) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  return {
    display: 'inline-flex' as const,
    alignItems: 'center' as const,
    gap: 4,
    padding: '2px 8px',
    borderRadius: 4,
    backgroundColor: `${scheme.bg1}`,
    color: scheme.text,
    fontSize: FontSize.TERTIARY, // 增大字体大小，提高可读性
    fontWeight: FontWeight.MEDIUM,
    border: `1px solid ${scheme.border}`,
  };
};

/**
 * 获取徽章样式（用于步骤编号、计数等）
 * @param stepType 步骤类型
 * @param variant 徽章变体
 * @returns CSS样式对象
 */
export const getStepBadgeStyle = (
  stepType: StepType | string,
  variant: 'default' | 'outline' = 'default'
) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  if (variant === 'outline') {
    return {
      padding: '1px 6px',
      borderRadius: 4,
      fontSize: FontSize.CAPTION,
      fontWeight: FontWeight.MEDIUM,
      color: scheme.text,
      border: `1px solid ${scheme.border}`,
      backgroundColor: 'transparent',
    };
  }
  
  return {
    padding: '1px 6px',
    borderRadius: 4,
    fontSize: FontSize.CAPTION,
    fontWeight: FontWeight.MEDIUM,
    color: Colors.TEXT.INVERSE,
    backgroundColor: scheme.text,
  };
};

/**
 * 获取详情展开样式（用于可折叠的详细信息）
 * @param stepType 步骤类型
 * @returns CSS样式对象
 */
export const getStepDetailStyle = (stepType: StepType | string) => {
  const scheme = (isValidStepType(stepType) ? colorSchemes[stepType] : colorSchemes.start) || colorSchemes.start;
  
  return {
    marginTop: 6,
    padding: '6px 10px',
    borderRadius: 4,
    backgroundColor: `${scheme.bg1}20`, // 20% opacity
    border: `1px solid ${scheme.border}`,
    fontSize: FontSize.CODE,
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
    color: scheme.textSecondary,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap' as const,
    wordBreak: 'break-word' as const,
  };
};

// ==================== 新增样式函数（设计文档第4章要求） ====================

/**
 * 时间戳样式 - 醒目版本，放在行右侧
 * 统一使用深灰色字体，浅色背景，对比强烈
 * @param stepType 步骤类型
 * @returns CSS样式对象
 */
export const getTimestampStyle = (stepType: StepType): React.CSSProperties => {
  const scheme = colorSchemes[stepType] || colorSchemes.start;
  
  // 转换十六进制颜色为rgba格式，添加透明度
  const hexToRgba = (hex: string, alpha: number): string => {
    // 移除#号
    const cleanHex = hex.replace('#', '');
    // 解析RGB值
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };
  
  return {
    marginLeft: "auto",              // 靠右对齐
    padding: '3px 10px',             // 增加内边距
    borderRadius: 6,                 // 圆角
    backgroundColor: scheme.bg1,     // 步骤类型的浅色背景（保持各类型特色）
    border: `1px solid ${hexToRgba(scheme.border, 0.38)}`,  // 步骤类型的边框，带透明度
    color: '#333333',                // 统一深灰色字体，对比强烈
    fontSize: FontSize.TERTIARY,     // 12px
    fontWeight: FontWeight.BOLD,     // 加粗
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',  // 轻微阴影
  };
};

/**
 * 下一步信息样式
 * @param stepType 步骤类型
 * @returns CSS样式对象
 */
export const getNextStepStyle = (stepType: StepType): React.CSSProperties => {
  const scheme = colorSchemes[stepType] || colorSchemes.start;
  
  // 转换十六进制颜色为rgba格式，添加透明度
  const hexToRgba = (hex: string, alpha: number): string => {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };
  
  return {
    marginTop: 6,
    padding: '6px 10px',
    borderRadius: 4,
    backgroundColor: hexToRgba(scheme.bg1, 0.19),  // 约30%透明度
    border: `1px solid ${hexToRgba(scheme.border, 0.25)}`,  // 约40%透明度
    fontSize: FontSize.TERTIARY,
    color: scheme.text,
    fontWeight: FontWeight.MEDIUM,
  };
};

/**
 * 状态徽章样式
 * @param status 成功或失败状态
 * @returns CSS样式对象
 */
export const getStatusBadgeStyle = (status: 'success' | 'error'): React.CSSProperties => {
  const isSuccess = status === 'success';
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    borderRadius: 4,
    backgroundColor: isSuccess ? '#f6ffed' : '#fff1f0',
    color: isSuccess ? '#52c41a' : '#ff4d4f',
    fontSize: FontSize.TERTIARY,
    fontWeight: FontWeight.MEDIUM,
    border: `1px solid ${isSuccess ? '#b7eb8f' : '#ffa39e'}`,
  };
};

/**
 * 结束徽章样式
 * @returns CSS样式对象
 */
export const getFinishedBadgeStyle = (): React.CSSProperties => {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '4px 12px',
    borderRadius: 6,
    backgroundColor: '#f6ffed',
    color: '#52c41a',
    fontSize: FontSize.TERTIARY,
    fontWeight: FontWeight.BOLD,
    border: '1px solid #b7eb8f',
    boxShadow: '0 2px 4px rgba(82,196,26,0.1)',
  };
};

// ==================== 辅助函数 ====================

/**
 * 获取步骤标签文本
 * @param stepType 步骤类型
 * @returns 标签文本（含emoji）
 */
export const getStepLabel = (stepType: StepType | string): string => {
  return isValidStepType(stepType) ? colorSchemes[stepType]?.label || "未知" : "未知";
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
 * @returns 优先级
 */
export const getStepPriority = (stepType: StepType | string): StepPriority => {
  return isValidStepType(stepType) ? colorSchemes[stepType]?.priority || 'secondary' : 'secondary';
};

/**
 * 获取分行模式
 * @param stepType 步骤类型
 * @returns 分行模式
 */
export const getStepLayout = (stepType: StepType | string): LayoutMode => {
  return isValidStepType(stepType) ? colorSchemes[stepType]?.layout || 'block' : 'block';
};

/**
 * 判断是否应该换行显示
 * @param stepType 步骤类型
 * @returns 是否应该换行
 */
export const shouldBreakLine = (stepType: StepType | string): boolean => {
  const layout = getStepLayout(stepType);
  return layout === 'block';
};

/**
 * 判断是否支持展开详情
 * @param stepType 步骤类型
 * @returns 是否支持展开
 */
export const hasExpandableDetails = (stepType: StepType | string): boolean => {
  const layout = getStepLayout(stepType);
  return layout === 'inline-with-details';
};

/**
 * 合并样式（用于自定义覆盖）
 * @param baseStyle 基础样式
 * @param overrides 覆盖样式
 * @returns 合并后的样式
 */
export const mergeStyles = (
  baseStyle: React.CSSProperties,
  overrides: React.CSSProperties
): React.CSSProperties => {
  return { ...baseStyle, ...overrides };
};
