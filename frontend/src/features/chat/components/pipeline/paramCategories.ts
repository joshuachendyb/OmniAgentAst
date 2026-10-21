// 编辑历史: 2026-10-21 小杨 - 新建：参数「路径类」判定单一真源（ParamsPanel/ParamsTree 双入口共用） — 小杨-2026-10-21
// 2026-10-22 小杨 - PATH_KEYS 按后端参数别名表补齐（目录/裸文件名/无扩展名文件同样按路径处理）；
//   isPathLike 放宽为绝对盘符/尾斜杠/末段扩展名三选一，并排除 URL — 小杨-2026-10-22
/**
 * 路径类参数判定 —— **单一真源**
 *
 * 为什么抽出来：深链要接**两个入口**（ParamsPanel 分组视图 + ParamsTree 树视图），
 *   两处若各写一份「这算不算路径」的规则，改一处忘另一处 → 同一参数在一个视图可点、
 *   另一个视图不可点（用户无从理解）。
 *
 * 规则沿用 ParamsPanel 原实现（口径不变，只是搬家）：
 * - 主判据 = key 命中 PATH_KEYS
 * - 补充判据 = 值形似路径（含分隔符，且是绝对盘符 / 尾斜杠目录 / 末段有扩展名；
 *   防误伤 SQL / 代码片段）
 */

/**
 * 路径特征：含分隔符，且满足任一硬特征（防误伤 SQL/代码片段）：
 *   绝对盘符 / 尾斜杠目录 / 末段扩展名。
 */
export const isPathLike = (v: string): boolean => {
  const s = v.trim();
  if (!s || !/[\\/]/.test(s)) return false;
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(s)) return false;
  if (/^[A-Za-z]:[\\/]/.test(s) || /[\\/]$/.test(s)) return true;
  const last = s.split(/[\\/]/).pop() ?? '';
  return /\.[A-Za-z0-9]{1,8}$/.test(last);
};

/**
 * 路径类参数 key 集（2026-10-13 小欧：据全仓 80+ 工具真实参数实测显式列入，
 *   使「其他参数」只接真正零散项）
 *
 * 2026-10-21 小杨 - 补齐工具真实参数名；key 命中后不再要求“值像路径”，
 *   目录、裸文件名、无扩展名文件一律按路径处理 — 小杨-2026-10-21
 *
 * 依据：backend/app/tools/tools_alias_mapper.py 的 PARAM_ALIASES —— 这些 key 在
 *   后端被统一映射到 path/dest/cwd，本身就是路径参数。
 */
export const PATH_KEYS: ReadonlySet<string> = new Set([
  'path',
  'paths',
  'file',
  'files',
  'filename',
  'file_name',
  'filePath',
  'filepath',
  'file_path',
  'file_paths',
  'dir_path',
  'dirPath',
  'dirpath',
  'directory',
  'dir',
  'folder',
  'dirname',
  'dir_name',
  'search_path',
  'search_dir',
  'source',
  'source_path',
  'source_file',
  'source_files',
  'source_dir',
  'src',
  'src_path',
  'target',
  'target_path',
  'target_file',
  'target_files',
  'target_dir',
  'dest',
  'dst',
  'dst_path',
  'destination',
  'destination_path',
  'dest_path',
  'output',
  'output_path',
  'output_file',
  'output_dir',
  'input',
  'input_path',
  'input_file',
  'input_dir',
  'save_path',
  'save_dir',
  'download_path',
  'upload_path',
  'archive',
  'archive_path',
  'extract_to',
  'workdir',
  'work_dir',
  'working_dir',
  'working_directory',
  'base_dir',
  'project_dir',
  'root_dir',
  'cwd',
  'sql_file',
  'script_path',
  'config_path',
  'log_path',
  'image_path',
  'media_path',
  'document_path',
  'pdf_path',
  'docx_path',
  'xlsx_path',
  'pptx_path',
  'attachments',
  // 旧版漏判导致 cwd/url/source/target 掉进「其他」（实测 bash.cwd、http_get.url）
  'url',
]);

/** 该参数是否按「路径」处理（双入口共用同一判据） */
export const isPathParam = (k: string, v: unknown): boolean =>
  PATH_KEYS.has(k) || (typeof v === 'string' && isPathLike(v));
