// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.9 + 9.9.1 新建：目录树（全量加载 / 降级补拉 / 右键菜单 / 焦点环） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§7.0.5(v5.12)：图标映射改用全局单一真源 @/components/fileIcon — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§9.9.1(O9)：Tree 增 focusable（键盘可达）；复制失败兜底走公用 copyTextToClipboard — 小杨-2026-10-21
/**
 * FilesTree —— 项目根目录树（只读浏览）
 *
 * 能力：全量优先（首屏一次 tree 拉满 5 层）+ 降级补拉（incomplete_child 的目录展开时按需补拉，
 *   loadedKeys 记账不重复请求）+ 右键菜单（设为会话工作目录 / 插入引用 / 复制路径）+ 键盘可达（O9）。
 */
import React, { useMemo, useState } from 'react';
import { Dropdown, Empty, Tree, Tooltip } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { FolderOutlined, PaperClipOutlined } from '@ant-design/icons';
import type { FileNode } from '@/services/api/file.api';
import { fileIcon } from '@/components/fileIcon';
import { copyTextToClipboard } from '@/utils/clipboard';
import { formatBytes } from '@/utils/format';
import { Colors, Icon } from '@/utils/stepStyles';
import { showMessage, ErrorType } from '@/services/error/handler';

export interface FilesTreeProps {
  nodes: FileNode[];
  selectedKey: string;
  /** T3：recent-files 的 path 集合，命中标 ● */
  recentSet: Set<string>;
  loadedKeys: string[];
  onLoadedKeys: (keys: string[]) => void;
  onSelectFile: (node: FileNode) => void;
  /** F9：树上右键插入引用（可未打开） */
  onInsertRef: (node: FileNode) => void;
  /** J3（仅目录） */
  onSetWorkspace: (node: FileNode) => void;
  /** 降级补拉回填 */
  onPatchNodes: (parentKey: string, kids: FileNode[]) => void;
  /** 补拉一个目录（返回其子节点；已加载则返回 null） */
  onLoadDir: (key: string) => Promise<FileNode[] | null>;
}

export const FilesTree: React.FC<FilesTreeProps> = (props) => {
  const {
    nodes,
    selectedKey,
    recentSet,
    loadedKeys,
    onLoadedKeys,
    onSelectFile,
    onInsertRef,
    onSetWorkspace,
    onPatchNodes,
    onLoadDir,
  } = props;
  const [ctx, setCtx] = useState<{
    node: FileNode;
    x: number;
    y: number;
  } | null>(null);

  /** antd treeData 转换（每渲染重建 → 用 useMemo 缓存，5000 节点下不做无谓重建） */
  const treeData = useMemo<DataNode[]>(() => {
    const toData = (list: FileNode[]): DataNode[] =>
      list.map((n) => ({
        key: n.key,
        isLeaf: n.type === 'file',
        title: (
          <span data-file-key={n.key}>
            {/* Tooltip 只包文字 span，不包整行（M16，否则与展开箭头打架） */}
            <Tooltip title={`${n.name} · ${formatBytes(n.size)} · ${n.mtime}`}>
              <span
                style={
                  n.preview === 'none' && n.type === 'file'
                    ? { opacity: 0.4 }
                    : undefined
                }
              >
                {fileIcon(n)} {n.name}
                {recentSet.has(n.key) ? ' ●' : ''}
              </span>
            </Tooltip>
          </span>
        ),
        children: n.children ? toData(n.children) : undefined,
      }));
    return toData(nodes);
  }, [nodes, recentSet]);

  /** 降级补拉：incomplete_child 的目录展开时按需拉子节点（loadedKeys 记账不重复请求） */
  const onLoadData = async (node: DataNode) => {
    const key = String(node.key);
    if (loadedKeys.includes(key)) return;
    const kids = await onLoadDir(key);
    if (!kids) return;
    onPatchNodes(key, kids);
    onLoadedKeys([...loadedKeys, key]);
  };

  return (
    <>
      {nodes.length === 0 ? (
        <Empty description="目录为空" />
      ) : (
        <Tree
          treeData={treeData}
          loadData={onLoadData}
          showLine
          focusable // O9：键盘可达（antd Tree 默认 Enter 触发 onSelect）
          selectedKeys={selectedKey ? [selectedKey] : []}
          onSelect={(keys) => {
            const hit = keys[0];
            if (hit == null) return;
            const found = findNode(nodes, String(hit));
            if (found && found.type === 'file') onSelectFile(found);
          }}
          onContextMenu={(e: React.MouseEvent<HTMLDivElement>) => {
            // 2026-10-21 小杨 - 审计修复：antd 5.12 的 Tree **未暴露 onNodeContextMenu**
            //   （rc-tree 有，但被 antd 的 Omit 列表排除），且 rc-tree 的节点 DOM **无 data-key 属性**
            //   → 原写法 closest('[data-key]') 恒 null → 右键菜单永不弹出。
            //   现改为取**我们自己渲染的 title 上的 data-file-key**（可控、类型安全）。
            const holder = (e.target as HTMLElement).closest('[data-file-key]');
            const key = holder?.getAttribute('data-file-key');
            const hit = key ? findNode(nodes, key) : null;
            if (!hit) return;
            e.preventDefault();
            setCtx({ node: hit, x: e.clientX, y: e.clientY });
          }}
        />
      )}
      {ctx && (
        <Dropdown
          open
          menu={{
            items: [
              ...(ctx.node.type === 'dir'
                ? [
                    {
                      key: 'ws',
                      label: '设为会话工作目录',
                      onClick: () => onSetWorkspace(ctx.node),
                    },
                  ]
                : []),
              ...(ctx.node.type === 'file' && ctx.node.preview === 'text'
                ? [
                    {
                      key: 'ref',
                      label: '插入引用',
                      icon: (
                        <PaperClipOutlined style={{ fontSize: Icon.BOX }} />
                      ),
                      onClick: () => onInsertRef(ctx.node),
                    },
                  ]
                : []),
              {
                key: 'copy',
                label: '复制路径',
                onClick: () => {
                  void copyTextToClipboard(ctx.node.key).then((r) => {
                    if (!r.ok)
                      showMessage(
                        ErrorType.COPY_FAILED,
                        '复制失败，请手动复制路径'
                      );
                  });
                },
              },
            ],
          }}
          onOpenChange={(o) => {
            if (!o) setCtx(null);
          }}
        >
          <span style={{ position: 'fixed', left: ctx.x, top: ctx.y }} />
        </Dropdown>
      )}
    </>
  );
};

/** 按 key 在树里找节点（相对路径 key，唯一） */
export const findNode = (nodes: FileNode[], key: string): FileNode | null => {
  for (const n of nodes) {
    if (n.key === key) return n;
    if (n.children) {
      const hit = findNode(n.children, key);
      if (hit) return hit;
    }
  }
  return null;
};

/** 目录图标（工具条/标题用，避免各处再 import antd 图标） */
export const FilesTreeFolderIcon = FolderOutlined;

/** 树标题里的 ● 颜色（与 token 对齐，供外部复用） */
export const RECENT_DOT_COLOR = Colors.PRIMARY;
