// 编辑历史: 2026-10-21 小欧 - 新建：项目根 ⇄ 相对路径转换唯一真源（绝对→相对自 PathLink 迁入；
//   新增相对→绝对供 J3 设会话目录用）— 小欧-2026-10-21
// 2026-10-21 小欧 - toAbsolutePath 改段级拼接：滤掉 '.' 与空段，
//   不再产出 "F:/proj/./a.md" 这类非规范路径 — 小欧-2026-10-21
/**
 * 项目根 ⇄ 相对路径 转换（单一真源）
 *
 * 相对路径口径 = 相对项目根的 posix 路径（后端 /files/tree 的 key）。
 */

/** 归一：分隔符统一 /，去尾斜杠 */
const norm = (p: string): string =>
  p.replace(/[/\\]+/g, '/').replace(/\/+$/, '');

/** 绝对 → 相对项目根；不在项目根内返回 null */
export const toRelativePath = (
  value: string,
  projectRoot?: string
): string | null => {
  if (!projectRoot) return null;
  const root = norm(projectRoot);
  const v = norm(value);
  if (!root || !v) return null;
  if (!v.toLowerCase().startsWith(root.toLowerCase())) return null;
  // 校验分隔符边界：F:\proj2\a.md 不是 F:\proj 内的 "2/a.md"
  if (v.length > root.length && v[root.length] !== '/') return null;
  const rel = v.slice(root.length).replace(/^\/+/, '');
  return rel || null;
};

/**
 * 相对项目根 → 绝对路径；形态不合法（已是绝对路径 / 含 ..）或缺项目根返回 null。
 *
 * 后端 _normalize_ws_path 硬拒相对路径，此处是它的前端对应物；越界形态交后端判界。
 */
export const toAbsolutePath = (
  rel: string,
  projectRoot?: string
): string | null => {
  if (!projectRoot) return null;
  const segs = norm(rel)
    .split('/')
    .filter((s) => s !== '' && s !== '.');
  if (!segs.length) return null;
  if (segs.includes('..')) return null;
  const root = norm(projectRoot);
  if (!root) return null;
  // 段级拼接：'.' 与空段已滤掉，避免产出 "F:/proj/./a.md" 这类非规范路径
  return `${root}/${segs.join('/')}`;
};

/** 同路径判定（大小写不敏感 + 分隔符归一） */
export const samePath = (a: string, b: string): boolean =>
  norm(a).toLowerCase() === norm(b).toLowerCase();
