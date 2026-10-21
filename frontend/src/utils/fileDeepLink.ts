// 编辑历史: 2026-10-21 小杨 - 新建：文件页深链唯一拼装点 — 小杨-2026-10-21
// 2026-10-22 小杨 - 增 encodePathParam / decodePathParam：补编括号防 markdown 链接被截断，
//   非法百分号编码解码为 null 而不是抛 URIError — 小杨-2026-10-22
/**
 * buildFileDeepLink —— `/files?path=…&line=…` 的**唯一**拼装点
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
  `/files?path=${encodePathParam(relPath)}${
    lineRange ? `&line=${lineRange.start}-${lineRange.end}` : ''
  }`;

/**
 * 查询参数编码：encodeURIComponent 不编码 `()`，而 `)` 会截断
 *   `[label](/file-ref?path=a).md)` 这类 markdown 链接，故补编码。
 */
export const encodePathParam = (path: string): string =>
  encodeURIComponent(path).replace(/[()]/g, (c) => (c === '(' ? '%28' : '%29'));

/** 查询参数解码：非法百分号编码返回 null，调用方退化为纯文本而不是抛 URIError */
export const decodePathParam = (value: string): string | null => {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
};
