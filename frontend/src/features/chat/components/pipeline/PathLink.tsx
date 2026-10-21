// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.12 新建：工具参数里的路径可点击直达文件页（J1） — 小杨-2026-10-21
/**
 * PathLink —— 工具参数里的路径 → 可点击直达文件页（J1 深链）
 *
 * 判定口径（4.2.8 定案）：**前端只做形态校验**，权威判定一律交给后端
 *   （路径是否真在项目根内由 `/files/read` 判界）—— 前端复制一份判据必然随规则演进而漂移。
 *
 * 相对路径怎么来：工具参数里的 path 绝大多数是**绝对路径**（LLM 原样给的），
 *   而文件页深链用的是**相对项目根**的路径。故这里做一次前缀剥离：
 *   `projectRoot` 前缀去掉 → 相对路径；剥不掉（不在项目根内）→ **退化为纯文本**（不做假链接）。
 */
import React from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { isValidRelPath } from '@/components/markdown/FileRefChip';
import { buildFileDeepLink } from '@/utils/fileDeepLink';
import { Colors } from '@/utils/stepStyles';

export interface PathLinkProps {
  value: string;
  /** 项目根（来自 GET /files/root）；用于把绝对路径转成相对路径 */
  projectRoot?: string;
}

/** 绝对路径 → 相对项目根；不在项目根内返回 null */
export const toRelativePath = (
  value: string,
  projectRoot?: string
): string | null => {
  if (!projectRoot) return null;
  const norm = (p: string) => p.replace(/[/\\]+/g, '/').replace(/\/+$/, '');
  const root = norm(projectRoot);
  const v = norm(value);
  if (!root || !v) return null;
  if (!v.toLowerCase().startsWith(root.toLowerCase())) return null;
  // 2026-10-21 小杨 - 审计修复：必须校验**分隔符边界**
  //   （否则 F:\proj2\a.md 会被当成 F:\proj 内的 "2/a.md" → 链接指向不存在的文件）
  if (v.length > root.length && v[root.length] !== '/') return null;
  const rel = v.slice(root.length).replace(/^\/+/, '');
  return rel || null;
};

/** 可点击形态（Router 内） */
const LinkInner: React.FC<PathLinkProps & { rel: string }> = ({
  value,
  rel,
}) => {
  const nav = useNavigate();
  return (
    <span
      role="link"
      tabIndex={0}
      title={value}
      style={{
        color: Colors.PRIMARY,
        textDecoration: 'underline',
        wordBreak: 'break-all',
        cursor: 'pointer',
      }}
      onClick={() => {
        nav(buildFileDeepLink(rel));
      }}
    >
      {value}
    </span>
  );
};

/**
 * PathLink —— 形态不合格（绝对路径外/UNC/穿越）或无 projectRoot 时**退化为纯文本**，不造假链接。
 */
export const PathLink: React.FC<PathLinkProps> = ({ value, projectRoot }) => {
  const inRouter = useInRouterContext();
  const rel = toRelativePath(value, projectRoot);
  if (!rel || !isValidRelPath(rel) || !inRouter) {
    return <span>{value}</span>;
  }
  return <LinkInner value={value} rel={rel} />;
};
