// 编辑历史: 2026-08-27 小欧 - 重构: 删36套per-tool视图与switch, 改按结果类型(tree/code/generic)分派(铁规复用优先/禁backward/KISS)
// 编辑历史: 2026-08-27 小欧 - 修复chat-A: 按结果类型(tree/code)分派专属渲染, 破除 tool_result 数组早退致目录树/代码块永远不可达
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
import {
  TreeResultRenderer,
  CodeResultRenderer,
  DefaultResultRenderer,
} from './shapeRenderers';
import { resolveResultType } from './resultTypes';

// 2026-08-27 小欧 三堂会审C10: 删未使用Props(isExpanded/toggleExpand/stepIndex), 调用方仅传step
interface ToolResultRendererProps {
  step: import('../../../../types/execution').ExecutionStep;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ step }) => {
  // 2026-08-27 小欧 修复: 按结果类型(tree/code)分派专属渲染, 命中 tree/code 即走 TreeResultRenderer/CodeResultRenderer;
  // 未命中专属形状(绝大多数 generic)才走 DefaultResultRenderer, 数据由 tool_result 数组承载(BUG-A 不退化)
  const type = resolveResultType(step);
  if (type === 'tree') return <TreeResultRenderer step={step} />;
  if (type === 'code') return <CodeResultRenderer step={step} />;
  return <DefaultResultRenderer step={step} />;
};

export default React.memo(ToolResultRenderer);
