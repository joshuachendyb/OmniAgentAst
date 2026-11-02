// 编辑历史: 2026-10-21 小欧 - 新建：项目根 ⇄ 相对路径转换唯一真源（绝对→相对自 PathLink 迁入；
//   新增相对→绝对供 J3 设会话目录用）— 小欧-2026-10-21
// 2026-10-21 小欧 - toAbsolutePath 改段级拼接：滤掉 '.' 与空段，
//   不再产出 "F:/proj/./a.md" 这类非规范路径 — 小欧-2026-10-21
// 2026-10-25 小欧 - toAbsolutePath 返回 Windows 风格反斜杠：原 norm 统一为 / 后拼出
//   F:/proj/... 正斜杠，Windows 下应输出 F:\proj\... — 小欧-2026-10-25
// 2026-10-21 小杨 - toRelativePath 支持工具参数里的相对路径；URL/UNC/越界路径仍返回 null — 小杨-2026-10-21
// 2026-10-22 小杨 - toRelativePath 增相对路径直转与换行/控制字符拒收（多行参数不拼假 href）；
//   新增 isAbsolutePath / isLinkableRelPath 供链接层判形态 — 小杨-2026-10-22
// 2026-10-22 小欧 - 外部文件判据：新增 isDriveAbsPath（盘符绝对路径，与后端 _is_abs_drive_path 口径）
//   与 isExternalAbsPath（盘符绝对路径且归一到不了项目根内 = 外部；根内绝对不算外部）— 小欧-2026-10-22
// 2026-11-01 小欧 - 新增目录形态判据两函数：isAbsDirLikePath（盘符绝对 + 无尾分隔符 + 无扩展名，
//   `F:\a\b` 按目录认，只判形态不查盘）与 isDirLikePath（= isDirPath ∪ isAbsDirLikePath，chip 徽标
//   与点击深链共用的唯一出口，防止两处各写一遍漂移）— 小欧-2026-11-01
// 2026-11-02 小欧 - 新增 isUnderRoot（含等于根 + 分隔符边界校验），isExternalAbsPath 改用它：
//   原判据 !toRelativePath 把「等于根」（rel 空串被 || 吃成 null）误判根外 — 小欧-2026-11-02
// 2026-11-02 小欧 - 迁入 isValidRelPath（原在 FileRefChip）：路径形态校验属本文件职责，
//   且唯一路径解析函数（fileDeepLink.resolvePathTarget）需要它 — 小欧-2026-11-02
// 2026-11-02 小欧 - 删 isExternalAbsPath：内外判定已收敛到唯一路径解析函数（resolvePathTarget），
//   保留两套判据必再漂移；本文件只留 isUnderRoot 单一判据 — 小欧-2026-11-02
// 2026-11-02 小欧 - 删 isDirLikePath（已无调用方）：目录合成判据由 resolvePathTarget 按
//   strictShape 选项组合 isDirPath/isAbsDirLikePath，不再单列一层 — 小欧-2026-11-02
// 2026-11-02 小欧 - 并入 utils/fileDeepLink.ts（该文件删除）：深链拼装 + 唯一路径解析
//   resolvePathTarget 迁入本文件，全前端「路径 → 链接」只此一个模块；需要取根的
//   resolveChipUrlFresh 移至 hooks/useProjectRoot（本文件保持零 React / 零网络）— 小欧-2026-11-02
// 2026-11-02 小欧 - 正文识别（原 components/markdown/pathDetect.ts）并入本文件并删原文件；
//   形态判据碎片抽 HAS_EXT_RE / ENDS_WITH_SEP_RE / hasCtrlChar / hasParentTraversal 消 4 处重复；
//   6 个零生产调用的判据取消 export（仅文件内使用）— 小欧-2026-11-02
// 2026-11-02 小欧 - 重复逻辑收敛：EXT_MAX 单点（原 8/10/10 三套口径）；lineQuery 单点（三处深链拼装
//   共用，file-ref 不再单独拼 `&line=n`）；抽 relSegments / spacedPath 消 2 处流水线重复；
//   形态校验收进 relFromRoot 一处（resolvePathTarget / toFileRefMarkdown 不再复检）；
//   convertRuns 三分支的 piece/consumed 收敛为一处；buildExternalDirDeepLink 只有 1 处调用且
//   行号恒空，内联为 buildExternalDeepLink(withDirTail(…), null) — 小欧-2026-11-02
// 2026-11-02 小欧 - 判据集中化：norm/baseName/hasSeparator/isUrlLike/hasDriveAbsPath/isFileRefLink
//   对外导出，isDirPath/isFileLikePath 由私有转导出，joinAbsPath 自 utils/fileTree 迁入；私有
//   isPathLike 改名 isInlineCodePath（与 paramCategories.isPathLike 同名异义）— 小欧-2026-11-02
// 2026-11-02 小欧 - 三堂会审末轮：isFileLikePath / isInlineCodePath 的末段改调 baseName，
//   toFileRefMarkdown 的「有没有目录」改调 hasSeparator（原各自手写 split(/[\\/]/).pop() 与
//   /[\\/]/.test，第四、第五份判据碎片）；toRelativePath 对「等于根」返回 ''（与 relFromRoot 同口径），
//   内外判定直接读它并删 isUnderRoot（原对同一段前缀比对算两遍）；PathTarget 增 pending —
//   「绝对路径 + 根未取回」由解析结果给出，文件页不再自己重写一遍同一判据 — 小欧-2026-11-02
/**
 * 项目根 ⇄ 相对路径转换 + 深链拼装 + 正文路径识别（**单一真源**）
 *
 * 相对路径口径 = 相对项目根的 posix 路径（后端 /files/tree 的 key）。
 * 本文件零依赖：不 import React、不发起请求（取根在 hooks/useProjectRoot）。
 *
 * SLAP 取舍：文件含「判据 / 拼装 / 解析 / markdown 正文识别」四段，抽象层不同，但四段共享同一套
 *   形态判据与同一变化原因（路径规则变了 → 四段一起变）。拆文件必须跨文件 import 判据（DRY 违规）
 *   或复制判据（口径漂移），故按「路径 → 链接只此一处」集中，函数级仍各自单一抽象层。
 */

/**
 * 分隔符归一（**唯一实现**）：反斜杠→正斜杠、折叠重复分隔符、去尾分隔符。
 * 2026-11-02 小欧 - 对外导出：`AuthorizationModal` 自建过一份 `p.replace(/\\/g,'/')`、
 *   `fileTree.joinAbsPath` 自建过一份「去尾 + 换向」，三套归一并存必漂移 — 小欧-2026-11-02
 */
export const norm = (p: string): string =>
  p.replace(/[/\\]+/g, '/').replace(/\/+$/, '');

// 2026-11-02 小欧 - 形态判据的公共碎片单点定义：原在 4 处各写一遍（正则还不一致），
//   任一处改动漏另一处即口径漂移 — 小欧-2026-11-02
/** 扩展名长度上限（**唯一口径**）：形态判据 / 正文识别 / 行内代码共用，原为 8/10/10 三套 — 小欧-2026-11-02 */
const EXT_MAX = 10;
/** 末段带扩展名（1~EXT_MAX 位字母数字） */
const HAS_EXT_RE = new RegExp(`\\.[A-Za-z0-9]{1,${EXT_MAX}}$`);
/** 尾部一个或多个分隔符 */
const ENDS_WITH_SEP_RE = /[\\/]+$/;
/** 含分隔符（`/` 或 `\`） */
export const hasSeparator = (p: string): boolean => /[\\/]/.test(p);
/** 含换行/制表/NUL 不是路径 */
const hasCtrlChar = (p: string): boolean => /[\r\n\t\0]/.test(p);
/** 含 `..` 段 = 越界穿越 */
const hasParentTraversal = (p: string): boolean =>
  p.split(/[\\/]/).includes('..');

/**
 * 路径末段（文件名/目录名）—— **唯一实现**：原 4 处各写 `split(/[\\/]/).pop()`，
 *   其中 2 处只认 `/`，Windows 反斜杠路径会把整条当名字（实测 chip 标题出现 `D:\a\b.md`）。
 * 2026-11-02 小欧 - 自 features/refs/identity.labelOf 上提，反向由 labelOf 复用 — 小欧-2026-11-02
 */
export const baseName = (p: string): string => p.split(/[\\/]/).pop() || '';

/** URL（`http://`、`https://` 等带 `//` 的 scheme）不是文件路径 */
export const isUrlLike = (p: string): boolean =>
  /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(p);

/** 正文/参数里是否出现盘符绝对路径（`F:\x`、`C:/x`）—— 决定要不要取项目根 */
export const hasDriveAbsPath = (text: string): boolean =>
  /(?:^|[^A-Za-z0-9+.-])[A-Za-z]:[\\/]/.test(text);

/** 正文内部链接前缀（buildFileRefLink 生成的唯一形态） */
const FILE_REF_PREFIX = '/file-ref?';

/** 是否内部文件引用链接（`/file-ref?…`，由 buildFileRefLink 生成） */
export const isFileRefLink = (href: string): boolean =>
  href.startsWith(FILE_REF_PREFIX);

/** 正文里是否**含有**内部文件引用链接（链接可能夹在文字中间，故用 includes） */
export const hasFileRefLink = (text: string): boolean =>
  text.includes(FILE_REF_PREFIX);

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
  hasSeparator(rel) || HAS_EXT_RE.test(rel);

/**
 * 前端**形态**校验唯一一份：绝对路径 / UNC / 含 `..` 一律不合格。
 * 2026-11-02 小欧 - 自 FileRefChip 迁入：唯一路径解析函数（fileDeepLink.resolvePathTarget）
 *   要用，而 fileDeepLink 不能反向 import 组件（会循环依赖）— 小欧-2026-11-02
 */
export const isValidRelPath = (p: string): boolean => {
  if (!p || /^[a-zA-Z]:/.test(p) || p.startsWith('/') || p.startsWith('\\'))
    return false;
  return !hasParentTraversal(p);
};

/**
 * 根内路径 → 相对 posix（`''` = 等于根本身）；根外 / 根未知 / 形态不合法 → null。
 * 2026-11-02 小欧 - 内外判定唯一实现：原 toRelativePath 与 isUnderRoot 各写一遍
 *   「前缀 + 分隔符边界」，任一处改动漏另一处即漂移 — 小欧-2026-11-02
 */
const relFromRoot = (p: string, projectRoot?: string): string | null => {
  if (!projectRoot) return null;
  const v = norm(p);
  const root = norm(projectRoot);
  if (!v || !root) return null;
  if (!v.toLowerCase().startsWith(root.toLowerCase())) return null;
  // 分隔符边界：F:\proj2\a.md 不是 F:\proj 内的 "2/a.md"
  if (v.length > root.length && v[root.length] !== '/') return null;
  const rel = v.slice(root.length).replace(/^\/+/, '');
  // 2026-11-02 小欧 - 切片后仍可能是 `../x`（`E:\root\..\x` 归一后前缀仍命中）：
  //   形态校验收在本函数一处，下游不再各自复检（原 3 处复检同一件事）— 小欧-2026-11-02
  return rel === '' || isValidRelPath(rel) ? rel : null;
};

/**
 * 相对路径 → 规范段数组（滤空段与 `.`）；全空或含 `..` → null。
 * 2026-11-02 小欧 - toRelativePath 与 toAbsolutePath 原各写一遍「滤段 + 拒 ..」，
 *   任一处改动漏另一处即漂移 — 小欧-2026-11-02
 */
const relSegments = (p: string): string[] | null => {
  const segs = norm(p)
    .split('/')
    .filter((s) => s !== '' && s !== '.');
  return segs.length && !segs.includes('..') ? segs : null;
};

/**
 * 任意工具路径 → 相对项目根路径。
 *
 * - 相对路径：归一后直接返回（工具可能给 src/main.py、doc\a.md）
 * - 绝对路径：必须落在项目根内，否则返回 null（不在根内不造假链接）
 * - `''` = 路径**就是项目根自身**（与 relFromRoot 同口径，不折成 null）
 * - URL / UNC / 含 .. 的越界路径：返回 null
 */
export const toRelativePath = (
  value: string,
  projectRoot?: string
): string | null => {
  const raw = value.trim();
  if (!raw) return null;
  // 含换行/控制字符的值不是路径（多行参数原样显示即可，别拼出带 %0A 的假 href）
  if (hasCtrlChar(raw)) return null;
  // URL（http://、file: 等自定义 scheme）不是项目文件路径；盘符绝对路径例外
  // 2026-11-02 小欧 - 原两条正则（先 `://` 再任意 scheme）判同一件事，且盘符判据内联了一份
  //   isDriveAbsPath 的正则，收敛为一条 — 小欧-2026-11-02
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(raw) && !isDriveAbsPath(raw))
    return null;

  const v = norm(raw);
  if (!v) return null;

  if (!isAbsolutePath(raw)) {
    const segs = relSegments(v);
    return segs ? segs.join('/') : null;
  }

  return relFromRoot(raw, projectRoot);
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
  const raw = rel.trim();
  if (!raw || isAbsolutePath(raw)) return null;
  const segs = relSegments(raw);
  if (!segs) return null;
  const root = norm(projectRoot ?? '');
  if (!root) return null;
  // 段级拼接：'.' 与空段已滤掉，避免产出 "F:\proj\.\a.md" 这类非规范路径
  // 2026-10-25 小欧 - norm 归一化后直接拼，最终转回 \ 保证 Windows 风格 — 小欧-2026-10-25
  return `${root}/${segs.join('/')}`.replace(/\//g, '\\');
};

/** 同路径判定（大小写不敏感 + 分隔符归一） */
export const samePath = (a: string, b: string): boolean =>
  norm(a).toLowerCase() === norm(b).toLowerCase();

/**
 * 绝对路径 + 相对路径 → Windows 风格绝对路径（`\` 分隔）。
 * 场景：externalBase 是 Windows 绝对路径（F:\x），后端返回的 key 是 posix 相对路径
 *   （backend/app/db/...），直接拼会混用 `\` 和 `/`；统一转 `\` 再拼，显示一致且后端 Path() 两种都认。
 * 2026-10-24 小欧 - 原在 utils/fileTree.ts，迁入本模块：拼接属路径职责，fileTree 只留树操作 — 小欧-2026-11-02
 */
export const joinAbsPath = (base: string, rel: string): string =>
  `${base.replace(ENDS_WITH_SEP_RE, '')}\\${rel.replace(/[/\\]+/g, '\\')}`;

/**
 * 末段是否像文件（带扩展名）—— 外部文件深链判据：
 * 根外盘符绝对路径「只有带扩展名才按文件打开外部只读预览」；目录/无扩展名路径不误判成文件。
 * 2026-10-23 小欧 - 新增（PathLink / FilePathLink 共用，避免两处各自写一次判据漂移）。— 小欧-2026-10-23
 */
export const isFileLikePath = (p: string): boolean =>
  HAS_EXT_RE.test(baseName(p.replace(ENDS_WITH_SEP_RE, '')));

/**
 * 目录形态判据：尾分隔符是唯一可靠信号（不猜扩展名，历史上误判过带 .md 的目录）。
 * 2026-10-23 小欧 - 由 FileRefChip 提到 projectPath 单点（Files 页 ext=1 目录分支 / 定位框
 *   根外目录开放共用，避免「目录=尾分隔符」判据两处各自写一次漂移）。— 小欧-2026-10-23
 */
export const isDirPath = (p: string): boolean => ENDS_WITH_SEP_RE.test(p);

/**
 * 无扩展名的盘符绝对路径（`F:\a\b`）→ 按**目录**认定（正文常写目录不带尾分隔符）。
 * 2026-11-01 小欧 - 仅形态判据、不查盘：带扩展名仍算文件，是否真目录由文件页/后端定。— 小欧-2026-11-01
 */
const isAbsDirLikePath = (p: string): boolean =>
  isDriveAbsPath(p) && !isDirPath(p) && !isFileLikePath(p);

// ===== 深链拼装 + 唯一路径解析（2026-11-02 小欧 - 自 utils/fileDeepLink.ts 并入）=====
// 合并理由：判据与拼装本是一件事的两步，拆两个文件只会让人在两处找「路径怎么变链接」。
// 本文件保持零 React / 零网络依赖：需要取根的 resolveChipUrlFresh 已移入 hooks/useProjectRoot。

/**
 * 查询参数编码：encodeURIComponent 不编码 `()`，而 `)` 会截断
 *   `[label](/file-ref?path=a).md)` 这类 markdown 链接，故补编码。— 小杨-2026-10-22
 */
export const encodePathParam = (path: string): string =>
  encodeURIComponent(path).replace(/[()]/g, (c) => (c === '(' ? '%28' : '%29'));

/** 查询参数解码：非法百分号编码返回 null，调用方退化为纯文本而不是抛 URIError — 小杨-2026-10-22 */
export const decodePathParam = (value: string): string | null => {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
};

/**
 * 行号查询串（**唯一格式** `&line=start-end`）：无行区间 → 空串。
 * 2026-11-02 小欧 - 三个深链拼装点原各写一遍模板，且 file-ref 还另用 `&line=start` 单值格式
 *   （两种格式下游都要兼容 = 口径分裂），统一到本函数 — 小欧-2026-11-02
 */
const lineQuery = (
  lineRange?: { start: number; end: number } | null
): string => (lineRange ? `&line=${lineRange.start}-${lineRange.end}` : '');

/**
 * `/files?path=…&line=…` 的**唯一**拼装点（相对项目根的 posix 路径）。
 * @param relPath 相对项目根的 posix 路径
 * @param lineRange 行区间（可选）；给定则拼 `&line=start-end`
 */
export const buildFileDeepLink = (
  relPath: string,
  lineRange?: { start: number; end: number } | null
): string => `/files?path=${encodePathParam(relPath)}${lineQuery(lineRange)}`;

/**
 * 项目根**外**路径深链：`/files?ext=1&path=<绝对路径>`（外部只读预览 / 外部目录树）。
 * @param absPath 盘符绝对路径（如 `E:\outside\a.py`）
 */
const buildExternalDeepLink = (
  absPath: string,
  lineRange?: { start: number; end: number } | null
): string =>
  `/files?ext=1&path=${encodePathParam(absPath)}${lineQuery(lineRange)}`;

/** 目录形归尾：去重复尾分隔符后补单个 `/`（幂等）— 小欧-2026-10-23 */
const withDirTail = (absPath: string): string =>
  `${absPath.replace(ENDS_WITH_SEP_RE, '')}/`;

/**
 * `/file-ref?path=…` 的**唯一**拼装点（正文 markdown 内部链接，href 存原文）。
 * 2026-11-02 小欧 - 自 FileRefChip.toFileRefMarkdown 迁入：全前端 URL 形态只剩
 *   `/files?...` 与 `/file-ref?...` 两种，且都只在本文件拼 — 小欧-2026-11-02
 * @param lineRange 行区间（可选）；与另两个深链同走 lineQuery，不再单独拼 `&line=n`
 */
const buildFileRefLink = (
  rawPath: string,
  lineRange?: { start: number; end: number } | null
): string =>
  `/file-ref?path=${encodePathParam(rawPath)}${lineQuery(lineRange)}`;

/** 正文 file-ref 链接的解析结果 */
export interface FileRefLinkParts {
  /** 解码后的原始路径 */
  rawPath: string;
  /** 行区间；无行号时为 null */
  lineRange: { start: number; end: number } | null;
}

/**
 * `/file-ref?path=…&line=a-b` 的**唯一**解析点（`buildFileRefLink` 的逆运算）。
 * 2026-11-02 小欧 - MarkdownBody / MarkdownText 各写一份解析正则（DRY 违规、口径还会漂），
 *   统一收到这里；非法百分号编码返回 null，调用方退化为纯文本，不抛 URIError — 小欧-2026-11-02
 */
export const parseFileRefLink = (href: string): FileRefLinkParts | null => {
  const m = /^\/file-ref\?path=([^&]*)(?:&line=(\d+)(?:-(\d+))?)?$/.exec(href);
  if (!m) return null;
  const rawPath = decodePathParam(m[1]);
  if (rawPath === null) return null;
  const lineRange = m[2]
    ? { start: Number(m[2]), end: m[3] ? Number(m[3]) : Number(m[2]) }
    : null;
  return { rawPath, lineRange };
};

/** 唯一路径解析选项 */
export interface PathTargetOptions {
  /** 工具语义声明该路径必为目录（对「路径==项目根」不生效） */
  dirHint?: boolean;
  /** 行号区间（目录不带行号） */
  lineRange?: { start: number; end: number } | null;
  /**
   * 严格形态：根外路径必须带形态信号（扩展名 / 尾分隔符 / dirHint）才出链接。
   * 仅工具参数（PathLink）用 true —— 参数不可信，不把 `F:\my docs` 猜成目录；
   * 正文 chip / 文件页用默认 false（正文里 `F:\a\b` 就是目录）— 小欧-2026-11-02
   */
  strictShape?: boolean;
}

/** 唯一路径解析结果：内外 / 目录 / 相对路径 / 深链 URL 一次算全 */
export interface PathTarget {
  /** 是否可生成深链 */
  linked: boolean;
  /** 根内相对路径（posix）；根外或不可链接时为 null */
  rel: string | null;
  /** 深链 URL；linked=false 时为空串 */
  url: string;
  /** 目录形态 */
  isDir: boolean;
  /** 根外：盘符绝对且不在项目根内 */
  isExternal: boolean;
  /** 归属未定（盘符绝对路径但根未取回）：调用方应等根重算，不得当「找不到」报错 */
  pending: boolean;
  /** linked=false 时的原因（给 Tooltip 用；linked=true 时为 undefined） */
  reason?: string;
}

/**
 * **唯一路径解析函数** —— 任意来源的路径 + 项目根 → (内外 / 目录 / 相对 / 深链 URL / 不可链接原因)。
 * 判内外只读 toRelativePath 的结果（`''` = 等于根 → 根内），判目录只调 isDirPath/isAbsDirLikePath，
 * URL 只调本文件 build*。
 * 2026-11-02 小欧 - 全前端路径判定收敛到此一处；不可链接原因也在此给出，
 *   调用方禁止再二次判形态猜原因 — 小欧-2026-11-02
 */
export const resolvePathTarget = (
  rawPath: string,
  root: string,
  opts: PathTargetOptions = {}
): PathTarget => {
  const raw = rawPath.trim();
  const dirHint = !!opts.dirHint;
  const strictShape = !!opts.strictShape;
  const lineRange = opts.lineRange ?? null;
  const abs = isDriveAbsPath(raw);
  // relRaw：`''` = 就是项目根自身，null = 根外 / 根未取回 / 形态不合法。
  // 2026-11-02 小欧 - 内外判定直接读它，不再另调 isUnderRoot 把同一段前缀比对算第二遍 — 小欧-2026-11-02
  const relRaw = toRelativePath(raw, root);
  const rel = relRaw || null;
  // 「路径 == 项目根」：目录声明不生效（否则把项目根当外部目录挂 __ext__ 树）
  const rootSelf = !!root && abs && samePath(raw, root);
  // 目录判据三来源（判据本身仍只调 isDirPath / isAbsDirLikePath，不在此重写形态）：
  //   ① 尾分隔符（唯一可靠形态信号）；② 宽松口径下无扩展名的盘符绝对路径按目录认；
  //   ③ 工具语义声明 dirHint —— 路径等于项目根时不生效（见上方 rootSelf）
  const isDir =
    isDirPath(raw) ||
    (!strictShape && isAbsDirLikePath(raw)) ||
    (dirHint && !rootSelf);
  // 形态不成立（空 / 控制字符）时 relRaw 也为 null，但那不是「根外」，故先过形态门
  const shaped = !!raw && !hasCtrlChar(raw);
  const isExternal = shaped && !!root && abs && relRaw === null;
  const pending = abs && !root;
  const miss = (reason: string): PathTarget => ({
    linked: false,
    rel,
    url: '',
    isDir,
    isExternal,
    pending,
    reason,
  });

  if (!raw) return miss('路径为空，未做链接');
  if (hasCtrlChar(raw)) return miss('路径含换行/控制字符，未做链接');
  // 盘符绝对路径但根未取回 → 归属未定，等根（不给错归属、不造假链接）
  if (pending) return miss('项目根尚未加载，暂时无法打开');

  if (isExternal) {
    // 严格形态：无扩展名无尾分隔符又无 dirHint → 前端无法区分文件/目录，不出假链接
    if (strictShape && !isFileLikePath(raw) && !isDirPath(raw) && !dirHint)
      return miss('不是可识别的文件路径（无扩展名与尾分隔符），未做链接');
    return {
      linked: true,
      rel: null,
      isDir,
      isExternal: true,
      pending: false,
      // 根外目录补尾 `/`（文件页靠尾分隔符判目录），目录不带行号
      url: isDir
        ? buildExternalDeepLink(withDirTail(raw), null)
        : buildExternalDeepLink(raw, lineRange),
    };
  }

  // 2026-11-02 小欧 - rel 由 toRelativePath 给出，形态校验已在 relFromRoot 单点完成
  //   （含 `..` / UNC / 根斜杠），此处不再复检同一件事 — 小欧-2026-11-02
  if (!rel) return miss('路径不在项目根内（或形态不合法），无法在文件页打开');
  // 目录（尾分隔符 / 无扩展名盘符绝对目录 / dirHint）不必过 isLinkableRelPath：
  //   否则根内目录 `E:\root\sub` 归一成 `sub` 后被拒 → 点击回落成绝对路径内部深链 — 小欧-2026-11-02
  if (!isLinkableRelPath(rel) && !isDir)
    return miss('不是可识别的文件路径（无分隔符与扩展名），未做链接');
  return {
    linked: true,
    rel,
    isDir,
    isExternal: false,
    pending: false,
    url: buildFileDeepLink(rel, isDir ? null : lineRange),
  };
};

// ===== 正文路径识别（2026-11-02 小欧 - 自 components/markdown/pathDetect.ts 并入）=====
// 并入理由：识别只调用本文件的判据，拆两个文件就必须跨文件 import 判据（DRY 违规），
// 且「路径规则变了」是同一个变化原因 —— 判据 / 拼装 / 解析 / 识别 属同一模块职责。
// 本段仍是纯函数：无 JSX、无 React、无网络。

/**
 * 裸路径识别的终止字符：空白、成对符号、引号、反引号、中英文标点。
 * 路径内合法的 `- . _ / \` 均不在内；中文路径段仍可识别。
 */
const PATH_STOP = '\\s<>()\\[\\]{}"\'`|,;，。；：！？、（）【】《》“”‘’';
const PATH_EXT = `\\.[A-Za-z0-9]{1,${EXT_MAX}}`;
const PATH_ABS = `[A-Za-z]:[\\\\/][^${PATH_STOP}]*${PATH_EXT}`;
/** 相对路径必须含分隔符；排除 `:` 防把 `路径:E:\\a.md` 的中文前缀并进路径 */
const PATH_REL = `[^${PATH_STOP}:\\\\/][^${PATH_STOP}:]*[\\\\/][^${PATH_STOP}:]*${PATH_EXT}`;
/**
 * 盘符绝对目录：尾分隔符收尾（`F:\a\b\`）。
 * 负向前瞻保证不把 `F:\a\b\c.md` 的前缀当目录（否则文件被截成目录 + 残余文件名）。
 * 相对目录不自动识别（正文里的“答复/思考”不是路径）。
 */
const PATH_SEG = `[^${PATH_STOP}:\\\\/]+`;
const PATH_ABS_DIR = `[A-Za-z]:[\\\\/](?:${PATH_SEG}[\\\\/])+(?![^${PATH_STOP}:\\\\/])`;
/**
 * 盘符绝对目录**不带尾分隔符**（`F:\a\b`）：无扩展名的盘符绝对路径按目录认。
 * 2026-11-01 小欧 - 至少 2 段（`F:\a\b`）挡掉「F:\my docs\…」把 `F:\my` 认成目录；尾部不让位给后续段 — 小欧-2026-11-01
 */
const PATH_ABS_NOTAIL = `[A-Za-z]:[\\\\/](?:${PATH_SEG}[\\\\/])+${PATH_SEG}(?![^${PATH_STOP}:])`;

// 2026-11-01 小欧 - 空格容差（盘符绝对专用）：正则只圈「无硬终止符的最大 run」（空白可入 run），
//   谁是文件/目录交 resolveAbsCand 裁决；run 内多条路径按盘符锚切段逐条识别，残余回扫不丢 token — 小欧-2026-11-01
/** run 硬终止集 = 原终止集去掉 `\s`（空白正是要容差的分隔）+ 显式换行/制表 */
const RUN_STOP = '<>()\\[\\]{}"`\'|,;，。；：！？、（）【】《》“”‘’\\n\\r\\t';
/** 空格容差 run：至少含一个空白（与严格三分支互斥，严格优先；正则不过刀，只圈界碑） */
const PATH_ABS_SP = `[A-Za-z]:[\\\\/](?=[^${RUN_STOP}]*[\\s])[^${RUN_STOP}]*`;

/**
 * 单趟识别四类 token（顺序即优先级；命中段整体跳过，不产生重叠）：
 *   ① 显式标记 `[[文件:path#L1-L2]]`
 *   ② 已有 markdown 链接/图片 —— 原样保留，防二次转换
 *   ③ URL —— 原样保留（早于裸路径，防 `https://x/a.md` 被当成相对路径）
 *   ④ 裸绝对路径（盘符）/绝对目录/含目录的相对路径 —— 转链接（href 存原文），其余原样
 *   ⑤ 空格容差 run（盘符绝对专用）—— 由 convertRuns 循环裁出候选，残余回扫
 */
const FILE_REF_TOKEN_RE = new RegExp(
  // 2026-10-22 小欧 - markPath 允许含 ']'（此前排除 ']' 导致 `[[文件:a[1].md]]` 整条匹配不上，
  //   路径含方括号时标记退化成原文 —— 回归）。改为**惰性匹配到首个 ']]' 收尾**：
  //   路径里的 ']' 由 escapeLabel 转义、参数由 encodePathParam 编码，两端都能还原 — 小欧-2026-10-22
  '\\[\\[文件:(?<markPath>[^|\\n]+?)(?:#L(?<markFrom>\\d+)(?:-L?(?<markTo>\\d+))?)?\\]\\]' +
    '|!?\\[[^\\]]*\\]\\([^)]*\\)' +
    '|(?:https?|ftp|file):\\/\\/[^\\s<>()]+' +
    // 2026-11-01 小欧 - lead 增中文：正文常写「写入到F:\…」「见F:\…」，无空格中文紧贴路径也算界碑 — 小欧-2026-11-01
    `|(?<lead>^|[\\s“”‘’《》（(【，,;；:：=*\\u4e00-\\u9fff])(?:(?<bareDirAbs>${PATH_ABS_DIR})|(?<bareAbs>${PATH_ABS})|(?<bareRel>${PATH_REL})|(?<spacedAbs>${PATH_ABS_SP})|(?<bareAbsNoTail>${PATH_ABS_NOTAIL}))`,
  'gu'
);

interface FileRefTokenGroups {
  markPath?: string;
  markFrom?: string;
  markTo?: string;
  lead?: string;
  bareDirAbs?: string;
  bareAbs?: string;
  bareRel?: string;
  /** 2026-11-01 小欧 - 无扩展名的盘符绝对路径（按目录认），如 `F:\a\b` */
  bareAbsNoTail?: string;
  /** 2026-11-01 小欧 - 空格容差 run（盘符绝对专用），截断由 convertRuns policy 裁决 */
  spacedAbs?: string;
}

/** label 里的方括号与反斜杠要转义，否则 markdown 链接解析被截断 */
const escapeLabel = (p: string): string => p.replace(/([[\]\\])/g, '\\$1');

/** 形态/安全门槛：控制字符与 `..` 穿越不是可链接路径（绝对路径同样适用） */
const isBadPath = (p: string): boolean =>
  !p || hasCtrlChar(p) || hasParentTraversal(p);

/**
 * 中文粘连剥离：token 尾部紧贴中文（无空格，如 `…563e目录：`）时把中文串还回正文。
 * 2026-11-01 小欧 - 只剥「ASCII 字母/数字之后起头」的中文串：`F:\项目\报告` 的中文段起于
 *   分隔符后 → 不剥（保全中文目录名）；一次剥不干净时由 convertRuns 残余回扫继续处理 — 小欧-2026-11-01
 */
const CJK_GLUE_RE = /[A-Za-z0-9]([\u4e00-\u9fff]+)$/;
const trimCjkGlue = (raw: string): { path: string; rest: string } => {
  const m = CJK_GLUE_RE.exec(raw);
  if (!m) return { path: raw, rest: '' };
  const cut = raw.length - m[1].length;
  return { path: raw.slice(0, cut), rest: raw.slice(cut) };
};

// 2026-11-01 小欧 - run 裁决 policy（SRP：正则只圈界碑，切哪一条交这里）— 小欧-2026-11-01
/** run 内按盘符锚切段：`F:\a b\x.md F:\c.md` 两条路径各自成段，后一条不被前一条吞掉 */
const absSegments = (run: string): string[] =>
  run.split(/(?=[A-Za-z]:[\\/])/).filter(Boolean);

/**
 * 段内扩展名锚（取**末个**）：`AI Agent架构…探索.md` 与 `v2.0 plan.md` 的 `.0` 都让位给真扩展名。
 * 2026-11-02 小欧 - 长度口径由 EXT_MAX 单点提供（原此处硬编码 10，与 HAS_EXT_RE 的 8 两套）— 小欧-2026-11-02
 */
const EXT_ANCHOR_SRC = `\\.[A-Za-z0-9]{1,${EXT_MAX}}(?![A-Za-z0-9./\\\\])`;

/**
 * 段内裁决 → {path, rest}：
 *   有扩展名锚 → 取**末个**锚截断为文件（多词文件名 `AI Agent架构…探索.md` 与版本号
 *     `v2.0 plan.md` 的 `.0` 都让位给真扩展名）；
 *   无锚 → 「分隔符紧跟空白/行尾」截断为带空格目录（`F:\my docs\proj\ 下有很多文件`）；
 *   再退一步 → run 的**无空白前缀**（≥2 段）当目录（`F:\a\b 已就绪` 里目录不带尾分隔符）；
 *   都没有 → null（原文退回，不造假链接）。
 */
const resolveAbsCand = (seg: string): { path: string; rest: string } | null => {
  // ⚠ 局部正则带 g 只在本函数内跑完，lastIndex 不跨调用残留（不建模块级 g 正则）
  const ext = new RegExp(EXT_ANCHOR_SRC, 'g');
  let hit: RegExpExecArray | null = null;
  for (let m = ext.exec(seg); m; m = ext.exec(seg)) hit = m;
  if (hit) {
    const end = hit.index + hit[0].length;
    return { path: seg.slice(0, end), rest: seg.slice(end) };
  }
  const dir = /[\\/](?=\s|$)/.exec(seg);
  if (dir) {
    const end = dir.index + 1;
    return { path: seg.slice(0, end), rest: seg.slice(end) };
  }
  // 2026-11-01 小欧 - 三退：无空白前缀即目录（≥2 段才认，挡 `F:\my docs…` 把 `F:\my` 当目录；
  //   去尾 `:` —— run 硬终止集不含 ASCII 冒号，`F:\a\b: 说明` 的冒号会粘进候选）— 小欧-2026-11-01
  const head = (seg.split(/\s/)[0] ?? '').replace(/:+$/, '');
  if (head !== seg && (head.match(/[\\/]/g) ?? []).length >= 2) {
    return { path: head, rest: seg.slice(head.length) };
  }
  return null;
};

/**
 * 空格容差 run → 首条候选路径（切段 → 段内裁决 → 剥中文粘连），`rest` = run 里未被路径消费的残余。
 * 2026-11-02 小欧 - convertRuns 的 ⑤ 分支与 toWholePathLink 原各写一遍这三步流水线，
 *   任一步改动漏另一处即口径漂移 — 小欧-2026-11-02
 */
const spacedPath = (run: string): { path: string; rest: string } | null => {
  const seg = resolveAbsCand(absSegments(run)[0] ?? '');
  if (!seg) return null;
  const pure = trimCjkGlue(seg.path);
  return { path: pure.path, rest: `${seg.rest}${pure.rest}` };
};

/**
 * 裸路径、行内代码、显式标记**共用的链接构造**（唯一真源，DRY）：
 *   @/# 开头（npm 包名 @scope/pkg、锚点 #L12）不是文件路径 → null；
 *   href **存原文**（chip 显示原文，由文件页入口归一绝对/相对，不在此处重拼根）；
 *   裸文件名（无目录）不自动转（无从精确定位）；显式标记允许无目录；
 *   相对目录不自动识别；盘符绝对目录等根取回再出 chip（归属未定）。
 *   调用方拿到 null 一律留原文，不造假链接。
 */
const toFileRefMarkdown = (
  raw: string,
  projectRoot?: string,
  explicit = false,
  lineRange?: { start: number; end: number } | null,
  asDir = false
): string | null => {
  if (isBadPath(raw)) return null;
  if (raw.startsWith('@') || raw.startsWith('#')) return null;
  // 2026-11-01 小欧 - asDir：调用方已判定为目录（无尾分隔符的盘符绝对路径），不必自己再猜 — 小欧-2026-11-01
  const dir = asDir || isDirPath(raw);
  const abs = isDriveAbsPath(raw);
  if (dir) {
    // 绝对目录：根未取回时分不清内/外，等根（宁可晚一拍，也不给错归属）
    if (abs && !projectRoot) return null;
    // 相对目录：仅显式标记可点（正文里的“答复/思考”不是路径）
    if (!abs && !explicit) return null;
    // 显式标记可绕过「必须含分隔符」，但绕不过形态门槛（UNC / 根斜杠 / `..`）
    if (!abs && !isValidRelPath(raw)) return null;
  } else if (!abs) {
    // 2026-11-02 小欧 - toRelativePath 已保证 rel 形态合法（relFromRoot 内唯一校验点），
    //   此处不再复检 isValidRelPath — 小欧-2026-11-02
    const rel = toRelativePath(raw, projectRoot);
    if (!rel) return null;
    // 2026-10-23 小欧 - 判“有没有目录”看原文（`./a.md` 显式带当前目录，不算裸文件名）— 小欧-2026-10-23
    if (!explicit && !hasSeparator(raw)) return null;
    if (!isLinkableRelPath(rel)) return null;
  }
  return `[${escapeLabel(raw)}](${buildFileRefLink(raw, lineRange)})`;
};

/**
 * 单趟前向扫描：命中即追加替换结果，**⑤ 只吃自己那一条候选**，残余留在 text 里由本循环继续扫
 * （字符串替换结果不参与二次扫描 → 旧版 replace 会把同行后续路径整段吞掉，此处从机制上消除）。
 */
const convertRuns = (text: string, projectRoot?: string): string => {
  let out = '';
  let pos = 0;
  for (;;) {
    FILE_REF_TOKEN_RE.lastIndex = pos;
    const m = FILE_REF_TOKEN_RE.exec(text);
    if (!m) break;
    const whole = m[0];
    const g = (m.groups ?? {}) as FileRefTokenGroups;
    const lead = g.lead ?? '';
    let piece = whole;
    let consumed = whole.length;

    if (g.markPath) {
      // 2026-10-23 小欧 - 显式标记是 Agent 的明确引用：允许无目录相对名；href 存原文 — 小欧-2026-10-23
      const lineRange =
        g.markFrom && !isDirPath(g.markPath)
          ? { start: Number(g.markFrom), end: Number(g.markTo ?? g.markFrom) }
          : null;
      // 整条标记已被正则吃掉，消费长度即 whole（残余不参与回扫）
      piece =
        toFileRefMarkdown(g.markPath, projectRoot, true, lineRange) ?? whole;
    } else {
      // 2026-11-02 小欧 - 三个裸路径分支只负责裁出候选与目录语义，链接构造/消费长度在下方统一 —
      //   原三分支各写一遍 piece/consumed（DRY）— 小欧-2026-11-02
      let cand: { path: string } | null = null;
      let asDir = false;
      if (g.spacedAbs) {
        // 2026-11-01 小欧 - ⑤ 空格容差：只吃首段裁决出的那一条，锚后残余（散文/后续路径）回扫不丢 — 小欧-2026-11-01
        cand = spacedPath(g.spacedAbs);
        // 与 bareAbsNoTail 同口径：无扩展名的盘符绝对目录按目录认
        asDir = !!cand && isAbsDirLikePath(cand.path);
      } else if (g.bareAbsNoTail) {
        // 2026-11-01 小欧 - 无扩展名的盘符绝对路径（`F:\a\b`）按目录出 chip：正文里目录常不带尾分隔符 — 小欧-2026-11-01
        cand = trimCjkGlue(g.bareAbsNoTail);
        asDir = true;
      } else {
        // 2026-11-01 小欧 - 尾部仍可能粘中文（`a.md是文件`）：剥掉中文串后残余回扫 — 小欧-2026-11-01
        const raw = g.bareDirAbs ?? g.bareAbs ?? g.bareRel;
        cand = raw ? trimCjkGlue(raw) : null;
      }
      const link = cand
        ? toFileRefMarkdown(cand.path, projectRoot, false, null, asDir)
        : null;
      if (cand && link) {
        piece = `${lead}${link}`;
        consumed = lead.length + cand.path.length;
      }
    }

    out += text.slice(pos, m.index) + piece;
    pos = m.index + Math.max(consumed, 1);
  }
  return out + text.slice(pos);
};

/**
 * 行内代码的**形态**门槛：整段无空白且末段是字母开头扩展名（`a.md` / `x.json`）。
 * 排除版本号（`1.2.3`）、无扩展名片段（`dsh-root`）；@/# 前缀统一由 toFileRefMarkdown 拒。
 * 2026-11-02 小欧 - 原名 isPathLike，与 paramCategories.isPathLike（判参数值）同名异义，改名消歧 — 小欧-2026-11-02
 */
const LAST_SEGMENT_FILE_RE = new RegExp(
  `\\.[A-Za-z][A-Za-z0-9]{0,${EXT_MAX - 1}}$`
);
const isInlineCodePath = (raw: string): boolean => {
  if (!raw || /\s/.test(raw)) return false;
  // 2026-10-23 小欧 - 行内代码里的目录只认盘符绝对（相对目录不自动识别）— 小欧-2026-10-23
  if (isDirPath(raw)) return isDriveAbsPath(raw);
  return LAST_SEGMENT_FILE_RE.test(baseName(raw));
};

const INLINE_CODE_RE = /(`+)([^`]*?)\1/g;

/** 行内代码整段就是一个路径时才转链接；夹带其他文字一律原样，避免把示例改成可点链接 */
const toWholePathLink = (code: string, projectRoot?: string): string | null => {
  const raw = code.trim();
  if (isInlineCodePath(raw)) return toFileRefMarkdown(raw, projectRoot);
  // 2026-11-01 小欧 - 行内代码里的**无扩展名盘符目录**（`` `F:\a\b` ``）：反引号已是天然界碑，
  //   语义唯一 → 按目录转（此前只认带尾 `\`，Agent 常写 `` `F:\test_dir\2026...`目录 `` 一直不识别）— 小欧-2026-11-01
  if (isAbsDirLikePath(raw))
    return toFileRefMarkdown(raw, projectRoot, false, null, true);
  // 2026-11-01 小欧 - 带空格盘符路径（文件/目录同规则）：整段即路径才转，有残余 = 语义不唯一 → 原文 — 小欧-2026-11-01
  if (!isDriveAbsPath(raw) || !/\s/.test(raw)) return null;
  const cand = spacedPath(raw);
  if (!cand || cand.rest) return null;
  return toFileRefMarkdown(
    cand.path,
    projectRoot,
    false,
    null,
    isAbsDirLikePath(cand.path)
  );
};

/** 行内代码段按整段路径转换，其余文字走裸路径识别 */
const convertOutsideInline = (line: string, projectRoot?: string): string => {
  let out = '';
  let last = 0;
  INLINE_CODE_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = INLINE_CODE_RE.exec(line)) !== null) {
    out += convertRuns(line.slice(last, m.index), projectRoot);
    out += toWholePathLink(m[2], projectRoot) ?? m[0];
    last = m.index + m[0].length;
  }
  return out + convertRuns(line.slice(last), projectRoot);
};

/**
 * 预处理：只转围栏外的标记，块内标记原样保留（代码块内不生效）
 *   2026-10-23 小欧 - 除显式 `[[文件:]]` 外，也识别 Agent 直接写的裸路径：
 *     含目录的相对路径、盘符绝对文件、盘符绝对目录转链接（href 存原文）；
 *     裸文件名、相对目录、非法形态原样。— 小欧-2026-10-23
 *
 * 2026-10-21 小杨 - 修复（先红后绿抓出的真缺陷）：
 *   设计稿原用 `text.split(/(^```[\s\S]*?(?:^```|$))/m)` 想"按围栏切段"，
 *   但 **multiline 下的 `$` 匹配的是"任意行尾"**，于是 `[\s\S]*?` 会在第一行行尾
 *   （`$`）就收尾 → 围栏段只切出 "```" 一行，其后的标记仍落在"非围栏段"里被转换
 *   → **围栏内的 [[文件:]] 照样被转**（"代码块内不生效"这条硬要求失效）。
 *   改为**行级状态机**：逐行判"是否围栏行"，围栏内整行跳过 —— 语义直白、无正则歧义。
 *   2026-10-21 小杨 - 同时支持 ~~~ 围栏与行内代码；按围栏字符+长度配对关闭 — 小杨-2026-10-21
 */
export const preprocessFileRefs = (
  text: string,
  projectRoot?: string
): string => {
  const lines = text.split('\n');
  let fence: { char: string; len: number } | null = null;
  return lines
    .map((line) => {
      const mark = /^\s*(`{3,}|~{3,})/.exec(line);
      if (fence) {
        if (mark && mark[1][0] === fence.char && mark[1].length >= fence.len)
          fence = null;
        return line;
      }
      if (mark) {
        fence = { char: mark[1][0], len: mark[1].length };
        return line;
      }
      return convertOutsideInline(line, projectRoot);
    })
    .join('\n');
};
