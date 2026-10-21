// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.13 新建：chip + 预处理 + 形态校验三件同文件 — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28] v5.9：J5 生成链接的 label 去 📄 emoji（chip 自带图标，防双重图标） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28] v5.12：深链改走 buildFileDeepLink（O7 唯一拼装点） — 小杨-2026-10-21
/**
 * FileRefChip —— Agent 输出的文件引用卡片（J5）
 *
 * 三件事同文件（DRY）：
 * 1. chip 渲染（不可删除：它是 Agent 的输出，不是用户的引用）
 * 2. `preprocessFileRefs`：把 `[[文件:path#L1-L2]]` 转成标准 markdown 链接（**围栏代码块内不转**）
 * 3. `isValidRelPath`：前端**形态**校验唯一一份（绝对路径/UNC/`..` 一律不合格）
 *
 * ⚠ 权威判定在后端：前端只做形态校验，路径是否真在项目根内由后端 `/files/read` 判界，
 *   校验不过的链接**退化为纯文本**，不造假链接。
 */
import React from 'react';
import { Tooltip } from 'antd';
import { FileOutlined } from '@ant-design/icons';
import { useNavigate, useInRouterContext } from 'react-router-dom';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';
import { buildFileDeepLink } from '@/utils/fileDeepLink';

export interface FileRefChipProps {
  relPath: string;
  lineRange?: { start: number; end: number };
  label: string;
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
  label,
  onGo,
}) => (
  <Tooltip title={relPath}>
    {/* 7.0.3 chip 基线：colorPrimaryBg 底 + BORDER.LIGHT 边 + Radius 6 + SM 内边距 + STRONG 字 */}
    <span style={chipStyle} onClick={onGo}>
      <FileOutlined style={{ color: Colors.PRIMARY, flexShrink: 0 }} /> {label}
      {lineRange ? `#L${lineRange.start}-L${lineRange.end}` : ''}
    </span>
  </Tooltip>
);

/**
 * FileRefChip —— Agent 输出的文件引用卡片（J5）
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
  label,
  url,
}) => {
  const nav = useNavigate();
  return (
    <ChipBody
      relPath={relPath}
      lineRange={lineRange}
      label={label}
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

/** J5 路径可点击的同一份形态校验（别名，避免两处各写一遍） */
export const isViewablePath = isValidRelPath;

const convertRuns = (text: string): string =>
  text.replace(
    /\[\[文件:([^\]#|]+)(?:#L(\d+)(?:-L?(\d+))?)?\]\]/g,
    (_m, p, a, b) => {
      if (!isValidRelPath(p)) return _m; // 非法即留原文，不造假链接
      const lines = a ? `&line=${a}${b ? `-${b}` : ''}` : '';
      // label 不带图标 emoji —— chip 自带 FileOutlined（防双重图标）
      return `[${p}](/file-ref?path=${encodeURIComponent(p)}${lines})`;
    }
  );

/**
 * 预处理：只转围栏外的标记，块内标记原样保留（代码块内不生效）
 *
 * 2026-10-21 小杨 - 文档[28] v5.15 修正（先红后绿抓出的真缺陷）：
 *   设计稿原用 `text.split(/(^```[\s\S]*?(?:^```|$))/m)` 想"按围栏切段"，
 *   但 **multiline 下的 `$` 匹配的是"任意行尾"**，于是 `[\s\S]*?` 会在第一行行尾
 *   （`$`）就收尾 → 围栏段只切出 "```" 一行，其后的标记仍落在"非围栏段"里被转换
 *   → **围栏内的 [[文件:]] 照样被转**（4.6 B7 的硬要求"代码块内不生效"失效）。
 *   改为**行级状态机**：逐行判"是否围栏行"，围栏内整行跳过 —— 语义直白、无正则歧义。
 */
export const preprocessFileRefs = (text: string): string => {
  const lines = text.split('\n');
  let inFence = false;
  return lines
    .map((line) => {
      if (/^\s*```/.test(line)) {
        // 围栏行本身不动；一行内 ``` 出现奇数次 = 开关状态翻转一次
        const marks = (line.match(/```/g) || []).length;
        if (marks % 2 === 1) inFence = !inFence;
        return line;
      }
      return inFence ? line : convertRuns(line);
    })
    .join('\n');
};
