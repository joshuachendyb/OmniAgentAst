// 编辑历史: 2026-10-21 小杨 - 文档[28]§4.4.12 新建：参数「路径类」判定单一真源（ParamsPanel/ParamsTree 双入口共用） — 小杨-2026-10-21
/**
 * 路径类参数判定 —— **单一真源**
 *
 * 为什么抽出来：J1 深链要接**两个入口**（ParamsPanel 分组视图 + ParamsTree 树视图），
 *   两处若各写一份「这算不算路径」的规则，改一处忘另一处 → 同一参数在一个视图可点、
 *   另一个视图不可点（用户无从理解）。
 *
 * 规则沿用 ParamsPanel 原实现（口径不变，只是搬家）：
 * - 主判据 = key 命中 PATH_KEYS
 * - 补充判据 = 值形似路径（含分隔符 **且** 末段有扩展名；防误伤 SQL / 代码片段）
 */

/** 路径特征：同时含分隔符 且 末段有扩展名（防误伤 SQL/代码片段） */
export const isPathLike = (v: string): boolean => {
  if (!/[\\/]/.test(v)) return false;
  const last = v.split(/[\\/]/).pop() ?? '';
  return /\.[A-Za-z0-9]{1,8}$/.test(last);
};

/**
 * 路径类参数 key 集（2026-10-13 小欧：据全仓 80+ 工具真实参数实测显式列入，
 *   使「其他参数」只接真正零散项）
 */
export const PATH_KEYS: ReadonlySet<string> = new Set([
  'path',
  'dir_path',
  'file_path',
  'source_path',
  'dest',
  'output_path',
  // 旧版漏判导致 cwd/url/source/target 掉进「其他」（实测 bash.cwd、http_get.url）
  'cwd',
  'url',
  'source',
  'target',
  'directory',
  'dir',
  'sql_file',
]);

/** 该参数是否按「路径」处理（双入口共用同一判据） */
export const isPathParam = (k: string, v: unknown): boolean =>
  PATH_KEYS.has(k) || (typeof v === 'string' && isPathLike(v));
