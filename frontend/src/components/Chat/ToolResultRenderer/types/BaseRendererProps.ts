/**
 * BaseRendererProps - 渲染器基础接口
 * 
 * 所有工具渲染器的基础Props接口
 * 统一接口设计，参考文档6.1节
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import type { ExecutionStep } from "../../../../utils/sse";

/**
 * 基础渲染器属性接口
 * 所有Renderer都应继承此接口
 */
export interface BaseRendererProps {
  /** 执行步骤数据 */
  step: ExecutionStep;
  /** 是否展开状态（可选） */
  isExpanded?: boolean;
  /** 切换展开状态的回调函数（可选） */
  onToggle?: () => void;
  /** 步骤索引（可选，用于onToggle回调） */
  stepIndex?: number;
}

/**
 * 带数据的基础渲染器属性接口
 * 用于从step中提取数据后的View组件
 */
export interface BaseViewProps {
  /** 是否展开状态（可选） */
  isExpanded?: boolean;
  /** 切换展开状态的回调函数（可选） */
  onToggle?: () => void;
}
