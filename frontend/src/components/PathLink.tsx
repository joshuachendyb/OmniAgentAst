// 编辑历史: 2026-11-02 小欧 - 新建：合并 FileRefChip（chip 形态）/ FilePathLink（行内形态）/
//   pipeline/PathLink（工具参数形态）三套链接 UI 为唯一组件。三者原本各自实现 <a>、图标、tooltip、
//   键盘可达、点击现取根、别针，任一处改动漏另两处即口径漂移 — 小欧-2026-11-02
// 2026-11-02 小欧 - 改名 PathLinkView → PathLink：本组件含导航副作用与降级决策，
//   不是纯展示，View 后缀名不副实 — 小欧-2026-11-02
// 2026-11-02 小欧 - 外壳契约收敛：LinkBodyProps 只声明渲染所需字段（不再 extends PathLinkProps，
//   免收 projectRoot/dirHint/strictShape）；label 由 PathLink 算一次下传；onGo 不再传占位假回调；
//   文件/目录图标 style 单点；删 `const body = anchor` 透传 — 小欧-2026-11-02
// 2026-11-02 小欧 - 删 text 入参（唯一调用方传的就是 rawPath，等价于没有）：文案即 rawPath，
//   连带删 label 中间层，外壳与纯文本态直接用 rawPath — 小欧-2026-11-02
// 2026-11-02 小欧 - 增 pin 开关：正文 chip 恢复旧 FileRefChip 的「别针」引用入口（合并时丢失），
//   可见性用同一次 resolvePathTarget 结果判定（已链接且非目录），调用方不自判 — 小欧-2026-11-02
// 2026-11-02 小欧 - 恢复无 Router 兜底（设置页安全Tab 独立渲染场景，旧 FileRefChip 行为）：
//   已链接时保持链接形态，点击走 resolveChipUrlFresh 现取根，判不过不跳 — 小欧-2026-11-02
/**
 * PathLink —— 路径 → 文件页链接的**唯一** UI 组件。
 *
 * 判定与 URL 一律来自 utils/projectPath.resolvePathTarget（渲染态）与
 * hooks/useProjectRoot.resolveChipUrlFresh（点击态，现取根）。本组件不做任何路径判定。
 *
 * 两种外观：
 *  - `chip`：正文/卡片形态（背景框 + 目录/根外徽标 + 行号后缀），Agent 输出的文件引用；
 *  - `inline`：行内下划线形态（工具参数、产出物清单）。
 */
import React from 'react';
import { FileOutlined, FolderOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { resolvePathTarget } from '@/utils/projectPath';
import { resolveChipUrlFresh, useProjectRoot } from '@/hooks/useProjectRoot';
// 2026-11-02 小欧 - 别针引用入口（pin）：引用实现仍在 features/refs（quote.ts 唯一实现），
//   此处只并列渲染，与旧 components/markdown/FileRefChip 的依赖方向一致 — 小欧-2026-11-02
import { QuoteButton } from '@/features/refs/QuoteButton';
import { chatTokens } from '@/theme/tokens';
import { Colors, FontFamily, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

export interface PathLinkProps {
  /** 原始路径（绝对或相对项目根，原样展示） */
  rawPath: string;
  /** 行区间（可选；目录不带行号） */
  lineRange?: { start: number; end: number } | null;
  /** 工具语义声明该路径必为目录（listdir/tree/find 的 path） */
  dirHint?: boolean;
  /** 严格形态口径：根外无扩展名无尾分隔符的路径不猜目录、不出链接（工具参数用） */
  strictShape?: boolean;
  /** 外观：chip = 卡片（默认），inline = 行内下划线 */
  variant?: 'chip' | 'inline';
  /** 悬停提示：链接态显示完整路径，不可链接态显示原因 */
  tooltip?: boolean;
  /** 行内形态用等宽字体 + 省略号（产出物清单） */
  mono?: boolean;
  /**
   * 并列渲染「别针」引用按钮（仅正文 chip 用）：已链接且非目录时出现在链接右侧。
   * 2026-11-02 小欧 - 恢复旧 FileRefChip 的引用入口（合并成 PathLink 时丢了）：
   *   可见性由同一次 resolvePathTarget 结果决定，调用方不自判目录/可链接 — 小欧-2026-11-02
   */
  pin?: boolean;
  /** 可选：调用方已持有项目根时传入；缺省走 useProjectRoot 订阅 */
  projectRoot?: string;
}

/** chip 外观（背景框） */
const chipStyle: React.CSSProperties = {
  background: chatTokens.colorPrimaryBg,
  color: Colors.TEXT.STRONG,
  border: `1px solid ${Colors.BORDER.LIGHT}`,
  borderRadius: chatTokens.radius,
  padding: `0 ${Spacing.SM}px`,
  textDecoration: 'none',
};

/** 行内外观（下划线暗示可点） */
const inlineStyle: React.CSSProperties = {
  color: Colors.PRIMARY,
  textDecoration: 'underline',
  textUnderlineOffset: 2,
  overflowWrap: 'anywhere',
};

/** 等宽 + 省略号（产出物清单原有外观，保持不破） */
const monoStyle: React.CSSProperties = {
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.SECONDARY,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

/** 徽标（目录/根外共用一个规格） */
const badgeStyle: React.CSSProperties = {
  fontSize: FontSize.CAPTION,
  fontWeight: FontWeight.BOLD,
};

/** 链接外壳的输入：只含渲染所需，不含判定参数（判定在 PathLink 内做一次） */
interface LinkBodyProps {
  rawPath: string;
  /** 行区间（chip 形态显示 #L 后缀；目录不显示） */
  lineRange?: { start: number; end: number } | null;
  variant: 'chip' | 'inline';
  tooltip: boolean;
  mono: boolean;
  /** 渲染态算好的 URL（中键/复制链接用） */
  url: string;
  isDir: boolean;
  isExternal: boolean;
}

/** 唯一链接外壳：<a> + 图标 + 徽标（两种外观共用） */
const LinkBody: React.FC<LinkBodyProps & { onGo: () => void }> = ({
  rawPath,
  lineRange,
  variant,
  tooltip,
  mono,
  url,
  isDir,
  isExternal,
  onGo,
}) => {
  const isChip = variant === 'chip';
  const ariaLabel = isDir
    ? `打开目录 ${rawPath}`
    : `${isExternal ? '根外文件 ' : ''}打开文件 ${rawPath}${
        lineRange ? ` 第 ${lineRange.start} 至 ${lineRange.end} 行` : ''
      }`;
  // 2026-11-02 小欧 - 图标规格单点：原文件/目录两分支各写一遍同一份 style — 小欧-2026-11-02
  const iconStyle: React.CSSProperties = {
    color: Colors.PRIMARY,
    flexShrink: 0,
    fontSize: isChip ? undefined : 12,
  };

  const anchor = (
    <a
      href={url}
      aria-label={ariaLabel}
      style={{
        display: 'inline-flex',
        alignItems: isChip ? 'center' : 'baseline',
        gap: Spacing.XS,
        cursor: 'pointer',
        minWidth: mono ? 0 : undefined,
        ...(isChip ? chipStyle : inlineStyle),
        ...(mono ? monoStyle : null),
      }}
      onClick={(e) => {
        // 保留 Ctrl/Cmd/Shift 的浏览器原生新标签行为
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
          return;
        e.preventDefault();
        onGo();
      }}
      onKeyDown={(e) => {
        // <a> 原生 Enter 用的是渲染期 href（可能是旧根算出的），故两种键都走现取根
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        onGo();
      }}
    >
      {isDir ? (
        <FolderOutlined aria-hidden style={iconStyle} />
      ) : (
        <FileOutlined aria-hidden style={iconStyle} />
      )}
      {isChip && isDir && (
        <span style={{ ...badgeStyle, color: Colors.TEXT.SECONDARY }}>
          目录
        </span>
      )}
      {isChip && isExternal && (
        <span style={{ ...badgeStyle, color: Colors.WARNING }}>根外</span>
      )}
      {rawPath}
      {isChip && !isDir && lineRange
        ? `#L${lineRange.start}-L${lineRange.end}`
        : ''}
    </a>
  );

  return tooltip ? <Tooltip title={rawPath}>{anchor}</Tooltip> : anchor;
};

/** 点击参数（只有路由层需要，外壳不关心） */
interface RoutedLinkProps extends LinkBodyProps {
  dirHint?: boolean;
  strictShape?: boolean;
}

/**
 * 唯一点击口径：点击时显取根解析 → 判不过不跳；落点由调用方决定（Router 内 SPA 跳 /
 * Router 外整页跳），共用同一个「现取根 + if (u)」判定，不造两套。 — 小欧-2026-11-02
 */
const goFresh = (
  rawPath: string,
  lineRange: { start: number; end: number } | null | undefined,
  opts: { dirHint?: boolean; strictShape?: boolean },
  sink: (url: string) => void
): void => {
  void resolveChipUrlFresh(rawPath, lineRange, opts).then((u) => {
    if (u) sink(u);
  });
};

/** Router 内的点击形态（单独一层，保证 useNavigate 只在有 Router 时被调用） */
const RoutedLink: React.FC<RoutedLinkProps> = ({
  rawPath,
  lineRange,
  dirHint,
  strictShape,
  ...body
}) => {
  const nav = useNavigate();
  return (
    <LinkBody
      {...body}
      rawPath={rawPath}
      lineRange={lineRange}
      onGo={() =>
        goFresh(rawPath, lineRange, { dirHint, strictShape }, (u) =>
          nav(u, { state: { internal: true } })
        )
      }
    />
  );
};

export const PathLink: React.FC<PathLinkProps> = ({
  rawPath,
  lineRange = null,
  dirHint,
  strictShape,
  variant = 'chip',
  tooltip = false,
  mono = false,
  pin = false,
  projectRoot,
}) => {
  // 2026-11-02 小欧 - 调用方已传根就不再订阅取根（参数面板一屏几十个路径，原实现逐个订阅）— 小欧-2026-11-02
  const subscribedRoot = useProjectRoot(!projectRoot);
  const inRouter = useInRouterContext();
  // 传空串等同未传：与上面 enabled 判定同一口径，避免「订阅了却不用」
  const root = projectRoot || subscribedRoot;
  const target = resolvePathTarget(rawPath, root, {
    dirHint,
    strictShape,
    lineRange,
  });

  // 2026-11-02 小欧 - 判定不过的唯一出口是纯文本；已链接则无 Router 时也要出链接
  //   （旧 FileRefChip 的兜底：设置页安全Tab 独立渲染等场景，点击整页跳）— 小欧-2026-11-02
  if (!target.linked) {
    const plain = (
      <span
        data-path-state="unlinked"
        style={mono ? monoStyle : { color: Colors.TEXT.PRIMARY }}
      >
        {rawPath}
      </span>
    );
    const reason = target.reason ?? '无法在文件页打开';
    return tooltip ? <Tooltip title={reason}>{plain}</Tooltip> : plain;
  }

  const linkProps = {
    rawPath,
    lineRange,
    variant,
    tooltip,
    mono,
    url: target.url,
    isDir: target.isDir,
    isExternal: target.isExternal,
  };
  const link = inRouter ? (
    <RoutedLink {...linkProps} dirHint={dirHint} strictShape={strictShape} />
  ) : (
    // 无 Router 兜底：同一 LinkBody，落点整页跳（sink 决定，不新开标签页）
    <LinkBody
      {...linkProps}
      onGo={() =>
        goFresh(rawPath, lineRange, { dirHint, strictShape }, (u) =>
          window.location.assign(u)
        )
      }
    />
  );
  // 别针只对文件（引用只对文本文件）；目录/未链接不出 — 小欧-2026-11-02
  if (!pin || target.isDir) return link;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.XS,
        minWidth: 0,
      }}
    >
      {link}
      <QuoteButton path={rawPath} lineRange={lineRange} />
    </span>
  );
};
