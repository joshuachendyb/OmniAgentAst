// 编辑历史: 2026-08-27 小欧 - 重构: 按结果类型(非tool名)分派渲染, 删36套per-tool视图(铁规复用优先/禁backward/KISS)
/**
 * resultTypes - 工具结果类型分派
 *
 * 【北京老陈/小欧 2026-08-27】后端发来的结果结构为通用字典(execution_result.data)
 * + 现成摘要(summary) + tool_name 标签, 不存在 tool 专属类型约束。
 * 故渲染按"结果形状"而非 tool 名分 3 类: generic(绝大多数) / tree(目录树) / code(文件内容)。
 * 仅少数工具需专属形状渲染, 其余统一 generic, 删除原 36 套 per-tool 视图(过度设计)。
 */
import type { ExecutionStep } from '../../../../types/execution';

export type ResultType = 'generic' | 'tree' | 'code';

// tool_name(后端真实注册名) -> 结果类型; 未列者默认 generic
// 经后端核查(2026-08-27): 仅 listdir/tree 为树形, readtext 为文件内容;
// compare_files/file_statistics/batch_rename 后端不存在, 故 diff/table 类当前无对应工具, 不实装(禁backward/YAGNI)。
// 2026-08-27 小欧 三堂会审A29: 删旧长名read_file(后端注册名为readtext, 禁backward)
const TOOL_RESULT_TYPE: Record<string, ResultType> = {
  listdir: 'tree',
  tree: 'tree',
  readtext: 'code',
};

export const resolveResultType = (step: ExecutionStep): ResultType => {
  const name = (step.tool_name ?? '') as string;
  return TOOL_RESULT_TYPE[name] ?? 'generic';
};
