// 编辑历史: 2026-08-26 小欧 - 修复B1: DefaultRenderer优先读step.tool_result(4.9.3),兜底execution_result
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.7 收窄object再取.data + 8.4.6 extractToolResult共享
/**
 * DefaultRenderer - 默认工具结果渲染器（第13章设计方案改造）
 *
 * 当tool_name未知时，显示原始JSON数据
 * 使用GenericResultRenderer统一渲染
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 */

import React from 'react';
import { GenericResultRenderer } from '@/components/Chat/renderers';
import { BaseRendererProps } from './BaseRendererProps';
import type { ExecutionStep } from '../../../../utils/sse';

interface DefaultRendererProps extends BaseRendererProps {}

// 2026-08-27 小欧 三堂会审: 共享提取原始tool_result/execution_result/content对象, 供default分支使用(DRY)
const extractToolResult = (step: ExecutionStep): unknown => {
  const tr = (step as { tool_result?: unknown }).tool_result;
  if (tr != null) return tr;
  const er = (step as { execution_result?: unknown }).execution_result;
  if (er != null) return er;
  return (step as { content?: unknown }).content;
};

const DefaultRenderer: React.FC<DefaultRendererProps> = ({ step }) => {
  // 【小欧 2026-08-26 修复 B1】4.9.3：优先读 obsStep.tool_result(新数组)，其次 execution_result
  // 2026-08-27 小欧 三堂会审: 经extractToolResult取原始值, 收窄object再取.data(#7)
  const raw = extractToolResult(step);
  const data =
    (typeof raw === 'object' && raw !== null
      ? (raw as Record<string, unknown>).data
      : raw) ?? (raw as Record<string, unknown>); // 2026-08-27 小欧 三堂会审: 收窄取.data

  if (!data) {
    return null;
  }

  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};

export default React.memo(DefaultRenderer);
