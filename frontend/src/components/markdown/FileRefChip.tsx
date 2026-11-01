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
// 2026-10-22 小沈 - 清除违规注释（删除""等过期定案字符）— 小沈-2026-10-22
// 2026-10-22 小欧 - 根外文件可点：toFileRefMarkdown/markPath 对根外盘符绝对路径生成外部链接
//   （/file-ref?path=绝对路径，chip 内部分流外部预览）；外部判据 isExternalAbsPath =
//   盘符绝对路径且归一到不了项目根内（根内绝对先归一相对走普通链接，不算外部）— 小欧-2026-10-22
// 2026-10-23 小欧 - 正文引用改**原文保真**：chip 显示正文原路径，不再用项目根补全（删 displayPathOf）；
//   目录（盘符绝对 + 尾分隔符）生成「目录」chip，外部目录只加标识不跳转；裸文件名不再生成链接。
//   链接 href 统一存原文，由文件页入口归一（绝对根内→相对、根外→外部预览）— 小欧-2026-10-23
//   2026-10-23 小欧 - 徽标文案「外部」改「根外」，与 project_root（项目根）概念对齐 — 小欧-2026-10-23
// 2026-10-28 小欧 - 点击用最新根：URL 不在渲染时固定（渲染时 useProjectRoot 快照在根切换后
//   时序窗口内持旧根 → 误判外部 → ext=1 URL）。FileRefChip/ChipWithRouter 的 onGo 改调
//   resolveChipUrl 实时取 getCurrentProjectRoot() 最新根算 ext=1 vs 普通深链；删渲染期
//   url 计算（含 buildExternalDeepLink/buildFileDeepLink 死 import）。ChipBody 仍用
//   useProjectRoot 算 navigable/根外徽标（显示用，点击不依赖）。— 小欧-2026-10-28
// 2026-10-28 小欧 - chip 增「别针」引用入口（与文件足迹同款，北京老陈令）：ChipBody 改双层
//   结构——外层 span 承担 chip 视觉，内层内容 span 承担 role=link/tabIndex/跳转，别针按钮
//   平铺兄弟位（role=link 内不放 button，防键盘/读屏语义冲突）；别针调 features/refs/
//   QuoteButton（quote.ts 唯一实现），仅文件 chip 出现、目录不出（引用只对文本文件）。— 小欧-2026-10-28
// 2026-10-29 小欧 - 删两处 resolveChipUrl 的 { source: 'chat' } 实参：该参数两支返回值相同（死参数，
//   同文件改动见 utils/fileDeepLink.ts），传了不产生任何差异；同时导航 state 只留 internal: true —
//   internal 已完整表达"站内跳转", source 是同一次跳转里恒真的重复判据(Files 页已按 DRY 收敛) — 小欧-2026-10-29
// 2026-11-01 - 小欧 - 空格容差（真退化疑案定案：非改错，是 10 月既定的 PATH_STOP 含 `\s`
//   边界撞上带空格文件名 `AI Agent架构模型深度研究与创新探索.md` 的既设计取舍）：
//   ⑤新分支盘符绝对 run（正则圈界碑/代码裁决）——首击扩展名锚截断 + 锚后紧跟 / \ . 让位
//   （版本号与路径中点不误锚），锚后残余原样放回；lead 类补**中文成对引符/书名号**界碑
//   （成对引符包路径今起可识别；ASCII 引号因与 JSON 字符串撞车禁入——J5 双反斜杠回归实证）；
//   行内代码带空格盘符路径整段全匹配才转。严格三分支优先级不动、相对路径不放开空格、
//   不查盘不造假链接（架构口径不变）— 小欧-2026-11-01
// 2026-11-01 小欧 - 修上一版退化并只增不减：单趟 replace 改手工 exec 循环，⑤ 只吃自己那条候选、
//   残余回同一循环继续扫（同行后续路径不再被吞）；run 按盘符锚切段逐条识别；段内取末个扩展名锚
//   （多词文件名/版本号让位真扩展名）；无锚时"分隔符紧跟空白/行尾"判为带空格目录。— 小欧-2026-11-01
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
import { FileOutlined, FolderOutlined } from '@ant-design/icons';
import { useNavigate, useInRouterContext } from 'react-router-dom';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';
import { encodePathParam, resolveChipUrl } from '@/utils/fileDeepLink';
import {
  isDriveAbsPath,
  isDirPath,
  isExternalAbsPath,
  isLinkableRelPath,
  toRelativePath,
} from '@/utils/projectPath';
import { useProjectRoot } from '@/hooks/useProjectRoot';
// 2026-10-28 小欧 - chip 内「别针」引用按钮（quote.ts 唯一实现的共用 UI 单点）— 小欧-2026-10-28
import { QuoteButton } from '@/features/refs/QuoteButton';

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
};

/** 徽标样式（目录/根外共用一个规格，避免两处漂移） */
const badgeStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
};

/** 形态：不可删除（Agent 的输出，不是用户的引用）；校验不过由调用方退化为纯文本，不渲染 chip */
const ChipBody: React.FC<FileRefChipProps & { onGo: () => void }> = ({
  relPath,
  lineRange,
  onGo,
}) => {
  // 2026-10-23 小欧 - 文案恒为原文（不补项目根）：正文写什么就显示什么 — 小欧-2026-10-23
  const projectRoot = useProjectRoot();
  const isDir = isDirPath(relPath);
  const isExternal = isExternalAbsPath(relPath, projectRoot);
  // 2026-10-23 小欧 - 可点判据：文件恒可点；根内相对目录可点；盘符绝对目录（根内/根外）
  //   根已取回即可点（根外目录走 ext=1 挂外部树），仅根未取回时归属未定 → 不可点。
  const navigable = !isDir || !isDriveAbsPath(relPath) || !!projectRoot;
  const label = isDir
    ? navigable
      ? `打开目录 ${relPath}`
      : `根外目录 ${relPath}，项目根尚未加载`
    : `${isExternal ? '根外文件 ' : ''}打开文件 ${relPath}${
        lineRange ? ` 第 ${lineRange.start} 至 ${lineRange.end} 行` : ''
      }`;
  return (
    // 2026-10-28 小欧 - 双层结构：外层 span 只承担 chip 视觉；链接语义（role=link +
    //   tabIndex + onGo）收在内层内容 span，别针 button 平铺兄弟位 —— role=link 内不放
    //   button（内嵌可交互元素会键盘/读屏双语义冲突，FileTrailPanel L244 教训）。
    //   别针只对文件 chip 出现（目录不引用，与足迹 preview==='text' 口径一致）。— 小欧-2026-10-28
    <span
      role={navigable ? 'link' : undefined}
      tabIndex={navigable ? 0 : undefined}
      aria-label={label}
      aria-disabled={navigable ? undefined : true}
      title={navigable ? undefined : '项目根尚未加载，暂时无法打开'}
      style={{
        ...chipStyle,
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.XS,
        cursor: navigable ? 'pointer' : 'default',
      }}
      onClick={navigable ? onGo : undefined}
      onKeyDown={
        navigable
          ? (e) => {
              if (e.key !== 'Enter' && e.key !== ' ') return;
              e.preventDefault();
              onGo();
            }
          : undefined
      }
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: Spacing.XS,
          pointerEvents: 'none',
        }}
      >
        {isDir ? (
          <FolderOutlined style={{ color: Colors.PRIMARY, flexShrink: 0 }} />
        ) : (
          <FileOutlined style={{ color: Colors.PRIMARY, flexShrink: 0 }} />
        )}
        {isDir && (
          <span style={{ ...badgeStyle, color: Colors.TEXT.SECONDARY }}>
            目录
          </span>
        )}
        {/* 2026-10-23 小欧 - 根外标识：提示该路径在当前项目根之外 — 小欧-2026-10-23 */}
        {isExternal && (
          <span style={{ ...badgeStyle, color: Colors.WARNING }}>根外</span>
        )}
        {relPath}
        {!isDir && lineRange ? `#L${lineRange.start}-L${lineRange.end}` : ''}
      </span>
      {!isDir && navigable && (
        <span style={{ pointerEvents: 'auto' }}>
          <QuoteButton path={relPath} lineRange={lineRange ?? null} />
        </span>
      )}
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
  // 2026-10-28 小欧 - URL 不在渲染时固定(项目根切换后 useProjectRoot 快照时序窗口内持旧根
  //   → 误判外部 → ext=1 URL)。改为 onClick 时 resolveChipUrl 实时取最新根(getCurrentProjectRoot)算。
  //   ChipBody 仍用 useProjectRoot 算 navigable/根外徽标(显示用, 点击不依赖)。— 小欧-2026-10-28
  if (inRouter) {
    return <ChipWithRouter {...props} />;
  }
  return (
    <ChipBody
      {...props}
      onGo={() => {
        window.location.assign(resolveChipUrl(props.relPath, props.lineRange));
      }}
    />
  );
};

/** Router 内的形态（单独一层组件，保证 useNavigate 只在有 Router 时被调用） */
const ChipWithRouter: React.FC<FileRefChipProps> = ({ relPath, lineRange }) => {
  const nav = useNavigate();
  return (
    <ChipBody
      relPath={relPath}
      lineRange={lineRange}
      onGo={() => {
        nav(resolveChipUrl(relPath, lineRange), { state: { internal: true } });
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
 * 盘符绝对目录：尾分隔符收尾（`F:\a\b\`）。
 * 负向前瞻保证不把 `F:\a\b\c.md` 的前缀当目录（否则文件被截成目录 + 残余文件名）。
 * 相对目录不自动识别（正文里的“答复/思考”不是路径）。
 */
const PATH_SEG = `[^${PATH_STOP}:\\\\/]+`;
const PATH_ABS_DIR = `[A-Za-z]:[\\\\/](?:${PATH_SEG}[\\\\/])+(?![^${PATH_STOP}:\\\\/])`;

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
    `|(?<lead>^|[\\s“”‘’《》（(【，,;；:：=*])(?:(?<bareDirAbs>${PATH_ABS_DIR})|(?<bareAbs>${PATH_ABS})|(?<bareRel>${PATH_REL})|(?<spacedAbs>${PATH_ABS_SP}))`,
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
  /** 2026-11-01 小欧 - 空格容差 run（盘符绝对专用），截断由 convertRuns policy 裁决 */
  spacedAbs?: string;
}

/** label 里的方括号与反斜杠要转义，否则 markdown 链接解析被截断 */
const escapeLabel = (p: string): string => p.replace(/([[\]\\])/g, '\\$1');

/** 形态/安全门槛：控制字符与 `..` 穿越不是可链接路径（绝对路径同样适用） */
const isBadPath = (p: string): boolean =>
  !p || /[\r\n\t\0]/.test(p) || p.split(/[\\/]/).includes('..');

// 2026-11-01 小欧 - run 裁决 policy（SRP：正则只圈界碑，切哪一条交这里）— 小欧-2026-11-01
/** run 内按盘符锚切段：`F:\a b\x.md F:\c.md` 两条路径各自成段，后一条不被前一条吞掉 */
const absSegments = (run: string): string[] =>
  run.split(/(?=[A-Za-z]:[\\/])/).filter(Boolean);

/**
 * 段内裁决 → {path, rest}：
 *   有扩展名锚 → 取**末个**锚截断为文件（多词文件名 `AI Agent架构…探索.md` 与版本号
 *     `v2.0 plan.md` 的 `.0` 都让位给真扩展名）；
 *   无锚 → 「分隔符紧跟空白/行尾」截断为带空格目录（`F:\my docs\proj\ 下有很多文件`）；
 *   两者皆无 → null（原文退回，不造假链接）。
 */
const resolveAbsCand = (seg: string): { path: string; rest: string } | null => {
  // ⚠ 局部正则带 g 只在本函数内跑完，lastIndex 不跨调用残留（不建模块级 g 正则）
  const ext = /\.[A-Za-z0-9]{1,10}(?![A-Za-z0-9./\\])/g;
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
  return null;
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
  lines = ''
): string | null => {
  if (isBadPath(raw)) return null;
  if (raw.startsWith('@') || raw.startsWith('#')) return null;
  const dir = isDirPath(raw);
  const abs = isDriveAbsPath(raw);
  if (dir) {
    // 绝对目录：根未取回时分不清内/外，等根（宁可晚一拍，也不给错归属）
    if (abs && !projectRoot) return null;
    // 相对目录：仅显式标记可点（正文里的“答复/思考”不是路径）
    if (!abs && !explicit) return null;
    if (!abs && !isValidRelPath(raw)) return null;
  } else if (!abs) {
    const rel = toRelativePath(raw, projectRoot);
    if (!rel) return null;
    // 2026-10-23 小欧 - 判“有没有目录”看原文（`./a.md` 显式带当前目录，不算裸文件名）— 小欧-2026-10-23
    if (!explicit && !/[\\/]/.test(raw)) return null;
    if (!isValidRelPath(rel) || !isLinkableRelPath(rel)) return null;
  }
  return `[${escapeLabel(raw)}](/file-ref?path=${encodePathParam(raw)}${lines})`;
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
      const lines =
        g.markFrom && !isDirPath(g.markPath)
          ? `&line=${g.markFrom}${g.markTo ? `-${g.markTo}` : ''}`
          : '';
      piece = toFileRefMarkdown(g.markPath, projectRoot, true, lines) ?? whole;
    } else if (g.spacedAbs) {
      // 2026-11-01 小欧 - ⑤ 空格容差：只吃首段裁决出的那一条，锚后残余（散文/后续路径）回扫不丢 — 小欧-2026-11-01
      const cand = resolveAbsCand(absSegments(g.spacedAbs)[0] ?? '');
      const link = cand ? toFileRefMarkdown(cand.path, projectRoot) : null;
      if (cand && link) {
        piece = `${lead}${link}`;
        consumed = lead.length + cand.path.length;
      }
    } else {
      const raw = g.bareDirAbs ?? g.bareAbs ?? g.bareRel;
      if (raw) {
        const link = toFileRefMarkdown(raw, projectRoot);
        if (link) piece = `${lead}${link}`;
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
 */
const LAST_SEGMENT_FILE_RE = /\.[A-Za-z][A-Za-z0-9]{0,9}$/;
const isPathLike = (raw: string): boolean => {
  if (!raw || /\s/.test(raw)) return false;
  // 2026-10-23 小欧 - 行内代码里的目录只认盘符绝对（相对目录不自动识别）— 小欧-2026-10-23
  if (isDirPath(raw)) return isDriveAbsPath(raw);
  return LAST_SEGMENT_FILE_RE.test(raw.split(/[\\/]/).pop() || '');
};

const INLINE_CODE_RE = /(`+)([^`]*?)\1/g;

/** 行内代码整段就是一个路径时才转链接；夹带其他文字一律原样，避免把示例改成可点链接 */
const toWholePathLink = (code: string, projectRoot?: string): string | null => {
  const raw = code.trim();
  if (isPathLike(raw)) return toFileRefMarkdown(raw, projectRoot);
  // 2026-11-01 小欧 - 带空格盘符路径（文件/目录同规则）：整段即路径才转，有残余 = 语义不唯一 → 原文 — 小欧-2026-11-01
  const cand =
    isDriveAbsPath(raw) && /\s/.test(raw)
      ? resolveAbsCand(absSegments(raw)[0] ?? '')
      : null;
  if (cand && !cand.rest) return toFileRefMarkdown(cand.path, projectRoot);
  return null;
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
 *     裸文件名、相对目录、非法形态原样。判据复用 utils/projectPath。— 小欧-2026-10-23
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
