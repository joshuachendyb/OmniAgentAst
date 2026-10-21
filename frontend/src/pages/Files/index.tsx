// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.11 + 9.9.2 新建：文件管理页（工具条 + 树 + 预览 + 深链定位） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§9.9.2(O8/O10)：页级兜底（root 失败 → Result + 重试）+ 工具条 ↻ 三同刷（树 + ● + 预览） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§10.2(S1-9)：● 数据改用共享 hook useRecentFiles（与 FT1/FQ1 同源，不再各拉一次） — 小杨-2026-10-21
/**
 * /files —— 文件管理页（项目根目录浏览 + 文本查看）
 *
 * 只读边界（S3）：本页面**不提供任何写操作**，工具条常驻「🔒 只读浏览」标签。
 * 唯一例外是「设为会话工作目录」（J3）：那是**授权**而非写文件，本期只留骨架。
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Alert, Button, Empty, Grid, Input, Result, Tag } from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fileApi, type FileNode } from '@/services/api/file.api';
import { FilesTree, findNode } from '@/features/files/components/FilesTree';
import { FilePreview } from '@/features/files/components/FilePreview';
import {
  composerRefStore,
  newRefId,
} from '@/features/chat/streams/composerRefStore';
import { useRecentFiles } from '@/hooks/useRecentFiles';
import { readStoredSessionId } from '@/utils/sessionStorage';
import { Spacing, Colors } from '@/utils/stepStyles';

/** 树归并：按 key（相对路径）把补拉的子节点挂到父下（不可变更新，只改一路祖先） */
const mergeKids = (
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

const FilesPage: React.FC = () => {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { md } = Grid.useBreakpoint(); // antd 5.12 未从 'antd' 顶层导出 useBreakpoint，走 Grid 命名空间
  const isNarrow = md === false;

  const [projectRoot, setProjectRoot] = useState('');
  const [rootErr, setRootErr] = useState<string | null>(null);
  const [tree, setTree] = useState<FileNode[]>([]);
  const [treeErr, setTreeErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<FileNode | null>(null);
  const [lineRange, setLineRange] = useState<{
    start: number;
    end: number;
  } | null>(null);
  const [loadedKeys, setLoadedKeys] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [leftW, setLeftW] = useState(320);
  const [locate, setLocate] = useState('');

  /** tree 的 ref 镜像（异步链里读最新值，不能只靠 state 闭包） */
  const treeRef = useRef<FileNode[]>([]);
  const refreshPreviewRef = useRef<(() => void) | null>(null);

  const sessionId = useMemo(() => readStoredSessionId(), []);
  /** T3 ●：共享 hook（树 / FT1 面板 / FQ1 三处同源同型） */
  const { files: recentFiles, reload: reloadRecent } =
    useRecentFiles(sessionId);
  const recentSet = useMemo(
    () => new Set(recentFiles.map((f) => f.path)),
    [recentFiles]
  );

  /** O8：页级兜底 —— root 拉不到 → 整页 Result + 重试（不静默空页） */
  const loadRoot = useCallback(async () => {
    setRootErr(null);
    try {
      const r = await fileApi.fetchRoot();
      setProjectRoot(r.project_root);
    } catch {
      setProjectRoot('');
      setRootErr('工作目录不可用：请检查 workspace.project_root 配置');
    }
  }, []);

  const loadTree = useCallback(async () => {
    setTreeErr(null);
    try {
      const r = await fileApi.fetchTree('');
      treeRef.current = r.nodes;
      setTree(r.nodes);
      setLoadedKeys([]);
    } catch {
      setTreeErr('目录加载失败，请重试');
    }
  }, []);

  useEffect(() => {
    void loadRoot();
  }, [loadRoot]);
  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  /** J2 深链定位：读 ?path=（逐级补拉）+ &line=（交 FilePreview 高亮） */
  const expandToPath = useCallback(
    async (rel: string): Promise<FileNode | null> => {
      const segs = rel.split('/').filter(Boolean);
      let cur = '';
      const expanded = [...expandedKeys];
      for (const s of segs) {
        cur = cur ? `${cur}/${s}` : s;
        let hit = findNode(treeRef.current, cur);
        if (!hit) return null; // 路径不存在 → 调用方给明确提示（J2 失败分支，不静默）
        if (hit.type === 'dir' && !hit.children) {
          const r = await fileApi.fetchTree(cur);
          const merged = mergeKids(treeRef.current, cur, r.nodes);
          treeRef.current = merged;
          setTree(merged);
          setLoadedKeys((prev) => (prev.includes(cur) ? prev : [...prev, cur]));
          hit = findNode(treeRef.current, cur);
          if (!hit) return null;
        }
        if (!expanded.includes(cur)) expanded.push(cur);
      }
      setExpandedKeys(expanded);
      return findNode(treeRef.current, rel);
    },
    [expandedKeys]
  );

  /** 深链进入：?path=…&line=… */
  useEffect(() => {
    const rel = params.get('path');
    if (!rel) return;
    void (async () => {
      const hit = await expandToPath(rel);
      if (hit && hit.type === 'file') {
        setSelected(hit);
        const line = params.get('line');
        if (line) {
          const m = /^(\d+)-(\d+)$/.exec(line);
          if (m) setLineRange({ start: Number(m[1]), end: Number(m[2]) });
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  /** 三途径统一 push（发送到输入框 / 树右键插入引用 / 引用选区 —— 产物等价） */
  const pushRef = useCallback(
    (
      kind: 'file' | 'selection',
      label: string,
      path: string,
      content: string,
      size: number,
      range?: { start: number; end: number }
    ) => {
      composerRefStore.push({
        id: newRefId(),
        kind,
        label,
        path,
        content,
        size,
        lineRange: range ?? null,
      });
      nav(`/?session_id=${encodeURIComponent(sessionId ?? '')}`);
    },
    [nav, sessionId]
  );

  /** 补拉一个目录（降级） */
  const loadDir = useCallback(
    async (key: string): Promise<FileNode[] | null> => {
      try {
        const r = await fileApi.fetchTree(key);
        return r.nodes;
      } catch {
        return null;
      }
    },
    []
  );

  const patchNodes = useCallback((parentKey: string, kids: FileNode[]) => {
    const merged = mergeKids(treeRef.current, parentKey, kids);
    treeRef.current = merged;
    setTree(merged);
  }, []);

  /** O10：工具条 ↻ 三同刷（树 + ● + 预览共用一次点击） */
  const refreshAll = useCallback(() => {
    void loadTree();
    void reloadRecent();
    refreshPreviewRef.current?.();
  }, [loadTree, reloadRecent]);

  /** 左右拖拽（280~600px；窄屏堆叠时关闭） */
  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault();
    const x0 = e.clientX;
    const w0 = leftW;
    const move = (ev: MouseEvent) => {
      setLeftW(Math.min(600, Math.max(280, w0 + ev.clientX - x0)));
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  if (rootErr) {
    return (
      <Result
        status="error"
        title="工作目录不可用"
        subTitle={rootErr}
        extra={<Button onClick={() => void loadRoot()}>重试</Button>}
      />
    );
  }

  return (
    <div style={{ padding: Spacing.MD }}>
      {/* 工具条 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          marginBottom: Spacing.MD,
        }}
      >
        <Tag color="default">🔒 只读浏览</Tag>
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          {projectRoot || '读取中…'}
        </span>
        <Input
          placeholder="定位路径"
          value={locate}
          onChange={(e) => setLocate(e.target.value)}
          onPressEnter={() => {
            if (!locate.trim()) return;
            void expandToPath(locate.trim());
          }}
          style={{ width: 220 }}
        />
        <Button onClick={refreshAll}>↻刷新</Button>
        {/* J3：本期只留骨架（按钮 + 常驻说明），接线等后端 _ws_deny_reason 修完再做 */}
        <Button
          disabled={!sessionId}
          title={
            sessionId
              ? '设为会话工作目录（本期仅骨架，后端校验通过后开放）'
              : '无会话时不可设置'
          }
        >
          设为会话工作目录
        </Button>
      </div>

      <div
        style={{
          display: 'flex',
          gap: 0,
          alignItems: 'stretch',
          height: 'calc(100vh - 140px)',
        }}
      >
        {/* 左：树 */}
        <div
          style={{
            width: isNarrow ? '100%' : leftW,
            minWidth: isNarrow ? undefined : 280,
            maxWidth: isNarrow ? undefined : 600,
            overflow: 'auto',
            paddingRight: Spacing.SM,
          }}
        >
          {treeErr ? (
            <Alert
              type="warning"
              message={treeErr}
              action={
                <Button size="small" onClick={() => void loadTree()}>
                  重试
                </Button>
              }
            />
          ) : (
            <FilesTree
              nodes={tree}
              selectedKey={selected?.key ?? ''}
              recentSet={recentSet}
              loadedKeys={loadedKeys}
              onLoadedKeys={setLoadedKeys}
              onSelectFile={(n) => {
                setSelected(n);
                setLineRange(null);
              }}
              onInsertRef={(n) => {
                void (async () => {
                  try {
                    const r = await fileApi.readFile(n.key);
                    pushRef('file', n.name, n.key, r.content, r.size);
                  } catch {
                    /* 失败由提示通道负责（见 FilePreview 同款处理） */
                  }
                })();
              }}
              onSetWorkspace={() => {
                /* J3 本期不接线 */
              }}
              onPatchNodes={patchNodes}
              onLoadDir={loadDir}
            />
          )}
        </div>

        {/* 分隔条（窄屏不拖拽） */}
        {!isNarrow && (
          <div
            onMouseDown={startDrag}
            style={{ width: 6, cursor: 'col-resize', flexShrink: 0 }}
          />
        )}

        {/* 右：预览 */}
        <div style={{ flex: 1, overflow: 'auto', paddingLeft: Spacing.SM }}>
          {tree.length === 0 && !treeErr ? (
            <Empty description="目录为空" />
          ) : (
            <FilePreview
              node={selected}
              lineRange={lineRange}
              refreshRef={refreshPreviewRef}
              onSendFile={(content, node) =>
                pushRef('file', node.name, node.key, content, content.length)
              }
              onSendSelection={(content, node, range) =>
                pushRef(
                  'selection',
                  `${node.name} L${range.start}-${range.end}`,
                  node.key,
                  content,
                  content.length,
                  range
                )
              }
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default FilesPage;
