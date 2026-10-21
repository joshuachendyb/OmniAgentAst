// 编辑历史: 2026-10-21 小杨 - 用自写树替换 antd Tree（antd Tree 的补丁堆积=选型错）：
//   自写树（block 流递归渲染，无 antd Tree 的 treenode>indent>switcher 抽象层）：
//   1) 目录行点击=展开/收起；首屏 5 层全量子级在 nodes.children 本地直接开（零请求）
//   2) 懒加载只对超深截断目录走 onLoadDir/onPatchNodes/onLoadedKeys
//   3) Ctrl 逐个 / Shift 区间（扁平序连线段）批量 → onSelectFiles（只收文件，目录不进批量）
//   4) 右键菜单（插入引用/设为会话工作目录/复制路径）自绘 fixed 浮层
//   5) antd Tree 特供补丁（files-tree-noswitcher CSS、expandable、multiple 手势）一并作废
//   2026-10-21 小杨 - 修复：展开集合改受控（深链定位可见）、多选集与预览集分离
//     （Ctrl 首次点选不再夹带预览文件）、空目录提示、hover 态落 CSS、复制失败不再静默 — 小杨-2026-10-21
import React, { useMemo, useState } from 'react';
import { Dropdown, Empty } from 'antd';
import { FolderOpenOutlined, FolderOutlined } from '@ant-design/icons';
import type { FileNode } from '@/services/api/file.api';
import { fileIcon } from '@/components/fileIcon';
import { formatBytes } from '@/utils/format';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { copyTextToClipboard } from '@/utils/clipboard';

export interface FilesTreeProps {
  nodes: FileNode[];
  /** 预览中的文件（浅蓝底，单选态） */
  activeKey: string;
  /** 批量勾选的文件（深灰底；Ctrl/Shift 只操作此集合） */
  checkedKeys: string[];
  /** recent-files 的 path 集合，命中标 ● */
  recentSet: Set<string>;
  /** 展开集合由上层层唯一持有（深链定位与树点击共用同一真源） */
  expandedKeys: string[];
  onExpandedKeys: React.Dispatch<React.SetStateAction<string[]>>;
  loadedKeys: string[];
  onLoadedKeys: React.Dispatch<React.SetStateAction<string[]>>;
  onSelectFile: (node: FileNode) => void;
  onSelectFiles?: (nodes: FileNode[]) => void;
  onInsertRef: (node: FileNode) => void;
  onSetWorkspace: (node: FileNode) => void;
  onPatchNodes: (parentKey: string, kids: FileNode[]) => void;
  onLoadDir: (key: string) => Promise<FileNode[] | null>;
}

/** 按 key 深度优先找节点（Files 页仍然引用此工具函数） */
export const findNode = (ns: FileNode[], key: string): FileNode | null => {
  for (const n of ns) {
    if (n.key === key) return n;
    if (n.children) {
      const hit = findNode(n.children, key);
      if (hit) return hit;
    }
  }
  return null;
};

export const FilesTree: React.FC<FilesTreeProps> = (props) => {
  const {
    nodes,
    activeKey,
    checkedKeys,
    recentSet,
    expandedKeys,
    onExpandedKeys,
    loadedKeys,
    onLoadedKeys,
    onSelectFile,
    onSelectFiles,
    onInsertRef,
    onSetWorkspace,
    onPatchNodes,
    onLoadDir,
  } = props;

  /** Shift 区间选择的起点锚（扁平序 index 由 key 反查） */
  const [anchor, setAnchor] = useState<string | null>(null);
  /** 右键菜单上下文 */
  const [ctx, setCtx] = useState<{
    node: FileNode;
    x: number;
    y: number;
  } | null>(null);

  /** 树扁平序（Shift 区间选择基于此序计算） */
  const flat = useMemo<FileNode[]>(() => {
    const out: FileNode[] = [];
    const walk = (ns: FileNode[]) => {
      for (const n of ns) {
        out.push(n);
        if (n.children) walk(n.children);
      }
    };
    walk(nodes);
    return out;
  }, [nodes]);

  /** 目录点击 = 展开/收起；本地已有子级零请求，只有超深截断目录才补拉 */
  const toggleExpand = (n: FileNode) => {
    const willOpen = !expandedKeys.includes(n.key);
    onExpandedKeys((prev) =>
      willOpen ? [...prev, n.key] : prev.filter((k) => k !== n.key)
    );
    if (willOpen && !loadedKeys.includes(n.key) && !n.children?.length) {
      void (async () => {
        try {
          const kids = await onLoadDir(n.key);
          if (kids && kids.length > 0) onPatchNodes(n.key, kids);
          // 2026-10-21 小杨 - 修复：函数式更新，避免并发补拉时
          //   闭包里的旧 loadedKeys 覆盖掉其它目录的登记
          onLoadedKeys((prev) =>
            prev.includes(n.key) ? prev : [...prev, n.key]
          );
        } catch {
          showMessage(ErrorType.FILE_READ, `无法加载「${n.name}」的子目录`);
        }
      })();
    }
  };

  /** 文件点击：无修饰=单选预览（清批量）；Ctrl=toggle；Shift=锚点区间（连线段只收文件） */
  const fileClick = (n: FileNode, e: React.MouseEvent) => {
    onSelectFile(n);
    if (!onSelectFiles) return;
    if (e.shiftKey) {
      // 2026-10-21 小杨 - 修复：首次 Shift 无锚点时以"当前预览文件"
      //   为锚；连预览都没有才退化为单选（原实现直接 return，点了没反应）
      const base = anchor ?? (activeKey || null);
      if (!base) {
        setAnchor(n.key);
        onSelectFiles([]);
        return;
      }
      if (!anchor) setAnchor(base);
      const ai = flat.findIndex((x) => x.key === base);
      const ci = flat.findIndex((x) => x.key === n.key);
      if (ai >= 0 && ci >= 0) {
        const [s, t] = ai <= ci ? [ai, ci] : [ci, ai];
        onSelectFiles(flat.slice(s, t + 1).filter((x) => x.type === 'file'));
      }
      return;
    }
    if (e.ctrlKey || e.metaKey) {
      // 2026-10-21 小杨 - 修复：多选集只从 checkedKeys 派生。
      //   原实现把"预览中的文件"并进集合 → 首次 Ctrl 点 B 会连未勾选的 A 一起引用。
      const keySet = new Set(checkedKeys);
      if (keySet.has(n.key)) keySet.delete(n.key);
      else keySet.add(n.key);
      onSelectFiles(flat.filter((x) => keySet.has(x.key) && x.type === 'file'));
      return;
    }
    setAnchor(n.key);
    onSelectFiles([]);
  };

  const renderRow = (n: FileNode, depth: number): React.ReactNode => {
    const isDir = n.type === 'dir';
    const isOpen = expandedKeys.includes(n.key);
    const checked = checkedKeys.includes(n.key);
    const active = activeKey === n.key;
    /** 已支持预览的文件才给完整信息；预览为 none 的文件降透明度（选中/预览中不压暗） */
    const dim = !isDir && n.preview === 'none';
    // 2026-10-21 小杨 - 修复：目录没有字节数，原实现显示「—」像坏数据
    const meta = isDir
      ? `${n.name} · ${n.mtime}`
      : `${n.name} · ${formatBytes(n.size)} · ${n.mtime}`;
    return (
      <div key={n.key}>
        <div
          data-file-key={n.key}
          data-checked={checked ? '1' : undefined}
          data-active={active && !checked ? '1' : undefined}
          className="files-tree-row"
          role="treeitem"
          aria-expanded={isDir ? isOpen : undefined}
          aria-selected={checked}
          aria-current={active ? 'true' : undefined}
          aria-label={meta}
          tabIndex={0}
          title={meta}
          onClick={(e) => (isDir ? toggleExpand(n) : fileClick(n, e))}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              if (isDir) toggleExpand(n);
              else fileClick(n, e as unknown as React.MouseEvent);
            }
          }}
          onContextMenu={(e) => {
            e.preventDefault();
            setCtx({ node: n, x: e.clientX, y: e.clientY });
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: `3px 8px 3px ${depth * 16 + 8}px`,
            cursor: 'pointer',
            opacity: dim && !checked && !active ? 0.4 : undefined,
          }}
        >
          {isDir ? (
            isOpen ? (
              <FolderOpenOutlined />
            ) : (
              <FolderOutlined />
            )
          ) : (
            fileIcon(n)
          )}
          {/* 2026-10-21 小杨 - 双 tooltip 收敛：只留**原生方框** title，
              antd 浮泡 Tooltip 移除（同一信息两套气泡是噪音） */}
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {n.name}
            {recentSet.has(n.key) ? ' ●' : ''}
          </span>
        </div>
        {isDir && isOpen && n.children?.map((c) => renderRow(c, depth + 1))}
        {/* 2026-10-21 小杨 - 修复：展开的空目录原先只剩一行目录名，
            看不出"没有子项"还是"加载失败"；补一行弱提示 */}
        {isDir &&
          isOpen &&
          Array.isArray(n.children) &&
          n.children.length === 0 && (
            <div
              style={{
                padding: `3px 8px 3px ${(depth + 1) * 16 + 8 + 20}px`,
                color: '#999',
                fontSize: 12,
              }}
            >
              （空目录）
            </div>
          )}
      </div>
    );
  };

  /** 右键菜单项（自绘 fixed 浮层，无 antd Dropdown 的多层结构） */
  const menuOpts: {
    key: string;
    label: string;
    disabled?: boolean;
    act: () => void;
  }[] = ctx
    ? [
        ...(ctx.node.type === 'file'
          ? [
              {
                key: 'ref',
                label: '插入引用',
                act: () => onInsertRef(ctx.node),
              },
            ]
          : []),
        {
          key: 'ws',
          label: '设为会话工作目录',
          disabled: true,
          act: () => onSetWorkspace(ctx.node),
        },
        {
          key: 'copy',
          label: '复制路径',
          act: () => {
            // 2026-10-21 小杨 - 修复：copyTextToClipboard 只 resolve {ok}
            //   从不 reject，原先 `.catch` 是死码 → 复制失败完全静默。
            void copyTextToClipboard(ctx.node.key).then((r) => {
              if (r.ok) showSuccess('路径已复制');
              else showMessage(ErrorType.COPY_FAILED, '复制失败，请手动复制');
            });
          },
        },
      ]
    : [];

  return (
    <>
      {nodes.length === 0 ? (
        <Empty description="目录为空" />
      ) : (
        flat.length > 0 && (
          <div style={{ minWidth: 0 }}>{nodes.map((n) => renderRow(n, 0))}</div>
        )
      )}
      {/* 右键菜单：自绘浮层（跟踪触发点坐标），离开自动收起 */}
      {ctx && (
        <Dropdown
          open
          onOpenChange={(o) => {
            if (!o) setCtx(null);
          }}
          trigger={['contextMenu']}
          menu={{
            items: menuOpts.map(({ key, label, disabled }) => ({
              key,
              label,
              disabled,
            })),
            onClick: ({ key, domEvent }) => {
              domEvent.stopPropagation();
              const hit = menuOpts.find((o) => o.key === key);
              setCtx(null);
              if (hit && !hit.disabled) hit.act();
            },
          }}
        >
          <span style={{ position: 'fixed', left: ctx.x, top: ctx.y }} />
        </Dropdown>
      )}
    </>
  );
};
