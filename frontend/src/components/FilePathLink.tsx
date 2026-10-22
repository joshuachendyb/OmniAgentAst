// 编辑历史: 2026-10-22 小欧 - 新建：路径 → 文件页深链的可点链接（产出物/工作目录共用）— 小欧-2026-10-22
/**
 * FilePathLink —— 把"任意来源的路径"渲染成可点的文件页深链
 *
 * 与 FileRefChip 的关系：FileRefChip 是 Agent 输出的 chip 卡片（带背景框），
 *   本组件是行内文本链接（下划线）——外观不同但逻辑同（判界→深链→Router 分流），
 *   底层判界复用 utils/projectPath、深链复用 utils/fileDeepLink（单一真源，不另立第二套）。
 *
 * 判界不过（根外/未取到根/形态非法）一律退化为纯文本，不造假链接（与 FileRefChip 同口径）。
 */
import React from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { buildFileDeepLink } from '@/utils/fileDeepLink';
import { isLinkableRelPath, toRelativePath } from '@/utils/projectPath';
import { useProjectRoot } from '@/hooks/useProjectRoot';
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
const RouterLink: React.FC<{ url: string; title: string; text: string }> = ({
  url,
  title,
  text,
}) => {
  const nav = useNavigate();
  return (
    <span
      role="link"
      tabIndex={0}
      title={title}
      aria-label={`打开文件 ${title}`}
      style={{ ...plainStyle, ...linkStyle }}
      onClick={() => nav(url)}
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        nav(url);
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
  const linkable = !!rel && isLinkableRelPath(rel);
  const label = text ?? rawPath;

  if (!linkable || !rel) {
    // 判界不过（根外/形态非法/未取到根）→ 原样纯文本，不造假链接
    return (
      <span title={rawPath} style={plainStyle}>
        {label}
      </span>
    );
  }

  const url = buildFileDeepLink(rel, lineRange);
  if (!inRouter) {
    // 无 Router 上下文（单测/非路由容器）→ 退化为整页跳转（与 FileRefChip 同款）
    return (
      <a href={url} title={rawPath} style={{ ...plainStyle, ...linkStyle }}>
        {label}
      </a>
    );
  }
  return <RouterLink url={url} title={rawPath} text={label} />;
};
