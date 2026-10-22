// 编辑历史: 2026-10-22 小欧 - 新建：文件树工具函数（从 pages/Files 抽出）— 小欧-2026-10-22
//   文档[43] R7：mergeKids / buildScanNotices 上提共享层，供 useFilesTree 与页面共用。
import type { FileNode } from '@/services/api/file.api';

/** 树归并：按 key（相对路径）把补拉的子节点挂到父下（不可变更新，只改一路祖先） */
export const mergeKids = (
  nodes: FileNode[],
  parentKey: string,
  kids: FileNode[]
): FileNode[] =>
  nodes.map((n) => {
    if (n.key === parentKey)
      return { ...n, children: kids, incomplete_child: false };
    if (n.children)
      return { ...n, children: mergeKids(n.children, parentKey, kids) };
    return n;
  });

/**
 * 扫描不完整提示（truncated / incomplete_depth / skipped / skipped_cycles 四源）：
 *   后端一直在算这几个标志，但前端原先只取 r.nodes 全丢 → 用户以为看到的是完整目录
 *   （大仓下目录被截断而用户毫不知情）。此处如实告知，几段拼成一行显示（过长自动折行）。
 */
export const buildScanNotices = (r: {
  truncated: boolean;
  incomplete_depth: boolean;
  skipped: number;
  skipped_cycles: number;
}): string[] => {
  const out: string[] = [];
  if (r.truncated) out.push('未显示目录在「定位路径」输入路径直达）.');
  if (r.incomplete_depth) out.push('深层点开时会自动加载.');
  if (r.skipped > 0) out.push(`${r.skipped} 条目读失败跳过.`);
  if (r.skipped_cycles > 0) out.push(`${r.skipped_cycles} 个符号链接）`);
  return out;
};
