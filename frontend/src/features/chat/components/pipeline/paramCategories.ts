// 编辑历史: 2026-10-21 小杨 - 新建：参数「路径类」判定单一真源（ParamsPanel/ParamsTree 双入口共用） — 小杨-2026-10-21
// 2026-10-22 小杨 - PATH_KEYS 按后端参数别名表补齐（目录/裸文件名/无扩展名文件同样按路径处理）；
//   isPathLike 放宽为绝对盘符/尾斜杠/末段扩展名三选一，并排除 URL — 小杨-2026-10-22
// 2026-10-23 小欧 - 增 DIR_TOOLS + isDirToolPath：目录类工具（listdir/tree/find）的路径参数
//   按目录渲染（顶层目录名也放行深链）；键判定沿用 PATH_KEYS 以覆盖后端别名键 — 小欧-2026-10-23
// 2026-11-02 小欧 - isPathLike 改复用 utils/projectPath 判据（hasSeparator/isUrlLike/isDriveAbsPath/
//   isDirPath/isFileLikePath），删本文件自建 4 条正则；扩展名上限随之由 8 统一到 EXT_MAX=10 — 小欧-2026-11-02
import {
  hasSeparator,
  isDirPath,
  isDriveAbsPath,
  isFileLikePath,
  isUrlLike,
} from '@/utils/projectPath';
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
 * 2026-11-02 小欧 - 判据全部改为复用 utils/projectPath 单点：原自建 URL / 盘符 / 尾斜杠 / 扩展名
 *   四条正则，扩展名写死 `{1,8}` 与 projectPath 的 EXT_MAX=10 口径冲突（同一路径在参数面板
 *   与正文/深链两处判定不一致）— 小欧-2026-11-02
 */
export const isPathLike = (v: string): boolean => {
  const s = v.trim();
  if (!s || !hasSeparator(s)) return false;
  if (isUrlLike(s)) return false;
  return isDriveAbsPath(s) || isDirPath(s) || isFileLikePath(s);
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

// ── 2026-10-23 小欧 - 目录类工具路径声明（渲染层单点判定） ─────────────
// 注册名对齐 backend/app/tools/file/file_register.py：listdir/tree/find 的路径参数
// 按 schema 语义必为目录（顶层目录名如 src 无扩展名无分隔符也放行跳转）。
// 键判定沿用 PATH_KEYS 而非 'path'：别名键（dir/dir_path/search_dir/search_path，
// 后端 tools_alias_mapper 才映射到 path）在前端是 LLM 原始键名，限 'path' 完全不命中。
export const DIR_TOOLS = new Set(['listdir', 'tree', 'find']);

/** 该工具的该参数是否按目录渲染（DIR_TOOLS 的路径类键；结果视图回显路径不在此列）— 小欧 2026-10-23 */
export const isDirToolPath = (tool: string, k: string, v: unknown): boolean =>
  DIR_TOOLS.has(tool) && PATH_KEYS.has(k) && typeof v === 'string';
