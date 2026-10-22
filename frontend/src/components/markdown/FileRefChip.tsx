// 编辑历史: 2026-10-21 小杨 - 新建：chip + 预处理 + 形态校验三件同文件；
//   生成链接的 label 去 📄 emoji（chip 自带图标，防双重图标）；
//   深链改走 buildFileDeepLink（唯一拼装点）— 小杨-2026-10-21
// 2026-10-22 小杨 - 预处理增 ~~~ 围栏与行内代码跳过、路径含方括号的惰性匹配与 label 转义；
//   chip 补键盘可达（role=link + tabIndex + Enter/Space）— 小杨-2026-10-22
// 2026-10-22 小欧 - 预处理增裸路径识别：答复/思考里 Agent 直接写的相对路径或项目根内绝对路径
//   也转成 /file-ref 链接；URL、markdown 链接、围栏/行内代码一律原样；
//   判据复用 utils/projectPath（toRelativePath/isLinkableRelPath），不另立一套 — 小欧-2026-10-22
// 2026-10-22 小欧 - 行内代码**整段就是一个路径**时也转链接（Agent 普遍把产物路径写成 `E:\...`）；
//   夹带其他文字的行内代码仍原样，避免把示例改成可点链接 — 小欧-2026-10-22
// 2026-10-22 小欧 - 防过度处理：可转路径须末段字母开头扩展名 + 拒 @/# 开头（npm 包名、锚点不转）；
//   chip 文字直接显示**完整绝对路径**并删除 tip — 小欧-2026-10-22
// 2026-10-22 小欧 - 修复三处：① 显式标记字符类误写 [^|\]]+? 断了方括号文件名（a[1].md）
//   通道 → 恢复 [^|]+? 惰性锚定 ']]'（回归由 path-link-consistency/S23 两测抓出）；
//   ② 链接构造两份（裸路径/行内代码）抽 toFileRefMarkdown 单一真源（DRY）；
//   ③ chip 拼展示文案抽 displayPathOf；删死参数 label（chip 文字已恒为绝对路径，YAGNI）— 小欧-2026-10-22
// 2026-10-22 小沈 - 清除违规注释（删除"三堂会审"等过期裁定字符）— 小沈-2026-10-22
/**
 * FileRefChip —— Agent 输出的文件引用卡片
 *
 * 三件事同文件（DRY）：
 * 1. chip 渲染（不可删除：它是 Agent 的输出，不是用户的引用）
 * 2. `preprocessFileRefs`：把 `[[文件:path#L1-L2]]` 与裸路径转成标准 markdown 链接
 *    （围栏代码块内不转；行内代码仅当**整段就是一个路径**时转）
 * 3. `isValidRelPath`：前端**形态**校验唯一一份（绝对路径/UNC/`..` 一律不合格）
 *
 * ⚠ 权威判定在后端：前端只做形态校验，路径是否真在项目根内由后端 `/files/read` 判界，
 *   校验不过的链接**退化为纯文本**，不造假链接。
 */
import React from 'react';
import { FileOutlined } from '@ant-design/icons';
import { useNavigate, useInRouterContext } from 'react-router-dom';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';
import { buildFileDeepLink, encodePathParam } from '@/utils/fileDeepLink';
import {
  isLinkableRelPath,
  toAbsolutePath,
  toRelativePath,
} from '@/utils/projectPath';
import { useProjectRoot } from '@/hooks/useProjectRoot';

export interface FileRefChipProps {
  relPath: string;
  lineRange?: { start: number; end: number };
}

/** chip 外观（两种导航形态共用，避免两处样式漂移） */
const chipStyle: React.CSSProperties = {
  background: chatTokens.colorPrimaryBg,
  color: Colors.TEXT.STRONG,
  border: `1px solid ${Colors.BORDER.LIGHT}`,
  borderRadius: chatTokens.radius,
  padding: `0 ${Spacing.SM}px`,
  cursor: 'pointer',
};

/** 形态：不可删除（Agent 的输出，不是用户的引用）；校验不过由调用方退化为纯文本，不渲染 chip */
const ChipBody: React.FC<FileRefChipProps & { onGo: () => void }> = ({
  relPath,
  lineRange,
  onGo,
}) => {
  // 2026-10-22 小欧 - chip 文字直接显示**完整绝对路径**（项目根 + 相对路径），不再靠 tip；
  //   根取不到时退相对路径（不造假）— 小欧-2026-10-22
  const projectRoot = useProjectRoot();
  const abs = toAbsolutePath(relPath, projectRoot);
  const fullPath = abs
    ? projectRoot.includes('\\')
      ? abs.replace(/\//g, '\\') // 根是 Windows 形态时展示统一反斜杠
      : abs
    : relPath;
  return (
    <span
      role="link"
      tabIndex={0}
      aria-label={`打开文件 ${fullPath}${
        lineRange ? ` 第 ${lineRange.start} 至 ${lineRange.end} 行` : ''
      }`}
      style={{
        ...chipStyle,
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.XS,
      }}
      onClick={onGo}
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        onGo();
      }}
    >
      <FileOutlined style={{ color: Colors.PRIMARY, flexShrink: 0 }} />{' '}
      {fullPath}
      {lineRange ? `#L${lineRange.start}-L${lineRange.end}` : ''}
    </span>
  );
};

/**
 * FileRefChip —— Agent 输出的文件引用卡片
 *
 * ⚠ 为什么不用 `useNavigate` 直接写：markdown 渲染层**可能不在 Router 上下文内**
 *   （单测直接渲染 MarkdownSlot、设置页安全Tab 独立渲染），此时 useNavigate 会抛
 *   "useNavigate() may be used only in the context of a <Router> component" → 整块渲染崩。
 *   故用 `useInRouterContext()` 在**组件级**分流（不是条件调用 Hook，合法）：
 *   在 Router 内 → SPA 跳转；不在 → 退化为整页跳转（window.location.assign）。
 */
export const FileRefChip: React.FC<FileRefChipProps> = (props) => {
  const inRouter = useInRouterContext();
  const url = buildFileDeepLink(props.relPath, props.lineRange ?? null);
  if (inRouter) {
    return <ChipWithRouter {...props} url={url} />;
  }
  return (
    <ChipBody
      {...props}
      onGo={() => {
        window.location.assign(url);
      }}
    />
  );
};

/** Router 内的形态（单独一层组件，保证 useNavigate 只在有 Router 时被调用） */
const ChipWithRouter: React.FC<FileRefChipProps & { url: string }> = ({
  relPath,
  lineRange,
  url,
}) => {
  const nav = useNavigate();
  return (
    <ChipBody
      relPath={relPath}
      lineRange={lineRange}
      onGo={() => {
        nav(url);
      }}
    />
  );
};

/** 前端形态校验唯一一份（不碰符号链接/代码根禁区这类后端语义） */
export function isValidRelPath(p: string): boolean {
  if (!p || /^[a-zA-Z]:/.test(p) || p.startsWith('/') || p.startsWith('\\'))
    return false;
  return !p.split(/[\\/]/).includes('..');
}

/**
 * 裸路径识别的终止字符：空白、成对符号、引号、反引号、中英文标点。
 * 路径内合法的 `- . _ / \` 均不在内；中文路径段仍可识别。
 */
const PATH_STOP = '\\s<>()\\[\\]{}"\'`|,;，。；：！？、（）【】《》“”‘’';
const PATH_EXT = '\\.[A-Za-z0-9]{1,10}';
const PATH_ABS = `[A-Za-z]:[\\\\/][^${PATH_STOP}]*${PATH_EXT}`;
/** 相对路径必须含分隔符；排除 `:` 防把 `路径:E:\\a.md` 的中文前缀并进路径 */
const PATH_REL = `[^${PATH_STOP}:\\\\/][^${PATH_STOP}:]*[\\\\/][^${PATH_STOP}:]*${PATH_EXT}`;

/**
 * 单趟识别三类 token（顺序即优先级，替换结果不会被二次扫描）：
 *   ① 显式标记 `[[文件:path#L1-L2]]`
 *   ② 已有 markdown 链接/图片 —— 原样保留，防二次转换
 *   ③ URL —— 原样保留（早于裸路径，防 `https://x/a.md` 被当成相对路径）
 *   ④ 裸绝对路径（盘符）或裸相对路径 —— 根内才转链接，其余原样
 */
const FILE_REF_TOKEN_RE = new RegExp(
  // 2026-10-22 小欧 - markPath 允许含 ']'（此前排除 ']' 导致 `[[文件:a[1].md]]` 整条匹配不上，
  //   路径含方括号时标记退化成原文 —— 回归）。改为**惰性匹配到首个 ']]' 收尾**：
  //   路径里的 ']' 由 escapeLabel 转义、参数由 encodePathParam 编码，两端都能还原 — 小欧-2026-10-22
  '\\[\\[文件:(?<markPath>[^|\\n]+?)(?:#L(?<markFrom>\\d+)(?:-L?(?<markTo>\\d+))?)?\\]\\]' +
    '|!?\\[[^\\]]*\\]\\([^)]*\\)' +
    '|(?:https?|ftp|file):\\/\\/[^\\s<>()]+' +
    `|(?<lead>^|[\\s（(【，,;；:：=*])(?:(?<bareAbs>${PATH_ABS})|(?<bareRel>${PATH_REL}))`,
  'gu'
);

interface FileRefTokenGroups {
  markPath?: string;
  markFrom?: string;
  markTo?: string;
  lead?: string;
  bareAbs?: string;
  bareRel?: string;
}

/** label 里的方括号与反斜杠要转义，否则 markdown 链接解析被截断 */
const escapeLabel = (p: string): string => p.replace(/([[\]\\])/g, '\\$1');

/**
 * 裸路径与行内代码**共用的链接构造**（唯一真源，DRY）：
 *   @/# 开头（npm 包名 @scope/pkg、锚点 #L12）不是文件路径 → null；
 *   归一为根内相对路径（utils/projectPath 唯一真源），根外/未取到根/形态不合格 → null；
 *   调用方拿到 null 一律留原文，不造假链接。
 */
const toFileRefMarkdown = (raw: string, projectRoot?: string): string | null => {
  if (raw.startsWith('@') || raw.startsWith('#')) return null;
  const rel = toRelativePath(raw, projectRoot);
  if (!rel || !isValidRelPath(rel) || !isLinkableRelPath(rel)) return null;
  return `[${escapeLabel(raw)}](/file-ref?path=${encodePathParam(rel)})`;
};

const convertRuns = (text: string, projectRoot?: string): string =>
  text.replace(FILE_REF_TOKEN_RE, (whole, ...rest) => {
    const g = rest[rest.length - 1] as FileRefTokenGroups;

    if (g.markPath) {
      if (!isValidRelPath(g.markPath)) return whole; // 非法即留原文，不造假链接
      const lines = g.markFrom
        ? `&line=${g.markFrom}${g.markTo ? `-${g.markTo}` : ''}`
        : '';
      // label 不带图标 emoji —— chip 自带 FileOutlined（防双重图标）
      return `[${escapeLabel(g.markPath)}](/file-ref?path=${encodePathParam(
        g.markPath
      )}${lines})`;
    }

    const raw = g.bareAbs ?? g.bareRel;
    if (!raw) return whole;
    const link = toFileRefMarkdown(raw, projectRoot);
    return link ? `${g.lead ?? ''}${link}` : whole;
  });

/**
 * 行内代码的**形态**门槛：整段无空白且末段是字母开头扩展名（`a.md` / `x.json`）。
 * 排除版本号（`1.2.3`）、无扩展名片段（`dsh-root`）；@/# 前缀统一由 toFileRefMarkdown 拒。
 */
const LAST_SEGMENT_FILE_RE = /\.[A-Za-z][A-Za-z0-9]{0,9}$/;
const isPathLike = (raw: string): boolean =>
  !!raw &&
  !/\s/.test(raw) &&
  LAST_SEGMENT_FILE_RE.test(raw.split(/[\\/]/).pop() || '');

const INLINE_CODE_RE = /(`+)([^`]*?)\1/g;

/** 行内代码整段就是一个路径时才转链接；夹带其他文字一律原样，避免把示例改成可点链接 */
const toWholePathLink = (code: string, projectRoot?: string): string | null => {
  const raw = code.trim();
  if (!isPathLike(raw)) return null;
  return toFileRefMarkdown(raw, projectRoot);
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
 *   2026-10-22 小欧 - 除显式 `[[文件:]]` 外，也识别 Agent 直接写的裸路径：
 *     相对路径原样；绝对路径按 projectRoot 归一为相对路径；根外/非法原样。
 *     判据复用 utils/projectPath，前端不另立一套根内规则。
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
