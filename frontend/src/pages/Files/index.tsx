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
import {
  Alert,
  Button,
  ConfigProvider,
  Empty,
  Grid,
  Input,
  Result,
  Spin,
  Tabs,
  Tag,
} from 'antd';
import { LockOutlined, PaperClipOutlined } from '@ant-design/icons';
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
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { Spacing, Colors } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
// 2026-10-21 小杨 - 控件规格统一（北京老陈痛骂"全系统的规范忘记了"）：直接复用
//   设置页设计令牌——控件高 28/圆角 4（taskTokens 推导与依据见 settingsTokens 注释）
import {
  SETTINGS_CONTROL_HEIGHT,
  SETTINGS_RADIUS,
} from '@/theme/settingsTokens';

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
  const [treeReady, setTreeReady] = useState(false); // 2026-10-21 小杨 - 深链需等树就绪
  const [treeLoading, setTreeLoading] = useState(true); // 2026-10-21 小杨 - 三态分离：加载中/空/错
  const [locateErr, setLocateErr] = useState<string | null>(null); // 定位失败的页内留痕
  const [narrowTab, setNarrowTab] = useState<'tree' | 'preview'>('tree'); // 窄屏 Tab
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
  /** 2026-10-21 小杨 - 体验审计：**就地收集**的本地台账（store 为真源，这里只为计数与去重展示） */
  const [collectedKeys, setCollectedKeys] = useState<string[]>([]);
  /** #12 批量引用：树 multiple 勾选的文件集合（预览单选仍走 selected，两者语义分开） */
  const [multiFiles, setMultiFiles] = useState<FileNode[]>([]);

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
      // 2026-10-21 小杨 - 体验审计：用户口吻（原「请检查 workspace.project_root 配置」是开发者语言）
      setRootErr('项目根目录不存在或不可访问，请检查「工作目录」设置后重试。');
    }
  }, []);

  const loadTree = useCallback(async () => {
    setTreeErr(null);
    setTreeLoading(true);
    try {
      const r = await fileApi.fetchTree('');
      treeRef.current = r.nodes;
      setTree(r.nodes);
      setLoadedKeys([]);
      setTreeReady(true); // 2026-10-21 小杨 - 审计修复：深链 effect 需等树就绪
    } catch {
      setTreeErr('目录加载失败，请重试');
    } finally {
      setTreeLoading(false);
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

  /**
   * 统一的"打开一个路径"入口（2026-10-21 小杨 - 体验审计最佳改造）
   *
   *   之前有 4 条各自半截的路径（深链 / 定位框 / 树点击 / 外部 chip），彼此不同步：
   *   定位框甚至**返回值被丢弃**（点了没反应）。
   *   现在统一为一条：定位（展开目录）→ 选中 → 高亮行 → 焦点落到内容。
   *   返回是否命中，调用方据此给"未找到"提示。
   */
  const openPath = useCallback(
    async (
      rel: string,
      line?: { start: number; end: number } | null
    ): Promise<boolean> => {
      const hit = await expandToPath(rel);
      if (!hit) return false;
      if (hit.type === 'dir') {
        // 目录：只展开定位（左侧树已展开到该目录），右侧保持上一份内容
        setSelected(null);
        return true;
      }
      setSelected(hit);
      setLineRange(line ?? null);
      return true;
    },
    [expandToPath]
  );

  /** 深链进入：?path=…&line=… */
  useEffect(() => {
    const rel = params.get('path');
    // 2026-10-21 小杨 - 审计修复（阻断）：原 effect 在**树未就绪**时就跑
    //   （loadTree 是 void 发起，同步段只走到第一个 await → treeRef.current 仍是 []）
    //   → findNode 恒 null → 深链 100% 失效（预览空白、树不定位、无任何提示）。
    //   现在等 treeReady 后再展开。
    if (!rel || !treeReady) return;
    void (async () => {
      const line = params.get('line');
      const m = line ? /^(\d+)-(\d+)$/.exec(line) : null;
      const ok = await openPath(
        rel,
        m ? { start: Number(m[1]), end: Number(m[2]) } : null
      );
      if (!ok) {
        // 页内留痕（不只弹一下 toast）：否则用户以为"点了没反应"
        setLocate(rel);
        setLocateErr(`未找到「${rel}」，请检查路径或从左侧树中选择`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, treeReady]);

  /**
   * 三途径统一 push（引用到对话 / 树右键引用 / 引用选区 —— 产物等价）
   *
   * 2026-10-21 小杨 - 体验审计（**设计模型变更，已获北京老陈批准**）：
   *   原实现每次引用都 `nav` 到会话页 → 用户读/挑多个文件时被反复踢出工作现场，
   *   且**无法批量**（引 3 个文件 = 3 次离开 + 3 次返回，阅读位置全丢）。
   *   现改为**就地收集**：只入 store + 计数，页面不动；用户点「去对话」时一次带走。
   */
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
      const key = `${path}|${range ? `${range.start}-${range.end}` : ''}`;
      setCollectedKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
      showSuccess(`已引用「${label}」`);
    },
    []
  );

  /** 去对话：此时才导航，ChatInput 挂载即消费 store 里的引用 */
  const goChat = useCallback(() => {
    nav(`/?session_id=${encodeURIComponent(sessionId ?? '')}`);
  }, [nav, sessionId]);

  /** 清空本次收集（同时清 store —— 否则"清空"只清了界面，引用仍会被带入对话） */
  const clearCollected = useCallback(() => {
    composerRefStore.clear();
    setCollectedKeys([]);
  }, []);

  /** #12 引用所选（批量）：逐个读正文 → 就地收集；全部成功才清空勾选 */
  const refSelectedFiles = useCallback(async () => {
    const ok: string[] = [];
    await Promise.all(
      multiFiles.map(async (n) => {
        try {
          const r = await fileApi.readFile(n.key);
          pushRef('file', n.name, n.key, r.content, r.size);
          ok.push(n.key);
        } catch {
          showMessage(ErrorType.FILE_READ, `无法读取「${n.name}」，未引用`);
        }
      })
    );
    if (ok.length === multiFiles.length) setMultiFiles([]);
  }, [multiFiles, pushRef]);

  /** 补拉一个目录（降级） */
  const loadDir = useCallback(
    async (key: string): Promise<FileNode[] | null> => {
      try {
        // 2026-10-21 小杨 - 北京老陈拍板：补拉**到 10 层**（首屏 5 秒开；子树量级可控才补得快）
        const r = await fileApi.fetchTree(key, 10);
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

  /**
   * 树 / 预览两个**内容单元**（2026-10-21 小杨 - 体验审计）
   *   窄屏作为 Tabs 的 children（单一真源）；宽屏左右分栏。原实现 Tabs 的 children 是 null、
   *   真实内容在 Tabs 外用 display:none 切换 → 标签条与内容区分离，Tab 面板是空壳。
   */
  const treePane = treeErr ? (
    <Alert
      type="warning"
      showIcon
      message={treeErr}
      action={
        <Button size="small" onClick={() => void loadTree()}>
          重试
        </Button>
      }
    />
  ) : treeLoading ? (
    /* 三态严格分离：加载中=Spin / 空=Empty / 错=Alert（加载中显示"目录为空"会让用户判定仓库是空的） */
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        padding: Spacing.LG,
      }}
    >
      <Spin tip="正在加载目录…" />
    </div>
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <FilesTree
          nodes={tree}
          selectedKey={selected?.key ?? ''}
          /* #12：预览单选 + 批量勾选共用一套受控键（去重），保证两类选择都有视觉反馈 */
          selectedKeys={Array.from(
            new Set(
              [
                ...(selected ? [selected.key] : []),
                ...multiFiles.map((n) => n.key),
              ].filter(Boolean)
            )
          )}
          recentSet={recentSet}
          loadedKeys={loadedKeys}
          onLoadedKeys={setLoadedKeys}
          onSelectFile={(n) => {
            setSelected(n);
            setLineRange(null);
            // 窄屏点文件后**自动切到预览**（否则用户点了却"什么都没发生"）
            if (isNarrow) setNarrowTab('preview');
          }}
          onSelectFiles={setMultiFiles}
          onInsertRef={(n) => {
            void (async () => {
              try {
                const r = await fileApi.readFile(n.key);
                pushRef('file', n.name, n.key, r.content, r.size);
              } catch {
                // 失败必须可感知（原实现静默吞掉 → 用户不知为何）
                showMessage(ErrorType.FILE_READ, '无法读取该文件，未能引用');
              }
            })();
          }}
          onSetWorkspace={() => {
            /* J3 本期不接线 */
          }}
          onPatchNodes={patchNodes}
          onLoadDir={loadDir}
        />
      </div>
    </div>
  );

  const previewPane =
    tree.length === 0 && !treeErr && !treeLoading ? (
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
    );

  /** 2026-10-21 小杨 - 控件规格统一（北京老陈拍板·三堂会审）：设置页同款
      ConfigProvider 落地——高 28/圆角 4；small 控件同压 28（页内不再 24/32 两档参差） */
  const pageTheme = {
    token: {
      controlHeight: SETTINGS_CONTROL_HEIGHT,
      controlHeightSM: SETTINGS_CONTROL_HEIGHT,
      borderRadius: SETTINGS_RADIUS,
      borderRadiusSM: SETTINGS_RADIUS,
    },
  } as const;

  if (rootErr) {
    return (
      <ConfigProvider theme={pageTheme}>
        <Result
          status="error"
          title="工作目录不可用"
          subTitle={rootErr}
          extra={<Button onClick={() => void loadRoot()}>重试</Button>}
        />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={pageTheme}>
      <div
        style={{
          padding: Spacing.MD,
          // 2026-10-21 小杨 - 体验审计（#2）：根改为**flex column + 撑满视口**
          //   原中间区 height:calc(100vh-140px) 是手算 —— 收集条一出现就溢出视口 40px。
          //   现在：工具条/收集条 flexShrink:0，中间区 flex:1 → 多一条内容，树/预览自动让位。
          display: 'flex',
          flexDirection: 'column',
          // 2026-10-21 小杨 - 底部空白（北京老陈痛骂）：calc(100vh-100px) 的 100 是拍脑袋
          //   （真实 chrome=Header43+Content padding10≈53px），改 height:100% 由
          //   Layout Content(flex:1+minHeight:0) 给准高度，贴合到底不空截。
          height: '100%',
          overflow: 'hidden',
        }}
      >
        {/* 工具条 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap', // 2026-10-21 小杨 - 体验审计（#9）：6 元素一行，1280 以下换行而非溢出
            gap: Spacing.SM,
            marginBottom: Spacing.MD,
            flexShrink: 0,
          }}
        >
          {/* 2026-10-21 小杨 - 体验审计最佳改造（工具条重排）：
            左=只读标识（图标替代 emoji）｜中=根路径（**截断+tooltip**，不再挤压控件）｜右=操作组
            并新增「当前会话」可见性 —— 跨页引用时用户必须知道引用会进哪个会话。 */}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: Colors.TEXT.SECONDARY,
            }}
            title="本页只读，不会修改任何文件"
          >
            <LockOutlined style={{ fontSize: 12 }} />
            只读浏览
          </span>
          <span
            title={projectRoot || '读取中…'}
            style={{
              color: Colors.TEXT.SECONDARY,
              maxWidth: 260,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {projectRoot || '读取中…'}
          </span>
          {sessionId ? (
            <Tag
              color="default"
              style={{ marginInlineEnd: 0 }}
              // 2026-10-21 小杨 - 体验审计：**不显示 UUID 前 8 位**（不可辨识，等于没有信息）
              //   完整会话 id 放 tooltip（需要核对时仍可核对）
              title={`引用会加入会话 ${sessionId}`}
            >
              当前会话
            </Tag>
          ) : (
            <Tag
              color="warning"
              style={{ marginInlineEnd: 0 }}
              title="尚无会话：引用会加入新会话"
            >
              新会话
            </Tag>
          )}
          {/* 2026-10-21 小杨 - 体验反馈（北京老陈）：手势提示**常驻**（勾选前也要看得见）
            勾选数不重复念 ——「引用所选 N 个」按钮本身已携带数量 */}
          <span
            style={{
              color: Colors.TEXT.SECONDARY,
              fontSize: chatTokens.fontSM,
            }}
          >
            多选：Ctrl 逐个 / Shift 连选
          </span>
          {multiFiles.length > 0 && (
            <>
              <Button
                size="small"
                type="primary"
                onClick={() => void refSelectedFiles()}
              >
                引用所选 {multiFiles.length} 个
              </Button>
              <Button
                size="small"
                type="text"
                onClick={() => setMultiFiles([])}
              >
                取消
              </Button>
            </>
          )}
          <span style={{ flex: 1 }} />
          <Input
            placeholder="定位路径（回车）"
            value={locate}
            onChange={(e) => {
              setLocate(e.target.value);
              if (locateErr) setLocateErr(null);
            }}
            onPressEnter={() => {
              if (!locate.trim()) return;
              void (async () => {
                const ok = await openPath(locate.trim());
                if (!ok) setLocateErr(`未找到「${locate.trim()}」`);
              })();
            }}
            style={{ width: 200 }}
            aria-label="定位路径"
          />
          <Button onClick={refreshAll} title="重新加载目录与足迹">
            重新加载
          </Button>
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

        {/* 2026-10-21 小杨 - 体验审计（就地收集）：收集条常驻显示"已引用多少 + 何时送走"
          —— 引用不再立刻跳页，用户需要一个明确的"我攒了几个、去哪送"的落点。 */}
        {collectedKeys.length > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.SM,
              marginBottom: Spacing.SM,
              padding: `${Spacing.XS}px ${Spacing.MD}px`,
              flexShrink: 0, // 2026-10-21 小杨 - 体验审计：flex 根布局下不被压缩
              background: Colors.BG.WARNING_LIGHT,
              border: `1px solid ${Colors.BORDER.LIGHT}`,
              borderRadius: 4,
            }}
          >
            <PaperClipOutlined style={{ color: Colors.WARNING }} />
            <span style={{ color: Colors.TEXT.STRONG }}>
              已引用 {collectedKeys.length} 个文件
            </span>
            <span style={{ color: Colors.TEXT.SECONDARY }}>
              已收集随时可用：从这里离开（含直接进会话页）引用都会带上，发送前可再编辑
            </span>
            <span style={{ flex: 1 }} />
            <Button size="small" onClick={clearCollected}>
              清空
            </Button>
            <Button size="small" type="primary" onClick={goChat}>
              去对话
            </Button>
          </div>
        )}

        {locateErr && (
          <Alert
            type="warning"
            showIcon
            message={locateErr}
            style={{ marginBottom: Spacing.SM }}
            action={
              <Button size="small" onClick={() => setLocateErr(null)}>
                知道了
              </Button>
            }
          />
        )}

        {isNarrow ? (
          <Tabs
            size="small"
            activeKey={narrowTab}
            onChange={(k) => setNarrowTab(k as 'tree' | 'preview')}
            items={[
              { key: 'tree', label: '文件', children: treePane },
              { key: 'preview', label: '预览', children: previewPane },
            ]}
            style={{ flex: 1, minWidth: 0, minHeight: 0 }}
          />
        ) : (
          <div
            style={{
              display: 'flex',
              gap: 0,
              alignItems: 'stretch',
              flex: 1,
              minHeight: 0,
            }}
          >
            {/* 左：树 */}
            <div
              style={{
                width: leftW,
                minWidth: 280,
                maxWidth: 600,
                overflow: 'auto',
                paddingRight: Spacing.SM,
              }}
            >
              {treePane}
            </div>

            {/* 分隔条：role="separator" + aria-valuenow + 方向键调节（键盘/触屏可达） */}
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="调整目录宽度"
              aria-valuenow={leftW}
              aria-valuemin={280}
              aria-valuemax={600}
              tabIndex={0}
              onMouseDown={startDrag}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft') {
                  e.preventDefault();
                  setLeftW((w) => Math.max(280, w - 16));
                } else if (e.key === 'ArrowRight') {
                  e.preventDefault();
                  setLeftW((w) => Math.min(600, w + 16));
                }
              }}
              style={{
                width: 6,
                cursor: 'col-resize',
                flexShrink: 0,
                background: 'transparent',
                borderRadius: 3,
                transition: 'background 120ms',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = Colors.BORDER.DEFAULT;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            />

            {/* 右：预览 */}
            <div
              style={{
                flex: 1,
                minHeight: 0,
                // 2026-10-21 小杨 - 空白根治（北京老陈拍板）：右栏成 flex column，
                //   FilePreview 的 pre 以 flex:1 吃满剩余高度（滚动在 pre 内）
                display: 'flex',
                flexDirection: 'column',
                overflow: 'auto',
                paddingLeft: Spacing.SM,
              }}
            >
              {previewPane}
            </div>
          </div>
        )}
      </div>
    </ConfigProvider>
  );
};

export default FilesPage;
