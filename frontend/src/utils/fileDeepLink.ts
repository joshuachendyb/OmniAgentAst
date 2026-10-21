// 编辑历史: 2026-10-21 小杨 - 文档[28]§9.6.2(O7) 新建：文件页深链唯一拼装点 — 小杨-2026-10-21
/**
 * buildFileDeepLink —— `/files?path=…&line=…` 的**唯一**拼装点（O7）
 *
 * 为什么收口：同一份深链格式散落在 ChatInput token、PathLink、FileRefChip 三处，
 *   改一处忘另两处 → 深链形态分叉（用户点 A 进不去、点 B 能进）。
 * 落码纪律：全仓 `?path=` 拼装只允许出现在本文件内，后续改动以 grep 校验。
 */

/**
 * @param relPath 相对项目根的 posix 路径
 * @param lineRange 行区间（可选）；给定则拼 `&line=start-end`
 */
export const buildFileDeepLink = (
  relPath: string,
  lineRange?: { start: number; end: number } | null
): string =>
  `/files?path=${encodeURIComponent(relPath)}${
    lineRange ? `&line=${lineRange.start}-${lineRange.end}` : ''
  }`;
