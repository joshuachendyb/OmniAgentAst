// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: 抽resolveScheme复用取色; hexToRgba提模块级; 删isDarkMode/darkModeColors死代码
// 2026-08-27 小欧 - 三堂会审: Colors.WARNING 收敛至 AntD5 默认警告色 #faad14(原 #d97706 旧琥珀色, 与第九章调色板不一致)
// 2026-08-27 小欧 - 三堂会审: 删全部死代码(colorSchemes/resolveScheme/hexToRgba/mergeStyles/ColorScheme接口/import React), 仅留6令牌+类型(YAGNI/KISS/禁止backward)
// 2026-08-27 小欧 - 修复step-5/step-6: 恢复getStep*/isValidStepType/getAllStepTypes(被误删), 以最小stepMeta映射替代已删colorSchemes(禁止backward), action_tool须被拒
// 2026-08-28 小沈 - 修复review-bugs#6: isValidStepType改hasOwnProperty, 防toString/__proto__原型污染 - 小沈-2026-08-28
// 2026-08-28 小欧 - 三堂会审v1.3(P0): Colors.TEXT扩5档灰(PRIMARY#595959/SECONDARY#8c8c8c/TERTIARY#999/WEAK#888/STRONG#333), 消灰阶硬码复发(H3); FontSize.SECONDARY 13→12 废13档统一14/12二档(M2) - 小欧-2026-08-28
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
 * @update 2026-08-26 小欧 - 8.4.14(5) StepType action 改名+覆盖7个meta类型+补 colorSchemes 条目
 */

// ==================== 类型定义 ====================

// 步骤类型定义
export type StepType =
  | 'thought'
  | 'start'
  | 'startinfo'
  | 'thought-start'
  | 'usage'
  | 'stats'
  | 'final_stats'
  | 'context_overview'
  | 'truncated'
  | 'final'
  | 'error'
  | 'cancelled'
  | 'paused'
  | 'resumed'
  | 'retrying'
  | 'observation'
  | 'action'
  | 'chunk'
  | 'report';

// 视觉优先级
export type StepPriority = 'primary' | 'secondary' | 'accent';

// 分行模式
export type LayoutMode = 'inline' | 'block' | 'inline-with-details';

// 字体大小规范
// ⚠️ 警告：修改或重命名属性前，请搜索 renderers/ 目录下所有引用（如 FontSize.SM/XS/XXS 过去已被误用过），务必同步更新，否则编译报错（历史教训 2026-05-23）
// 2026-08-28 小欧 v1.3: 废 SECONDARY=13 半档, 统一 14/12 二档(M2); 13px 游离扫视不齐已消除
export const FontSize = {
  // 主要内容字体
  PRIMARY: 14, // 主标题、重要信息（final、error主要内容）
  SECONDARY: 12, // 普通内容（thought、start描述）— v1.3 由13降12, 与TERTIARY同档, 全链仅14/12二档
  TERTIARY: 12, // 辅助信息（时间戳、ID）
  SMALL: 11, // 微小信息（标签、徽章）
  CAPTION: 10, // 注释文字

  // 特殊字体
  CODE: 12, // 代码/路径
  EMOJI: 14, // 表情符号大小
} as const;

// 字重规范
export const FontWeight = {
  BOLD: 600, // 标题、重要标签
  MEDIUM: 500, // 次要标题
  REGULAR: 400, // 普通文字
  LIGHT: 300, // 辅助文字
} as const;

// 间距常量 - 小强 2026-05-22
// ⚠️ 警告：修改或重命名属性前，请搜索 renderers/ 目录下所有引用，务必同步更新（历史教训 2026-05-23）
export const Spacing = {
  XS: 4, // 极小间距
  SM: 6, // 小间距（标准）
  MD: 8, // 中间距
  LG: 12, // 大间距
  XL: 16, // 超大间距
} as const;

// 2026-08-30 小欧 北京老陈最新定案(字体留白全0 + 行高=字号+4): 流水线段距单点——
// 默认(独立 step)=Spacing.SM=6=step 间, compact(step 内文字 4 折不折同)=Spacing.XS=4;
// 字体留白0 + 行高=字号+Spacing.XS(4)，数值一律 Spacing 常量 - 小欧-2026-08-30
export const stepMargin = (compact: boolean): string =>
  `${compact ? Spacing.XS : Spacing.SM}px 0`;

// 边框宽度常量 - 小强 2026-05-22
export const BorderWidth = {
  THIN: 1, // 细边框
  DEFAULT: 1, // 默认边框
  THICK: 2, // 粗边框
} as const;

// 圆角常量 - 小强 2026-05-22
export const Radius = {
  SM: 4, // 小圆角
  DEFAULT: 6, // 默认圆角
  LG: 8, // 大圆角
} as const;

// 颜色常量 - 语义化功能色 + 文字/背景/边框中性色
export const Colors = {
  // 文字颜色（5种浅色灰阶，v1.3 扩档消硬码 H3）
  TEXT: {
    PRIMARY: '#595959', // 主要文字 - 中灰（标题/正文）
    SECONDARY: '#8c8c8c', // 次要文字 - 浅灰（参数/说明）— v1.3 由#595959降#8c8c8c, 与PRIMARY拉开层级
    TERTIARY: '#999999', // 辅助文字 - 浅灰
    WEAK: '#888888', // 弱文字 - 空态/斜体
    STRONG: '#333333', // 强文字 - 文件名/重点（替代硬码#333/#262626）
  },
  // 背景颜色（3种浅色）
  BG: {
    PRIMARY: '#ffffff', // 主背景 - 白色
    SECONDARY: '#fafafa', // 次要背景 - 极浅灰
    TERTIARY: '#f5f5f5', // 第三背景 - 浅灰
    LIGHT: '#fafafa', // 浅背景（别名）
    WARNING_LIGHT: '#fffbe6', // 警告浅底（高亮背景，替 rgba）
  },
  // 边框颜色（3种浅色）
  BORDER: {
    LIGHT: '#f0f0f0', // 浅边框-水平分割线
    VERTICAL: '#e8e8e8', // 垂直左线（Pipeline/通用嵌套统一）
    DEFAULT: '#d9d9d9', // 中边框（通用嵌套旧值，逐步收敛至 VERTICAL）
    STRONG: '#bfbfbf', // 深边框（仍是浅色）
  },
  // 功能颜色（5种）
  PRIMARY: '#1677ff', // 主色调 - 蓝色
  SUCCESS: '#52c41a', // 成功状态 - 绿色
  ERROR: '#ff4d4f', // 错误状态 - 红色
  WARNING: '#faad14', // 警告/思考状态 - 橙色(AntD5默认警告色, 收敛)
  INFO: '#096dd9', // 信息/开始状态 - 蓝色
  WARNING_BG: '#fffbe6', // 警告背景（高亮浅底）
} as const;

// ==================== 步骤配置 ====================
// 2026-08-27 小欧 三堂会审: 已移除全部死代码(colorSchemes/getStep*/resolveScheme/hexToRgba/mergeStyles 等),
// 仅 stepStyles.test.ts 引用, src(renderers) 只用上方 6 个令牌与类型(YAGNI/KISS/禁止backward)

// 2026-08-27 小欧 修复step-6: 最小 stepMeta 映射(仅 label/priority/layout), 供下方 getStep* 使用;
// 不再复活已删的彩虹 colorSchemes(禁止backward)。键集合须与 StepType 完全一致。
interface StepMeta {
  label: string;
  priority: StepPriority;
  layout: LayoutMode;
}

const stepMeta: Record<StepType, StepMeta> = {
  thought: { label: '💭 思考', priority: 'secondary', layout: 'block' },
  start: {
    label: '🚀 开始',
    priority: 'primary',
    layout: 'inline-with-details',
  },
  startinfo: { label: '🚀 开始信息', priority: 'secondary', layout: 'inline' },
  'thought-start': {
    label: '💭 开始思考',
    priority: 'secondary',
    layout: 'block',
  },
  usage: { label: '🔢 Token', priority: 'secondary', layout: 'inline' },
  stats: { label: '📊 统计', priority: 'secondary', layout: 'inline' },
  final_stats: {
    label: '📊 最终统计',
    priority: 'secondary',
    layout: 'inline',
  },
  context_overview: {
    label: '📑 上下文概览',
    priority: 'secondary',
    layout: 'inline',
  },
  truncated: { label: '✂️ 截断', priority: 'secondary', layout: 'inline' },
  final: { label: '✅ 完成', priority: 'primary', layout: 'block' },
  error: { label: '❌ 错误', priority: 'primary', layout: 'block' },
  cancelled: { label: '⚠️ 已取消', priority: 'primary', layout: 'block' },
  paused: { label: '⏸️ 暂停', priority: 'secondary', layout: 'inline' },
  resumed: { label: '▶️ 恢复', priority: 'secondary', layout: 'inline' },
  retrying: { label: '🔄 重试', priority: 'secondary', layout: 'inline' },
  observation: {
    label: '📋 观察',
    priority: 'secondary',
    layout: 'inline-with-details',
  },
  action: {
    label: '⚙️ 执行',
    priority: 'primary',
    layout: 'inline-with-details',
  },
  chunk: { label: '📝 内容', priority: 'primary', layout: 'block' },
  report: {
    label: '📊 报告',
    priority: 'secondary',
    layout: 'inline-with-details',
  },
};

// 2026-08-27 小欧 修复step-5: action_tool 不在 stepMeta 键集合中, isValidStepType 必返回 false(8.4.2 禁止 backward)
// 2026-08-28 小沈 修复B6: 改hasOwnProperty.call, 只检查自有属性, 避免toString/__proto__原型污染命中
export const isValidStepType = (stepType: string): stepType is StepType => {
  return Object.prototype.hasOwnProperty.call(stepMeta, stepType);
};

export const getAllStepTypes = (): StepType[] => {
  return Object.keys(stepMeta) as StepType[];
};

export const getStepLabel = (stepType: StepType | string): string => {
  return isValidStepType(stepType) ? stepMeta[stepType].label : '未知';
};

export const getStepPriority = (stepType: StepType | string): StepPriority => {
  return isValidStepType(stepType) ? stepMeta[stepType].priority : 'secondary';
};

export const getStepLayout = (stepType: StepType | string): LayoutMode => {
  return isValidStepType(stepType) ? stepMeta[stepType].layout : 'block';
};

// 2026-08-27 小欧 修复step-6: block 布局需换行; inline-with-details 支持展开详情
export const shouldBreakLine = (stepType: StepType | string): boolean => {
  return getStepLayout(stepType) === 'block';
};

export const hasExpandableDetails = (stepType: StepType | string): boolean => {
  return getStepLayout(stepType) === 'inline-with-details';
};
