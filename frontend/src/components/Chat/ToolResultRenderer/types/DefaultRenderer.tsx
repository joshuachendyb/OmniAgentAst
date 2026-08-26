// 编辑历史: 2026-08-26 小欧 - 修复B1: DefaultRenderer优先读step.tool_result(4.9.3),兜底execution_result
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

interface DefaultRendererProps extends BaseRendererProps {}

const DefaultRenderer: React.FC<DefaultRendererProps> = ({ step }) => {
  // 【小欧 2026-08-26 修复 B1】4.9.3：优先读 obsStep.tool_result(新数组)，其次 execution_result
  const raw =
    (step as { tool_result?: unknown }).tool_result ??
    (step as { execution_result?: unknown }).execution_result;
  const data =
    (raw as Record<string, unknown>)?.data || (raw as Record<string, unknown>);

  if (!data) {
    return null;
  }

  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};

export default React.memo(DefaultRenderer);
