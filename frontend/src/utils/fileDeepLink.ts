// 编辑历史: 2026-10-21 小杨 - 新建：文件页深链唯一拼装点 — 小杨-2026-10-21
// 2026-10-22 小杨 - 增 encodePathParam / decodePathParam：补编括号防 markdown 链接被截断，
//   非法百分号编码解码为 null 而不是抛 URIError — 小杨-2026-10-22
// 2026-10-22 小欧 - 增 buildExternalDeepLink：外部文件深链 /files?ext=1&path=<绝对路径>（复用唯一拼装点）— 小欧-2026-10-22
// 2026-10-23 小欧 - 增 buildExternalDirDeepLink：外部目录深链补尾分隔符（文件页 isDirPath 判据所需），仍复用同一拼装点 — 小欧-2026-10-23
// 2026-10-28 小欧 - 增 resolveChipUrl：chip 点击时实时取最新项目根(getCurrentProjectRoot)算
//   ext=1 vs 普通深链，不依赖渲染时 useProjectRoot 快照（项目根切换后时序窗口内快照持旧根
//   → 误判外部 → ext=1 URL → Files 页 linkErr）。FileRefChip/FilePathLink 的 onClick 共用本函数(DRY)。— 小欧-2026-10-28
// 2026-10-29 小欧 - 删 resolveChipUrl 的 opts.source 参数与 ChipNavSource/ResolveChipUrlOptions：
//   该参数两支返回值完全相同(isExternalAbsPath(rawPath, root) 求值两次), 调用方传它不产生任何
//   行为差异 —— 死参数(违反 YAGNI/KISS-DIRECT), 且让读代码的人误以为站内/站外有两条解析路径。
//   站内/站外分流实际由 Files 页的 location.state.internal 决定, 与 URL 拼装无关 — 小欧-2026-10-29
/**
 * buildFileDeepLink —— `/files?path=…&line=…` 的**唯一**拼装点
 *
 * 为什么收口：同一份深链格式散落在 ChatInput token、PathLink、FileRefChip 三处，
 *   改一处忘另两处 → 深链形态分叉（用户点 A 进不去、点 B 能进）。
 *   落码纪律：全仓 `?path=` 拼装只允许出现在本文件内，后续改动以 grep 校验。
 */

import { getCurrentProjectRoot } from '@/hooks/useProjectRoot';
import { isExternalAbsPath, isDirPath } from '@/utils/projectPath';

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
 * 项目根**外**文件（外部文件）深链：`/files?ext=1&path=<绝对路径>`。
 * 2026-10-22 小欧 - 会话里 Agent 引用的文件可能不在当前项目根内，根外文件
 * 走 `ext=1` 形态直开外部只读预览（不走树定位）。— 小欧-2026-10-22
 *
 * @param absPath 盘符绝对路径（如 `E:\outside\a.py`）
 */
export const buildExternalDeepLink = (
  absPath: string,
  lineRange?: { start: number; end: number } | null
): string =>
  `/files?ext=1&path=${encodePathParam(absPath)}${
    lineRange ? `&line=${lineRange.start}-${lineRange.end}` : ''
  }`;

/** 2026-10-23 小欧 - 目录形归尾：去重复尾分隔符后补单个 `/`（幂等，已是目录形原样归一） */
const withDirTail = (absPath: string): string =>
  `${absPath.replace(/[\\/]+$/, '')}/`;

/**
 * 项目根**外**目录深链：`/files?ext=1&path=<绝对目录>/`（补尾分隔符，
 * 文件页 isDirPath 靠尾分隔符区分目录与文件）。— 小欧-2026-10-23
 *
 * @param absDir 盘符绝对目录（如 `E:\outside\data`）
 */
export const buildExternalDirDeepLink = (
  absDir: string,
  lineRange?: { start: number; end: number } | null
): string => buildExternalDeepLink(withDirTail(absDir), lineRange);

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

/**
 * chip 点击时实时算文件页深链 URL（不依赖渲染时 useProjectRoot 快照）。
 * 2026-10-28 小欧 - 取当前最新项目根(getCurrentProjectRoot)判 isExternal：
 *   根外盘符绝对 → ext=1 外部深链；根内/相对 → 普通深链(Files 页归一定位)。
 *   目录不带行号。FileRefChip/FilePathLink 的 onClick 共用本函数。— 小欧-2026-10-28
 * 2026-10-28 小欧 - 增加 source 标记：站内聊天卡片（chat）走内部渲染优先用项目根解析，
 *   外部直链（url）保留现有行为。两种场景分流，避免上次外部目录状态覆盖相对路径。— 小欧-2026-10-28
 * 2026-10-29 小欧 - 上一条已撤销：两支返回值完全相同，source 标记从未产生分流效果，故删除 —
 *   小欧-2026-10-29
 */
export const resolveChipUrl = (
  rawPath: string,
  lineRange?: { start: number; end: number } | null
): string => {
  const root = getCurrentProjectRoot();
  const isDir = isDirPath(rawPath);
  const lines = isDir ? null : (lineRange ?? null);
  const isExternal = isExternalAbsPath(rawPath, root);
  return isExternal
    ? buildExternalDeepLink(rawPath, lines)
    : buildFileDeepLink(rawPath, lines);
};
