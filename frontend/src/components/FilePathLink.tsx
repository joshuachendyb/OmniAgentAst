// 编辑历史: 2026-10-22 小欧 - 新建：路径 → 文件页深链的可点链接（产出物/工作目录共用）— 小欧-2026-10-22
// 2026-10-23 小欧 - 根外盘符绝对路径（文件）也生成 ext=1 外部只读预览深链（与正文 chip 同口径），
//   不再静默退化纯文本；根内绝对仍归一走普通深链；根未取回时盘符绝对路径归属未定 → 不出链接。— 小欧-2026-10-23
// 2026-10-23 小欧 - 根外目录（尾分隔符）也生成 ext=1 深链（挂外部树 __ext__），
//   external 条件放宽 isFileLikePath || isDirPath；目录态 aria-label 改「打开目录」— 小欧-2026-10-23
// 2026-10-28 小欧 - 点击用最新根：RouterLink 增 resolveUrl 回调（点击/键盘时调
//   resolveChipUrl 实时取 getCurrentProjectRoot() 最新根重算 ext=1 vs 普通），渲染 href
//   保留供中键新标签/复制链接（旧根 href 由 Files 页 ext=1 降级兜底）；行号截断由
//   resolveChipUrl 内部 isDirPath 统一判，调用处不再重复 `dir ? null`（消冗余）。— 小欧-2026-10-28
// 2026-10-28 小欧 - 链接旁增「别针」引用入口（与文件足迹同款，北京老陈令）：withPin 承载壳
//   把链接 + QuoteButton 包为 inline-flex 兄弟位（四个链接返回形态共用一份，minWidth:0
//   承接原链接 span 的 flex 压缩、保内层 ellipsis 不破坏）；外部目录不包（目录不引用）；
//   判界不过的纯文本分支不出别针。别针调 features/refs/QuoteButton（quote.ts 唯一实现）。— 小欧-2026-10-28
/**
 * FilePathLink —— 把"任意来源的路径"渲染成可点的文件页深链
 *
 * 与 FileRefChip 的关系：FileRefChip 是 Agent 输出的 chip 卡片（带背景框），
 *   本组件是行内文本链接（下划线）——外观不同但逻辑同（判界→深链→Router 分流），
 *   底层判界复用 utils/projectPath、深链复用 utils/fileDeepLink（单一真源，不另立第二套）。
 *
 * 判界不过（根外/未取到根/形态非法）一律退化为纯文本，不造假链接（与 FileRefChip 同口径）。
 * 根外目录（尾分隔符）走 ext=1 挂外部树；根外文件走 ext=1 外部只读预览。
 */
import React from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import {
  buildExternalDeepLink,
  buildFileDeepLink,
  resolveChipUrl,
} from '@/utils/fileDeepLink';
import {
  isDirPath,
  isDriveAbsPath,
  isFileLikePath,
  isLinkableRelPath,
  toRelativePath,
} from '@/utils/projectPath';
import { useProjectRoot } from '@/hooks/useProjectRoot';
// 2026-10-28 小欧 - 链接旁「别针」引用按钮（quote.ts 唯一实现的共用 UI 单点）— 小欧-2026-10-28
import { QuoteButton } from '@/features/refs/QuoteButton';
import { Colors, FontFamily, FontSize } from '@/utils/stepStyles';

export interface FilePathLinkProps {
  /** 原始路径（绝对或相对项目根，工具自声明原样） */
  rawPath: string;
  /** 行区间（可选） */
  lineRange?: { start: number; end: number } | null;
  /** 展示文案（缺省=原始路径） */
  text?: string;
}

/** 链接态样式（可点 = 主色 + 下划线暗示） */
const linkStyle: React.CSSProperties = {
  color: Colors.PRIMARY,
  cursor: 'pointer',
  textDecoration: 'underline',
  textUnderlineOffset: 2,
};

/** 纯文本态样式（判界不过 = 原样展示，不给假链接；保持产出物列表原有 ellipsis 外观） */
const plainStyle: React.CSSProperties = {
  color: Colors.TEXT.PRIMARY,
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.SECONDARY,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

/** Router 内的形态（单独一层，保证 useNavigate 只在有 Router 时被调用） */
const RouterLink: React.FC<{
  url: string;
  title: string;
  text: string;
  isDir?: boolean;
  /** 点击时用最新根重新计算 URL（项目根切换后时序窗口兜底） */
  resolveUrl?: () => string;
}> = ({ url, title, text, isDir, resolveUrl }) => {
  const nav = useNavigate();
  const go = () => nav(resolveUrl ? resolveUrl() : url);
  return (
    <span
      role="link"
      tabIndex={0}
      title={title}
      aria-label={`${isDir ? '打开目录' : '打开文件'} ${title}`}
      style={{ ...plainStyle, ...linkStyle }}
      onClick={go}
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        go();
      }}
    >
      {text}
    </span>
  );
};

export const FilePathLink: React.FC<FilePathLinkProps> = ({
  rawPath,
  lineRange = null,
  text,
}) => {
  const inRouter = useInRouterContext();
  const projectRoot = useProjectRoot();
  const rel = toRelativePath(rawPath, projectRoot);
  // 根外盘符绝对路径（文件有扩展名 / 目录尾分隔符）→ ext=1 外部深链（与正文 chip 同口径）；
  // 根未取回时盘符绝对路径归属未定 → 不出链接（等根取回后重算）；
  // 无尾分隔符且无扩展名的根外路径前端无法区分文件/目录 → 不出链接（不造假）。
  const external =
    !!projectRoot &&
    isDriveAbsPath(rawPath) &&
    !rel &&
    (isFileLikePath(rawPath) || isDirPath(rawPath));
  const dir = external && isDirPath(rawPath);
  const linkable = !!rel && isLinkableRelPath(rel);
  const label = text ?? rawPath;

  /**
   * 2026-10-28 小欧 - 链接 + 别针 的承载壳：四个链接返回形态共用一份（DRY，不在四处
   *   各包一次 JSX）。minWidth:0 由壳承接原链接 span 的 flex 压缩职责（内层 overflow
   *   hidden 的 flex 项最小尺寸归零），ellipsis 行为不变。— 小欧-2026-10-28
   */
  const withPin = (linkEl: React.ReactNode): React.ReactNode => (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        minWidth: 0,
      }}
    >
      {linkEl}
      <QuoteButton path={rawPath} lineRange={lineRange} />
    </span>
  );

  if (external) {
    const url = buildExternalDeepLink(rawPath, dir ? null : lineRange);
    if (!inRouter) {
      // 无 Router 上下文 → 退化为整页跳转（与 FileRefChip 同款）
      const link = (
        <a
          href={url}
          title={rawPath}
          style={{ ...plainStyle, ...linkStyle }}
          onClick={(e) => {
            if (
              e.button !== 0 ||
              e.metaKey ||
              e.ctrlKey ||
              e.shiftKey ||
              e.altKey
            )
              return;
            e.preventDefault();
            window.location.assign(resolveChipUrl(rawPath, lineRange));
          }}
        >
          {label}
        </a>
      );
      return dir ? link : withPin(link);
    }
    const link = (
      <RouterLink
        url={url}
        title={rawPath}
        text={label}
        isDir={dir}
        resolveUrl={() => resolveChipUrl(rawPath, lineRange)}
      />
    );
    return dir ? link : withPin(link);
  }

  if (!linkable || !rel) {
    // 判界不过（根内归一失败/形态非法/未取到根）→ 原样纯文本，不造假链接（不出别针）
    return (
      <span title={rawPath} style={plainStyle}>
        {label}
      </span>
    );
  }

  const url = buildFileDeepLink(rel, lineRange);
  if (!inRouter) {
    // 无 Router 上下文（单测/非路由容器）→ 退化为整页跳转（与 FileRefChip 同款）
    const link = (
      <a
        href={url}
        title={rawPath}
        style={{ ...plainStyle, ...linkStyle }}
        onClick={(e) => {
          if (
            e.button !== 0 ||
            e.metaKey ||
            e.ctrlKey ||
            e.shiftKey ||
            e.altKey
          )
            return;
          e.preventDefault();
          window.location.assign(resolveChipUrl(rawPath, lineRange));
        }}
      >
        {label}
      </a>
    );
    return withPin(link);
  }
  return withPin(
    <RouterLink
      url={url}
      title={rawPath}
      text={label}
      resolveUrl={() => resolveChipUrl(rawPath, lineRange)}
    />
  );
};
