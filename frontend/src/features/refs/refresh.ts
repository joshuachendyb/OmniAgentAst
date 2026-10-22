// 编辑历史: 2026-10-22 小欧 - 新建：发送前引用校验与保鲜（唯一实现）— 小欧-2026-10-22
/**
 * refreshRefs —— 发送前对每条引用**重读一遍**
 *
 * 为什么重读（语义不变，只搬家）：① 文件被删/不可读 → 标 invalid、阻断发送并点名
 *   （不让模型收到失效内容）；② 读成功的把 content 换成最新（内容保鲜）；
 *   ③ 行号区间按**当前**文件重新切片（文件变了行号也会变）。
 *
 * 为什么抽函数：原实现内联在 ChatInput 里 46 行，不可单测；
 *   抽成纯函数后，失效判定与切片口径有单测兜底（可靠性目标）。
 */
import { fileApi } from '@/services/api/file.api';
import type { ComposerRef } from './store';

/** 按行区间切片（1-based 闭区间）；越界 → null（判失效） */
export const sliceByLineRange = (
  content: string,
  range: { start: number; end: number }
): string | null => {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  if (range.start > lines.length || range.end > lines.length) return null;
  return lines.slice(range.start - 1, range.end).join('\n');
};

/** 逐条重读 + 保鲜 + 失效标记 */
export const refreshRefs = async (
  refs: ComposerRef[]
): Promise<ComposerRef[]> =>
  Promise.all(
    refs.map(async (r) => {
      // v1.4（修 D6）：pending 占位由发送闸门拦截，不进重读（显式跳过，不靠隐式时序保证）
      if (r.pending) return r;
      if (!r.path) return r;
      try {
        const f = await fileApi.readFile(r.path);
        if (r.lineRange) {
          const content = sliceByLineRange(f.content, r.lineRange);
          if (content === null) return { ...r, invalid: true };
          return {
            ...r,
            content,
            size: new TextEncoder().encode(content).length,
            invalid: false,
          };
        }
        return { ...r, content: f.content, size: f.size, invalid: false };
      } catch {
        return { ...r, invalid: true };
      }
    })
  );
