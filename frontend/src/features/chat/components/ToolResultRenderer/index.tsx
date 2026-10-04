// 编辑历史: 2026-08-27 小欧 - 重构: 删36套per-tool视图与switch, 改按结果类型(tree/code/generic)分派(铁规复用优先/禁backward/KISS)
// 编辑历史: 2026-10-04 小欧 - 文档[8]第六章第1/2/4条: 删形状分派, 统一 generic — 三条依据:
//   1(目录恒显"目录为空"): TreeResultRenderer 要的 data.entries/data.tree 永远拿不到 —— data_text 是喂LLM的展示文本非JSON(实测 0/2306 可解析), 只能兜底成 content;
//   2(统计数字显示不出/[object Object]): metrics 的值是 {value,text} 对象, 被当 number 用 → 比较恒假或字符串化;
//   4(展开的工具标题显示错): 分派依据 step.tool_name, 而并行时它只取 tool_result[0].tool_name(文档[8]§2.1) → 展开 bash 却显"读取文件成功"。
//   三者同源: 按 tool 名/形状分派的前提(结构化 data)根本不存在。KISS-DIRECT: 一律 generic, 不再分派。
/**
 * ToolResultRenderer - 工具结果渲染器(统一 generic)
 *
 * 取数优先级: tool_result 数组 → execution_result → content。
 * 渲染交 GenericResultRenderer(它按值类型递归渲染: 字符串/数字/数组/对象)。
 *
 * @author 小欧
 * @since 2026-08-27
 */
import React from 'react';
import { GenericResultRenderer } from '@/features/chat/components/renderers';
import type { ExecutionStep } from '../../../../types/execution';

interface ToolResultRendererProps {
  step: ExecutionStep;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({ step }) => {
  const raw = step.tool_result ?? step.execution_result ?? step.content;
  if (raw == null) return null;
  const data =
    (typeof raw === 'object' && raw !== null
      ? (raw as Record<string, unknown>).data
      : raw) ?? (raw as Record<string, unknown>);
  if (!data) return null;
  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};

export default React.memo(ToolResultRenderer);
