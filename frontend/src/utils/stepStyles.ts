/**
 * 步骤样式工具 - 统一管理所有步骤类型的视觉样式
 *
 * 功能：提供统一的样式函数，支持TypeScript类型检查
 * 设计原则：视觉层次清晰、颜色语义明确、分行规则统一
 *
 * @author 小强
 * @version 2.1.0
 * @since 2026-03-24
 * @update 2026-04-28 小强 - 第七步添加深色模式支持
 */

import React from 'react';

/**
 * 检测深色模式（第七步实现）
 * @returns true表示深色模式，false表示浅色模式
 */
export const isDarkMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
};

/**
 * 深色模式配色 - 9种浅色方案精简版
 * 设计原则：3种色系×3种深浅=9种浅色，绝对不用深色
 * 兼容说明：保留StepRow组件需要的临时属性，后续框层合并时删除
 */
export const darkModeColors = {
  // 基础3色（容器/边框/文字）
  container: '#1f1f1f',
  border: '#404040',
  text: '#e5e5e5',
  // 扩展色（保留必要区分度）
  success: '#52c41a',
  error: '#cf1322',
  warning: '#d97706',
  // StepRow临时使用的属性（后续框层合并时删除）
  headerBg: '#2a2a2a',
  contentBg: '#141414',
  footerBg: '#1a1a1a',
  hoverBorder: '#595959',
};

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
  | 'report'
  | 'incident';

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

// 颜色常量 - 9种浅色方案精简版
// 设计原则：3种色系×3种深浅=9种浅色，绝对不用深色，禁止到处框框色块
export const Colors = {
  // 文字颜色（3种浅色）
  TEXT: {
    PRIMARY: '#262626',     // 主要文字 - 浅灰
    SECONDARY: '#595959',   // 次要文字 - 中灰
    TERTIARY: '#999999',    // 辅助文字 - 深灰（仍是浅色）
  },
  // 背景颜色（3种浅色）
  BG: {
    PRIMARY: '#ffffff',    // 主背景 - 白色
    SECONDARY: '#fafafa',  // 次要背景 - 极浅灰
    TERTIARY: '#f5f5f5',   // 第三背景 - 浅灰
  },
  // 边框颜色（3种浅色）
  BORDER: {
    LIGHT: '#f0f0f0',    // 浅边框
    DEFAULT: '#d9d9d9',    // 中边框
    STRONG: '#bfbfbf',    // 深边框（仍是浅色）
  },
  // 功能颜色（4种）
  SUCCESS: '#52c41a',        // 成功状态 - 绿色
  ERROR: '#ff4d4f',          // 错误状态 - 红色
  WARNING: '#d97706',        // 警告/思考状态 - 橙色
  INFO: '#096dd9',          // 信息/开始状态 - 蓝色
} as const;

// ==================== 步骤配置 ====================

// 精细化颜色方案映射 - 统一为3种主色调：灰/绿/橙
const colorSchemes: Record<StepType, ColorScheme> = {
  // ===== 思考类（橙色系）=====
  thought: {
    bg1: "#fff7e6",
    bg2: "#fffbe6",
    border: "#ffd591",
    text: "#ad4e00",
    textSecondary: "#7a4a00",
    label: "💭 思考",
    priority: "secondary",
    layout: "block",
  },
  incident: {
    bg1: "#fff7e6",
    bg2: "#fffbe6",
    border: "#ffd591",
    text: "#ad4e00",
    textSecondary: "#7a4a00",
    label: "🔧 处理中",
    priority: "secondary",
    layout: "block",
  },
  interrupted: {
    bg1: "#fff2e8",
    bg2: "#fff",
    border: "#ffbb96",
    text: "#d4380d",
    textSecondary: "#ad4e26",
    label: "⚠️ 中断",
    priority: "primary",
    layout: "block",
  },

  // ===== 基础类（灰色系）=====
  start: {
    bg1: "#fafafa",
    bg2: "#f5f5f5",
    border: "#d9d9d9",
    text: "#262626",
    textSecondary: "#595959",
    label: "🚀 开始",
    priority: "primary",
    layout: "inline-with-details",
  },
  retrying: {
    bg1: "#f5f5f5",
    bg2: "#f0f0f0",
    border: "#d9d9d9",
    text: "#595959",
    textSecondary: "#8c8c8c",
    label: "🔄 重试",
    priority: "secondary",
    layout: "inline",
  },
  action_tool: {
    bg1: "#f5f5f5",
    bg2: "#fafafa",
    border: "#d9d9d9",
    text: "#262626",
    textSecondary: "#595959",
    label: "⚙️ 执行",
    priority: "primary",
    layout: "inline-with-details",
  },

  // ===== 完成类（绿色系）=====
  final: {
    bg1: "#f6ffed",
    bg2: "#f5f5f5",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#52c41a",
    label: "✅ 完成",
    priority: "primary",
    layout: "block",
  },
  resumed: {
    bg1: "#f6ffed",
    bg2: "#f5f5f5",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#237804",
    label: "▶️ 恢复",
    priority: "secondary",
    layout: "inline",
  },
  observation: {
    bg1: "#f6ffed",
    bg2: "#f5fff5",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#52c41a",
    label: "📋 观察",
    priority: "secondary",
    layout: "inline-with-details",
  },
  report: {
    bg1: "#f6ffed",
    bg2: "#f5f5f5",
    border: "#b7eb8f",
    text: "#389e0d",
    textSecondary: "#52c41a",
    label: "📊 报告",
    priority: "secondary",
    layout: "inline-with-details",
  },

  // ===== 错误类（红色系）=====
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
    background: scheme.bg1,
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
    padding: '3px 10px',     // 【小强修复 2026-04-14】与时间戳统一高度
    borderRadius: 6,        // 【小强修复 2026-04-14】与时间戳统一圆角
    backgroundColor: `${scheme.bg1}`,
    color: scheme.text,
    fontSize: FontSize.TERTIARY, // 增大字体大小，提高可读性
    fontWeight: FontWeight.MEDIUM,
    // 【小强修复 2026-04-14】去掉边框，更简洁
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',  // 【小强修复 2026-04-14】与时间戳统一阴影
  };
};

/**
 * 获取徽章样式（用于步骤编号、计数等）
 * 2026-04-28 小强修改：第二步实现渐变badge（设计文档3.2节要求）
 * @param stepType 步骤类型
 * @param variant 徽章变体
 * @returns CSS样式对象
 */
export const getStepBadgeStyle = (
  stepType: StepType | string,
  variant: 'default' | 'outline' = 'default'
) => {
  // 渐变色映射表（设计文档3.2节要求）
  const gradientBg: Record<string, string> = {
    start: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)',
    thought: 'linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%)',
    action_tool: 'linear-gradient(135deg, #f9f0ff 0%, #d3adf7 100%)',
    observation: 'linear-gradient(135deg, #e6fffb 0%, #87e8de 100%)',
    final: 'linear-gradient(135deg, #f6ffed 0%, #b7eb8f 100%)',
    error: 'linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%)',
    interrupted: 'linear-gradient(135deg, #fff2e8 0%, #ffbb96 100%)',
    paused: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)',
    resumed: 'linear-gradient(135deg, #f6ffed 0%, #b7eb8f 100%)',
    retrying: 'linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%)',
    incident: 'linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%)',
    report: 'linear-gradient(135deg, #f6ffed 0%, #b7eb8f 100%)',
  };
  
  // 文字颜色映射表
  const textColor: Record<string, string> = {
    start: '#096dd9',
    thought: '#d97706',
    action_tool: '#722ed1',
    observation: '#08979c',
    final: '#389e0d',
    error: '#cf1322',
    interrupted: '#d4380d',
    paused: '#096dd9',
    resumed: '#389e0d',
    retrying: '#cf1322',
    incident: '#d97706',
    report: '#389e0d',
  };
  
  const validType = isValidStepType(stepType) ? stepType : 'start';
  const gradient = gradientBg[validType] || gradientBg.start;
  const color = textColor[validType] || textColor.start;
  
  if (variant === 'outline') {
    return {
      padding: '4px 10px',
      borderRadius: 6,
      fontSize: FontSize.TERTIARY,
      fontWeight: FontWeight.BOLD,
      color: color,
      border: '1.5px solid ' + color,
      backgroundColor: 'transparent',
    };
  }
  
  // 渐变badge样式（第二步实现）
  return {
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: FontSize.TERTIARY,
    fontWeight: FontWeight.BOLD,
    color: color,
    background: gradient,
    border: '1px solid transparent',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
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
  
  return {
    marginLeft: "auto",              // 靠右对齐
    padding: '3px 10px',             // 增加内边距
    borderRadius: 6,                 // 圆角
    backgroundColor: scheme.bg1,     // 步骤类型的浅色背景（保持各类型特色）
    // 【小强修复 2026-04-14】去掉边框，更简洁
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
