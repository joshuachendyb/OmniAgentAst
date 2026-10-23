// 编辑历史: 2026-10-21 小欧 - 新建：项目根 ⇄ 相对路径转换唯一真源（绝对→相对自 PathLink 迁入；
//   新增相对→绝对供 J3 设会话目录用）— 小欧-2026-10-21
// 2026-10-21 小欧 - toAbsolutePath 改段级拼接：滤掉 '.' 与空段，
//   不再产出 "F:/proj/./a.md" 这类非规范路径 — 小欧-2026-10-21
// 2026-10-21 小杨 - toRelativePath 支持工具参数里的相对路径；URL/UNC/越界路径仍返回 null — 小杨-2026-10-21
// 2026-10-22 小杨 - toRelativePath 增相对路径直转与换行/控制字符拒收（多行参数不拼假 href）；
//   新增 isAbsolutePath / isLinkableRelPath 供链接层判形态 — 小杨-2026-10-22
// 2026-10-22 小欧 - 外部文件判据：新增 isDriveAbsPath（盘符绝对路径，与后端 _is_abs_drive_path 口径）
//   与 isExternalAbsPath（盘符绝对路径且归一到不了项目根内 = 外部；根内绝对不算外部）— 小欧-2026-10-22
/**
 * 项目根 ⇄ 相对路径 转换（单一真源）
 *
 * 相对路径口径 = 相对项目根的 posix 路径（后端 /files/tree 的 key）。
 */

/** 归一：分隔符统一 /，去尾斜杠 */
const norm = (p: string): string =>
  p.replace(/[/\\]+/g, '/').replace(/\/+$/, '');

/** Windows 盘符绝对路径（F:/ 或 F:\） */
export const isAbsolutePath = (p: string): boolean =>
  /^[A-Za-z]:[\\/]/.test(p) || /^[\\/]/.test(p);

/**
 * 盘符绝对路径（C:\x / D:/x）—— 外部文件判据；UNC/斜杠路径不算。
 * 2026-10-22 小欧 - 与后端 browse_service._is_abs_drive_path 口径对齐（外部只读端点只收盘符绝对路径）。— 小欧-2026-10-22
 */
export const isDriveAbsPath = (p: string): boolean => /^[A-Za-z]:[\\/]/.test(p);

/**
 * 相对路径是否像一条真路径（含分隔符，或带扩展名）。
 * 用途：key 命中路径集但值其实是 "user" / "api" 这类普通词时，不做成假链接。
 */
export const isLinkableRelPath = (rel: string): boolean =>
  /[\\/]/.test(rel) || /\.[A-Za-z0-9]{1,8}$/.test(rel);

/**
 * 任意工具路径 → 相对项目根路径。
 *
 * - 相对路径：归一后直接返回（工具可能给 src/main.py、doc\a.md）
 * - 绝对路径：必须落在项目根内，否则返回 null（不在根内不造假链接）
 * - URL / UNC / 含 .. 的越界路径：返回 null
 */
export const toRelativePath = (
  value: string,
  projectRoot?: string
): string | null => {
  const raw = value.trim();
  if (!raw) return null;
  // 含换行/控制字符的值不是路径（多行参数原样显示即可，别拼出带 %0A 的假 href）
  if (/[\r\n\t\0]/.test(raw)) return null;
  // URL 不是项目文件路径；file: 等自定义 scheme 同样不接
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw)) return null;
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(raw) && !/^[A-Za-z]:[\\/]/.test(raw))
    return null;

  const v = norm(raw);
  if (!v) return null;

  if (!isAbsolutePath(raw)) {
    const segs = v.split('/').filter((s) => s !== '' && s !== '.');
    if (!segs.length || segs.includes('..')) return null;
    return segs.join('/');
  }

  if (!projectRoot) return null;
  const root = norm(projectRoot);
  if (!root) return null;
  if (!v.toLowerCase().startsWith(root.toLowerCase())) return null;
  // 校验分隔符边界：F:\proj2\a.md 不是 F:\proj 内的 "2/a.md"
  if (v.length > root.length && v[root.length] !== '/') return null;
  const rel = v.slice(root.length).replace(/^\/+/, '');
  return rel || null;
};

/**
 * 外部文件判据：盘符绝对路径 **且归一到不了项目根内**。
 * 2026-10-22 小欧 - 项目根内的绝对路径不是外部（先归一成相对走普通深链），
 * 只有根外绝对路径才算外部。根未知时返回 false（信息不足，调用方保持原文，
 * 不造假链接）——否则首帧根未取回时，根内绝对路径会被误标"外部"并生成外部深链。
 * 2026-10-22 小欧 - 与后端 _is_abs_drive_path 口径：只认盘符绝对路径。— 小欧-2026-10-22
 */
export const isExternalAbsPath = (p: string, projectRoot?: string): boolean =>
  !!projectRoot && isDriveAbsPath(p) && !toRelativePath(p, projectRoot);

/**
 * 相对项目根 → 绝对路径；形态不合法（已是绝对路径 / 含 ..）或缺项目根返回 null。
 *
 * 后端 _normalize_ws_path 硬拒相对路径，此处是它的前端对应物；越界形态交后端判界。
 */
export const toAbsolutePath = (
  rel: string,
  projectRoot?: string
): string | null => {
  const raw = rel.trim();
  if (!raw || isAbsolutePath(raw)) return null;
  const segs = norm(raw)
    .split('/')
    .filter((s) => s !== '' && s !== '.');
  if (!segs.length) return null;
  if (segs.includes('..')) return null;
  const root = norm(projectRoot ?? '');
  if (!root) return null;
  // 段级拼接：'.' 与空段已滤掉，避免产出 "F:/proj/./a.md" 这类非规范路径
  return `${root}/${segs.join('/')}`;
};

/** 同路径判定（大小写不敏感 + 分隔符归一） */
export const samePath = (a: string, b: string): boolean =>
  norm(a).toLowerCase() === norm(b).toLowerCase();
