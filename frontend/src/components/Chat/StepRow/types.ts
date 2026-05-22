/**
 * StepRow 类型定义
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import type { ExecutionStep } from "../../../utils/sse";

/**
 * StepRow组件props接口
 */
export interface StepRowProps {
  step: ExecutionStep;
  taskId?: string;
  stepIndex?: number;
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
}

/**
 * StepHeader组件props接口
 */
export interface StepHeaderProps {
  step: ExecutionStep;
  stepIndex: number;
  expandedSteps: Map<number, boolean>;
  badgeStyle: React.CSSProperties;
  labelStyle: React.CSSProperties;
  label: string;
  icon: string;
}

/**
 * StepContent组件props接口
 */
export interface StepContentProps {
  step: ExecutionStep;
  stepIndex: number;
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
  contentStyle: React.CSSProperties;
}

/**
 * StepFooter组件props接口
 */
export interface StepFooterProps {
  step: ExecutionStep;
  hasMore: boolean;
  onLoadMore: () => void;
}
