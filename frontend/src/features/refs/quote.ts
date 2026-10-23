// 编辑历史: 2026-10-22 小欧 - 新建：引用入口唯一实现（读盘 + 组装 + 入队）— 小欧-2026-10-22
/**
 * quote —— 「把文件送进对话」的唯一入口
 *
 * 为什么收口（DRY）：重构前有 3 份近似实现（文件页 / 足迹面板 / 任务卡），
 *   各自读盘、各自组装 ref、各自提示错误 —— 加一个入口就多一份分叉。
 *   本文件是唯一实现，新增入口（产出物可点、上下文包）只调这里。
 *
 * 语义约定：
 * - 就地收集：只入队不导航（用户在文件页读/挑多个文件时不该被反复踢走）；
 *   需要跳回对话页时由调用方决定（文件页有「去对话」按钮）。
 * - 正文当轮即弃：content 只存在队列里，上行后由后端组装；台账只存路径。
 * - 读失败不静默：只返回 reason，不弹提示——成功与失败文案都归调用方。
 */
import { fileApi } from '@/services/api/file.api';
import { isDriveAbsPath } from '@/utils/projectPath';
import { composerRefStore, newRefId } from './store';

export interface QuoteResult {
  ok: boolean;
  /** 失败原因（ok=false 时给出，供调用方分支选择提示文案） */
  reason?: string;
}

/** 引用整个文件（正文可由调用方预读后直传，避免文件页预览已有内容再读一遍） */
export const quoteFile = async (
  path: string,
  opts?: { label?: string; content?: string; size?: number }
): Promise<QuoteResult> => {
  const label = opts?.label ?? path.split('/').pop() ?? path;
  try {
    const content =
      opts?.content ??
      (isDriveAbsPath(path)
        ? (await fileApi.readExternalFile(path)).content
        : (await fileApi.readFile(path)).content);
    composerRefStore.push({
      id: newRefId(),
      kind: 'file',
      label,
      path,
      content,
      size: opts?.size ?? content.length,
      lineRange: null,
    });
    return { ok: true };
  } catch {
    return { ok: false, reason: 'read_failed' };
  }
};

/** 引用一段行区间（选区引用）；正文可由调用方预切后直传（文件页选区已切好行） */
export const quoteSelection = async (
  path: string,
  range: { start: number; end: number },
  opts?: { label?: string; content?: string; size?: number }
): Promise<QuoteResult> => {
  const label = opts?.label ?? path.split('/').pop() ?? path;
  try {
    const content = opts?.content ?? (await fileApi.readFile(path)).content;
    composerRefStore.push({
      id: newRefId(),
      kind: 'selection',
      label,
      path,
      content,
      size: opts?.size ?? content.length,
      lineRange: range,
    });
    return { ok: true };
  } catch {
    return { ok: false, reason: 'read_failed' };
  }
};

/**
 * 引用一组文件为一个包（上下文包）。
 * ⚠ 包内无 path → 后端 sanitize_refs 放行（"无 path 的条目不校验"），
 *   _render_refs_block 以 label 作锚 —— 不需要任何后端改动。
 */
export const quotePack = async (
  files: { path: string; label?: string }[],
  opts?: { max?: number }
): Promise<QuoteResult> => {
  const max = opts?.max ?? 10;
  if (files.length === 0) return { ok: false, reason: 'empty' };
  if (files.length > max) {
    return { ok: false, reason: 'too_many' };
  }
  const parts: string[] = [
    `【文件清单】\n${files.map((f) => f.path).join('\n')}`,
  ];
  for (const f of files) {
    try {
      const r = await fileApi.readFile(f.path);
      parts.push(`【文件】${f.path}\n${r.content}`);
    } catch {
      parts.push(`【文件】${f.path}\n（读取失败，已跳过）`);
    }
  }
  const content = parts.join('\n\n');
  composerRefStore.push({
    id: newRefId(),
    kind: 'file',
    label: `${files.length} 个文件`,
    path: '',
    content,
    size: content.length,
    lineRange: null,
  });
  return { ok: true };
};
