// 编辑历史: 2026-10-21 小杨 - 新建：文件引用预处理的流式期节流 — 小杨-2026-10-21
// 2026-10-22 小欧 - 增 projectRoot：裸绝对路径需按项目根归一为相对路径 — 小欧-2026-10-22
/**
 * useDeferredPreprocess —— 文件引用预处理的流式期节流
 *
 * 问题：流式响应每个 chunk 都全量跑一遍预处理正则（含围栏拆分），
 *   长回复下 CPU 明显抖动。
 * 做法：文本**稳定后再处理**（React `useDeferredValue` 让急迫更新先出），
 *   即"渲染先跟手、预处理随后补齐"，最终内容与 preprocessFileRefs 逐字节一致。
 *
 * 为什么放 components/markdown/：单一消费域（MarkdownSlot 一家）+ 就近放置；
 *   若出现第二个消费者再升迁 src/hooks/（迁移成本 = 1 行 import）。
 */
import { useDeferredValue, useMemo } from 'react';
import { preprocessFileRefs } from './FileRefChip';

/**
 * @param source 原始文本（流式过程中会不断增长）
 * @param projectRoot 项目根（裸绝对路径归一用；空串时绝对路径保持原文）
 * @returns 预处理后的文本（与 preprocessFileRefs(source, projectRoot) 逐字节一致，只是时机不同）
 */
export function useDeferredPreprocess(
  source: string,
  projectRoot?: string
): string {
  const deferred = useDeferredValue(source);
  return useMemo(
    () => preprocessFileRefs(deferred, projectRoot),
    [deferred, projectRoot]
  );
}
