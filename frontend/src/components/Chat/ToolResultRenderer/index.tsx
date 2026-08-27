// 编辑历史: 2026-08-27 小欧 - 重构: 删36套per-tool视图与switch, 改按结果类型(tree/code/generic)分派(铁规复用优先/禁backward/KISS)
/**
 * ToolResultRenderer - 工具结果渲染器(结果类型分派, 非 tool 名)
 *
 * 后端发来的结果为通用字典 + 现成摘要 + tool_name 标签, 无 tool 专属结构约束。
 * 仅 tree(目录树) / code(文件内容) 需形状专属渲染, 其余统一 generic(由 GenericResultRenderer 承担)。
 * 映射见 resultTypes.ts, 仅含后端真实存在的工具名。
 *
 * @author 小欧
 * @since 2026-08-27
 */
import React from 'react';
import { TreeResultRenderer, CodeResultRenderer, DefaultResultRenderer } from './shapeRenderers';
import { resolveResultType } from './resultTypes';

interface ToolResultRendererProps {
  step: import('../../../types/execution').ExecutionStep;
  isExpanded?: boolean;
  toggleExpand?: (index: number) => void;
  stepIndex?: number;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ step }) => {
  // 严禁退化: tool_result 为数组时优先通用渲染(后端08-18契约 data 由 data_text 承载, 专用渲染器解析会空)
  if (step.tool_result && Array.isArray(step.tool_result) && step.tool_result.length) {
    return <DefaultResultRenderer step={step} />;
  }
  const type = resolveResultType(step);
  switch (type) {
    case 'tree':
      return <TreeResultRenderer step={step} />;
    case 'code':
      return <CodeResultRenderer step={step} />;
    default:
      return <DefaultResultRenderer step={step} />;
  }
};

export default React.memo(ToolResultRenderer);
