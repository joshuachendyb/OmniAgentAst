// 编辑历史: 2026-08-26 小欧 - 8.4 实施: pipeline桶导出, 供RightViewer引用(8.5)
// 编辑历史: 2026-10-28 小欧 - P2 前端懒渲染优化: 导出 useLazyRender 渐进式渲染 hook(分批调度, 可复用) — 小欧-2026-10-28
/**
 * pipeline 桶导出
 *
 * 【小欧 2026-08-26 8.4】供 RightViewer(8.5) `from '../pipeline'` 引用 PipelineRenderer，
 * 子组件亦可按需引入。
 *
 * @author 小欧
 * @date 2026-08-26
 */

export { PipelineRenderer } from './PipelineRenderer';
export { ThinkingStream } from './ThinkingStream';
export { ToolCallLine } from './ToolCallLine';
export { ResponseStream } from './ResponseStream';
export { StatusLine } from './StatusLine';
export { CollapsibleText } from './CollapsibleText';
export { splitSteps, isBusinessStep, META_STEP_TYPES } from './stepFilter';
export type { SplitResult } from './stepFilter';
export { useLazyRender } from './useLazyRender'; // 2026-10-28 小欧 - P2: 渐进式渲染 hook(分批调度, 可复用) — 小欧-2026-10-28
export type { LazyRenderResult } from './useLazyRender';
