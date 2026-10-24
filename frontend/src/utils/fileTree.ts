// 编辑历史: 2026-10-22 小欧 - 新建：文件树工具函数（从 pages/Files 抽出）— 小欧-2026-10-22
//   mergeKids / buildScanNotices 上提共享层，供 useFilesTree 与页面共用。
// 2026-10-24 小欧 - 新增 prefixKeys（递归给树节点 key 加前缀）修复外部目录深层懒加载路径丢失；
//   新增 joinAbsPath（Windows 分隔符统一）修复路径混用 \ 和 / 问题 — 小欧-2026-10-24
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
 * 2026-10-24 小欧 - 递归给树节点 key 加统一前缀（不可变）。
 * 场景：后端懒加载返回的 key 是相对于「被请求子目录」的，
 *   需要拼上父路径前缀才能与整棵树中其他节点的 key 对齐（外部根相对路径）。
 *   也用于合成 __ext__ 根时给外部子树加 EXT_KEY 前缀。
 */
export const prefixKeys = (
  nodes: FileNode[],
  prefix: string
): FileNode[] =>
  nodes.map((n) => ({
    ...n,
    key: `${prefix}/${n.key}`,
    children: n.children ? prefixKeys(n.children, prefix) : undefined,
  }));

/**
 * 2026-10-24 小欧 - 拼绝对路径：base + rel，统一分隔符为 Windows 风格（\）。
 * 场景：externalBase 是 Windows 绝对路径（F:\x），后端返回的 key 是 posix 相对路径
 *   （backend/app/db/...），直接拼会混用 \ 和 /。此处统一转为 \ 再拼，
 *   保证显示一致且后端 Path() 两种分隔符都能处理。
 */
export const joinAbsPath = (base: string, rel: string): string => {
  const normBase = base.replace(/[\\/]$/, '');
  const normRel = rel.replace(/\//g, '\\');
  return `${normBase}\\${normRel}`;
};

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
  if (r.truncated) out.push('深层点开时会自动加载（当前显示不完整）。');
  if (r.incomplete_depth) out.push('深层点开时会自动加载.');
  if (r.skipped > 0) out.push(`${r.skipped} 条目读失败跳过.`);
  if (r.skipped_cycles > 0) out.push(`${r.skipped_cycles} 个符号链接）`);
  return out;
};
