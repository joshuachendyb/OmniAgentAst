// 编辑历史: 2026-10-30 小欧 新建: 引用入口的提示唯一实现(成功/超限/读取失败三分支) — 小欧-2026-10-30

/**
 * quoteToast —— 引用入口的"调入队 + 弹提示"唯一实现
 *
 * 为何独立(DRY): 文件页 / 足迹面板 / 任务卡 / 行内别针 4 处各自写一遍
 *   `if (r.ok) showSuccess(…) else if (too_many) showMessage(超限文案) else showMessage(读取失败)`。
 *   其中 3 处漏了 too_many 分支 —— 引用超上限 20 时提示"引用内容读取失败，请重试"，
 *   用户会去检查一个根本没坏的文件，且怎么重试都不会成功。
 *
 * 分工(SRP): 入队/去重/上限判定仍归 quote.ts + composerRefStore; 本文件只管"结果 → 提示"。
 *   调用方需要流程控制时用返回值(例如任务卡恢复后要导航)。
 */
import { quoteFile, quoteSelection, type QuoteResult } from './quote';
import { labelOf } from './identity';
import { refLimitText } from './store';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';

export interface QuoteToastOptions {
  /** 展示名(缺省取路径末段, 与 chip 标题同口径) */
  label?: string;
  /** 已知大小(文件页批量场景手上有 size 时免再探) */
  size?: number;
  /**
   * 成功文案; 缺省 `已引用「<label>」到对话`;
   * 传空串 = 成功不提示(如任务卡恢复后直接导航, 原页的 toast 已无意义)。
   */
  successText?: string;
}

/**
 * 引用一条（整份 / 行区间）并统一提示。
 * @param range 行区间；给定走选区引用(quoteSelection)，空走整份引用(quoteFile)
 */
export const quoteWithToast = async (
  path: string,
  range?: { start: number; end: number } | null,
  opts?: QuoteToastOptions
): Promise<QuoteResult> => {
  const label = opts?.label ?? labelOf(path);
  const result = range
    ? await quoteSelection(path, range, { label, size: opts?.size })
    : await quoteFile(path, { label, size: opts?.size });
  if (result.ok) {
    const text = opts?.successText ?? `已引用「${label}」到对话`;
    if (text) showSuccess(text);
  } else if (result.reason === 'too_many') {
    showMessage(ErrorType.FILE_READ, refLimitText());
  } else {
    showMessage(ErrorType.FILE_READ, '引用内容读取失败，请重试');
  }
  return result;
};
