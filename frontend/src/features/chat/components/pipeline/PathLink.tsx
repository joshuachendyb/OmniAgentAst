// 编辑历史: 2026-10-21 小杨 - 新建：工具参数里的路径可点击直达文件页 — 小杨-2026-10-21
// 2026-10-21 小欧 - toRelativePath 迁至 utils/projectPath.ts（与新增的 toAbsolutePath 同源，
//   绝对⇄相对互逆运算只此一处）— 小欧-2026-10-21
// 2026-10-21 小杨 - 支持相对路径；补图标/键盘/根外原因提示；<a> 原生 href 保底 — 小杨-2026-10-21
// 2026-10-22 小杨 - 改原生 <a> + 文件图标 + 键盘可达（Enter/Space）；不可链接时用 Tooltip 说明原因
//   （不用 title 属性，避免参数树出现"截断兜底"节点）— 小杨-2026-10-22
// 2026-10-23 小欧 - 根外盘符绝对路径（文件）也生成 ext=1 外部只读预览深链（与正文 chip 同口径），
//   不再拦死为纯文本；根内绝对仍归一走普通深链；根未取回时盘符绝对路径归属未定 → 不出链接
//   （等根取回后重算，与正文 chip 同口径）。— 小欧-2026-10-23
// 2026-10-23 小欧 - 根外目录（尾分隔符）也生成 ext=1 深链（挂外部树 __ext__），
//   external 条件放宽 isFileLikePath || isDirPath；LinkInner 目录态换 FolderOutlined 图标 — 小欧-2026-10-23
/**
 * PathLink —— 工具参数里的路径 → 可点击直达文件页（深链）
 *
 * 判定口径：**前端只做形态校验**，权威判定一律交给后端
 *   （路径是否真在项目根内由 `/files/read` 判界）—— 前端复制一份判据必然随规则演进而漂移。
 *
 * 相对路径：工具可能给 `src/main.py` / `doc\a.md`，归一后直接进深链；
 *   根内绝对路径归一成相对走普通深链；**根外盘符绝对路径（文件/目录）走 ext=1 外部深链**；
 *   仅非盘符绝对且形态非法（UNC/斜杠/穿越/无扩展名且无尾分隔符）才退纯文本。
 */
import React from 'react';
import { FileOutlined, FolderOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { isValidRelPath } from '@/components/markdown/FileRefChip';
import {
  isDirPath,
  isDriveAbsPath,
  isFileLikePath,
  isLinkableRelPath,
  toRelativePath,
} from '@/utils/projectPath';
import { buildExternalDeepLink, buildFileDeepLink } from '@/utils/fileDeepLink';
import { Colors, Spacing } from '@/utils/stepStyles';

export interface PathLinkProps {
  value: string;
  /** 项目根（来自 GET /files/root）；用于把绝对路径转成相对路径 */
  projectRoot?: string;
}

/** 可点击形态（Router 内）：原生 <a> 保底，点击/键盘都可达 */
const LinkInner: React.FC<{
  value: string;
  url: string;
  isDir?: boolean;
}> = ({ value, url, isDir }) => {
  const nav = useNavigate();
  return (
    <Tooltip title={value}>
      <a
        href={url}
        aria-label={`${isDir ? '打开目录' : '打开文件'} ${value}`}
        style={{
          display: 'inline-flex',
          alignItems: 'baseline',
          gap: Spacing.XS,
          color: Colors.PRIMARY,
          textDecoration: 'underline',
          textUnderlineOffset: 2,
          overflowWrap: 'anywhere',
          cursor: 'pointer',
        }}
        onClick={(e) => {
          // 保留 Ctrl/Cmd/Shift 的浏览器原生新标签行为
          if (
            e.button !== 0 ||
            e.metaKey ||
            e.ctrlKey ||
            e.shiftKey ||
            e.altKey
          )
            return;
          e.preventDefault();
          nav(url);
        }}
        onKeyDown={(e) => {
          // <a> 原生 Enter 已可跳转；补 Space，和系统内其他 role=link 一致
          if (e.key !== ' ') return;
          e.preventDefault();
          nav(url);
        }}
      >
        {isDir ? (
          <FolderOutlined aria-hidden style={{ flexShrink: 0, fontSize: 12 }} />
        ) : (
          <FileOutlined aria-hidden style={{ flexShrink: 0, fontSize: 12 }} />
        )}
        {value}
      </a>
    </Tooltip>
  );
};

/**
 * PathLink —— 可链接（根内归一 / 根外盘符绝对）进深链；
 * 仅非盘符绝对且形态非法（UNC/斜杠/穿越/无扩展名）时保留纯文本 + Tooltip 说明原因，
 * 不造假链接，也不让用户面对"点了没反应"。
 */
export const PathLink: React.FC<PathLinkProps> = ({ value, projectRoot }) => {
  const inRouter = useInRouterContext();
  const rel = toRelativePath(value, projectRoot);
  // 根外盘符绝对路径（文件有扩展名 / 目录尾分隔符）→ ext=1 外部深链（与正文 chip 同口径）；
  // 根未取回时盘符绝对路径归属未定 → 不出链接（等根取回后重算）；
  // 无尾分隔符且无扩展名的根外路径前端无法区分文件/目录 → 不出链接（不造假）。
  const external =
    !!projectRoot &&
    isDriveAbsPath(value) &&
    !rel &&
    (isFileLikePath(value) || isDirPath(value));
  const dir = external && isDirPath(value);
  if (external && inRouter) {
    return (
      <LinkInner value={value} url={buildExternalDeepLink(value)} isDir={dir} />
    );
  }
  if (rel && isValidRelPath(rel) && isLinkableRelPath(rel) && inRouter) {
    return <LinkInner value={value} url={buildFileDeepLink(rel)} />;
  }

  let reason = '路径形态不合法，无法在文件页打开';
  if (!inRouter) {
    reason = '当前页面不支持应用内跳转';
  } else if (rel && !isLinkableRelPath(rel)) {
    reason = '不是可识别的文件路径（无分隔符与扩展名），未做链接';
  } else if (isDriveAbsPath(value)) {
    reason = projectRoot
      ? '路径不在项目根内，无法在文件页打开'
      : '项目根尚未加载，暂时无法打开';
  }
  // 用 Tooltip 讲原因而不用 title 属性：树视图铁律「不靠 title 兜底」，
  //   title 会让整棵树出现 [title] 节点、破坏「全文直显」契约。
  return (
    <Tooltip title={reason}>
      <span data-path-state="unlinked">{value}</span>
    </Tooltip>
  );
};
