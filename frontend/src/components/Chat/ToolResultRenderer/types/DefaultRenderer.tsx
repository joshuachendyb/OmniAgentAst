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
  const execResult = step.execution_result;
  const data =
    (execResult as Record<string, unknown>)?.data ||
    (execResult as Record<string, unknown>);

  if (!data) {
    return null;
  }

  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};

export default React.memo(DefaultRenderer);
