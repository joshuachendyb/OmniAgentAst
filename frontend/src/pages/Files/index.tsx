// 编辑历史: 2026-10-21 小杨 - 新建文件管理页：工具条 + 树 + 预览 + 深链定位；
//   页级兜底（root 失败 → Result + 重试）、工具条刷新（树 + 足迹 + 预览共用一次点击）、
//   足迹数据改用共享 hook useRecentFiles（树 / 足迹面板 / 推荐三处同源同型）— 小杨-2026-10-21
//   2026-10-21 小杨 - 修复：树三态合为状态机、展开集合唯一真源、定位输入自持状态、
//     分栏宽度内聚（拖拽不重绘树/预览）、主题常量上提、border-box 消 16px 溢出、引用体量统一字节 — 小杨-2026-10-21
//   2026-10-21 小欧 - ① 消费后端扫描标志（truncated/incomplete_depth/skipped/skipped_cycles）：
//     原先三标志全丢，目录被截断而用户毫不知情 → 树上方如实提示（每条一行、可折行、保留条数）；
//   ② 摘掉工具条「设为会话工作目录」死按钮（无 onClick 的骨架，点了没反应）— 小欧-2026-10-21
//   2026-10-21 小欧 - 树请求竞态防护（I7）：替换型请求（整树刷新）走 AbortController 取消上一轮，
//     合并型请求（补拉子树）按键序号丢弃过期响应（不同键并发合法，不能一 abort 了之）— 小欧-2026-10-21
//   2026-10-21 小欧 - J3「设为会话工作目录」实现：树右键菜单入口 + 先 GET 后 PATCH（全量覆盖语义），
//     相对→绝对路径走 utils/projectPath.ts，422 的 workspace_rejected 逐条呈现 — 小欧-2026-10-21
// 2026-10-22 小杨 - 深链路径归一（Windows 反斜杠与 ./ 前缀），否则按 posix 拆分定位必失败 — 小杨-2026-10-22
// 2026-10-22 小欧 - 深链/定位命中后树滚动到定位行（reveal 信号 → FilesTree 提交后 effect 自滚，
//   竞态根治）+ 窄屏深链目标是文件时自动切预览 Tab（与树点击对齐）— 小欧-2026-10-22

/**
 * /files —— 文件管理页（项目根目录浏览 + 文本查看）
 *
 * 只读边界：本页面**不提供任何写操作**，工具条常驻「只读浏览」标签。
 * 2026-10-22 小杨 - 订正上一条「设为会话工作目录入口下线」的**错误说明**：
 *   该入口**保留**（树右键菜单 → 先 GET 后 PATCH 全量覆盖），后端确有会话工作目录能力
 *   （session_workspace 快照 + 会话 workspaces 接口），并非死入口；
 *   本页仍不写任何文件 —— 设工作目录只改「Agent 可访问范围」，不落盘。
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
import { sessionApi } from '@/services/api/session.api';
import { toAbsolutePath, samePath } from '@/utils/projectPath';
import { FilesTree, findNode } from '@/features/files/components/FilesTree';
import { FilePreview } from '@/features/files/components/FilePreview';
import {
  composerRefStore,
  newRefId,
} from '@/features/refs/store';
import { useRecentFiles } from '@/hooks/useRecentFiles';
import { readStoredSessionId } from '@/utils/sessionStorage';
import {
  showMessage,
  showSuccess,
  ErrorType,
  isSilentError,
} from '@/services/error/handler';
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

/**
 * 2026-10-21 小欧 - 扫描不完整提示（truncated / incomplete_depth / skipped / skipped_cycles 四源）：
 *   后端一直在算这几个标志，但前端原先只取 r.nodes 全丢 → 用户以为看到的是完整目录
 *   （大仓下目录被截断而用户毫不知情）。此处如实告知，**几段拼成一行**显示（过长自动折行）。
 *   措辞按后端口径分列：skipped＝真读不到，skipped_cycles＝链接绕回已展开目录被防环拦下。
 */
const buildScanNotices = (r: {
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

/** 2026-10-21 小杨 - 修复：树的加载态升级为单一状态机
 *  （原 treeLoading/treeReady/treeErr 三个布尔可组合出"就绪且加载中且报错"的非法态） */
type TreeStatus =
  | { phase: 'loading' }
  | { phase: 'ready' }
  | { phase: 'error'; message: string };

const MIN_LEFT_W = 280;
const MAX_LEFT_W = 600;

/** 2026-10-21 小杨 - 控件规格统一：设置页同款常量（控件高 28 / 圆角 4）
 *  —— 提升到模块级，避免每次 render 新建 theme 对象触发 ConfigProvider 全树重算 */
const PAGE_THEME = {
  token: {
    controlHeight: SETTINGS_CONTROL_HEIGHT,
    controlHeightSM: SETTINGS_CONTROL_HEIGHT,
    borderRadius: SETTINGS_RADIUS,
    borderRadiusSM: SETTINGS_RADIUS,
  },
} as const;

/** 定位输入（自带草稿与错误态）：输入过程只重绘本组件，不惊动树/预览 */
const LocateBox: React.FC<{
  onLocate: (rel: string) => Promise<boolean>;
}> = ({ onLocate }) => {
  const [value, setValue] = useState('');
  const [err, setErr] = useState<string | null>(null);
  return (
    <>
      <Input
        placeholder="定位路径（回车）"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          if (err) setErr(null);
        }}
        onPressEnter={() => {
          const rel = value.trim();
          if (!rel) return;
          void onLocate(rel).then((ok) =>
            setErr(ok ? null : `未找到「${rel}」`)
          );
        }}
        style={{ width: 200 }}
        aria-label="定位路径"
      />
      {err && (
        <span
          role="alert"
          style={{ color: Colors.WARNING, fontSize: chatTokens.fontSM }}
        >
          {err}
        </span>
      )}
    </>
  );
};

/** 左右分栏（宽度状态内聚）：拖拽只重绘本组件，树/预览 element 引用不变 → React 跳过其子树 */
const SplitPane: React.FC<{
  left: React.ReactNode;
  right: React.ReactNode;
}> = ({ left, right }) => {
  const [leftW, setLeftW] = useState(320);
  const cleanupRef = useRef<(() => void) | null>(null);
  useEffect(() => () => cleanupRef.current?.(), []);

  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault();
    const x0 = e.clientX;
    const w0 = leftW;
    const move = (ev: MouseEvent) =>
      setLeftW(
        Math.min(MAX_LEFT_W, Math.max(MIN_LEFT_W, w0 + ev.clientX - x0))
      );
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      cleanupRef.current = null;
    };
    cleanupRef.current = up;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: 0,
        alignItems: 'stretch',
        flex: 1,
        minHeight: 0,
      }}
    >
      <div
        style={{
          width: leftW,
          minWidth: MIN_LEFT_W,
          maxWidth: MAX_LEFT_W,
          overflow: 'auto',
          paddingRight: Spacing.SM,
        }}
      >
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="调整目录宽度"
        aria-valuenow={leftW}
        aria-valuemin={MIN_LEFT_W}
        aria-valuemax={MAX_LEFT_W}
        tabIndex={0}
        className="files-splitter"
        onMouseDown={startDrag}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            e.preventDefault();
            setLeftW((w) => Math.max(MIN_LEFT_W, w - 16));
          } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            setLeftW((w) => Math.min(MAX_LEFT_W, w + 16));
          }
        }}
        style={{
          width: 6,
          cursor: 'col-resize',
          flexShrink: 0,
          borderRadius: 3,
        }}
      />
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
          paddingLeft: Spacing.SM,
        }}
      >
        {right}
      </div>
    </div>
  );
};

const FilesPage: React.FC = () => {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { md } = Grid.useBreakpoint(); // antd 5.12 未从 'antd' 顶层导出 useBreakpoint，走 Grid 命名空间
  const isNarrow = md === false;

  const [projectRoot, setProjectRoot] = useState('');
  const [rootErr, setRootErr] = useState<string | null>(null);
  /** 2026-10-21 小欧 - 扫描不完整提示（truncated/incomplete_depth/skipped/skipped_cycles）；空数组＝结果完整 */
  const [scanNotices, setScanNotices] = useState<string[]>([]);
  const [tree, setTree] = useState<FileNode[]>([]);
  /** 2026-10-21 小杨 - 深链需等树就绪；加载/就绪/错误三态合一 */
  const [treeStatus, setTreeStatus] = useState<TreeStatus>({
    phase: 'loading',
  });
  /** 深链失败留痕（与定位框自身的草稿/错误无关，互不牵连） */
  const [linkErr, setLinkErr] = useState<string | null>(null);
  const [narrowTab, setNarrowTab] = useState<'tree' | 'preview'>('tree'); // 窄屏 Tab
  const [selected, setSelected] = useState<FileNode | null>(null);
  const [lineRange, setLineRange] = useState<{
    start: number;
    end: number;
  } | null>(null);
  const [loadedKeys, setLoadedKeys] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  /**
   * 2026-10-22 小欧 - 滚动定位信号：openPath 命中后递增，FilesTree 在提交后的
   *   effect 里把该行滚入视口（n 自增保证同 key 重复定位也触发）— 小欧-2026-10-22
   */
  const [reveal, setReveal] = useState<{ key: string; n: number } | null>(null);
  /** 2026-10-21 小杨 - **就地收集**的本地台账（store 为真源，这里只为计数与去重展示） */
  const [collectedKeys, setCollectedKeys] = useState<string[]>([]);
  /** 批量引用：树 checked 勾选的文件集合（预览单选仍走 selected，两者语义分开） */
  const [multiFiles, setMultiFiles] = useState<FileNode[]>([]);

  /** 从单一状态机派生的视图布尔（不作为独立 state，避免非法组合） */
  const treeReady = treeStatus.phase === 'ready';
  const treeLoading = treeStatus.phase === 'loading';
  const treeErr = treeStatus.phase === 'error' ? treeStatus.message : null;

  /** tree 的 ref 镜像（异步链里读最新值，不能只靠 state 闭包） */
  const treeRef = useRef<FileNode[]>([]);
  const refreshPreviewRef = useRef<(() => void) | null>(null);

  /**
   * 树请求生命周期（I7）：替换型（整树刷新）独占通道，新请求 abort 旧请求；
   * 合并型（补拉子树）按键序号丢弃过期响应 —— 不同键并发合法，不能一 abort 了之。
   */
  const treeAbortRef = useRef<AbortController | null>(null);
  const dirSeqRef = useRef<Map<string, number>>(new Map());

  /** 开启一轮替换型树请求：取消上一轮，返回本轮 signal */
  const beginTreeReq = useCallback((): AbortSignal => {
    treeAbortRef.current?.abort();
    const ctl = new AbortController();
    treeAbortRef.current = ctl;
    return ctl.signal;
  }, []);

  /** 合并型请求序号闸门：同键后发者作废先发者 */
  const claimDir = useCallback((key: string): number => {
    const seq = (dirSeqRef.current.get(key) ?? 0) + 1;
    dirSeqRef.current.set(key, seq);
    return seq;
  }, []);

  const sessionId = useMemo(() => readStoredSessionId(), []);
  /** 足迹标记：共享 hook（树 / 足迹面板 / 推荐三处同源同型） */
  const { files: recentFiles, reload: reloadRecent } =
    useRecentFiles(sessionId);
  const recentSet = useMemo(
    () => new Set(recentFiles.map((f) => f.path)),
    [recentFiles]
  );

  /** 页级兜底 —— root 拉不到 → 整页 Result + 重试（不静默空页） */
  const loadRoot = useCallback(async () => {
    setRootErr(null);
    try {
      const r = await fileApi.fetchRoot();
      setProjectRoot(r.project_root);
    } catch {
      setProjectRoot('');
      // 2026-10-21 小杨 - 用户口吻（原「请检查 workspace.project_root 配置」是开发者语言）
      setRootErr('项目根目录不存在或不可访问，请检查「工作目录」设置后重试。');
    }
  }, []);

  const loadTree = useCallback(async () => {
    const signal = beginTreeReq();
    setTreeStatus({ phase: 'loading' });
    try {
      // 2026-10-21 小欧 - 首屏只取**前 3 层**（max_depth=3）：实测 E:\test_dir 全树 8.9 万节点 /
      //   19.9MB，服务端 TTFB 9.8 秒（其中 gzip level9 占 4.7s）→ 首屏白屏 10 秒。
      //   现改为：首屏取 3 层，点开更深目录时用已有的 loadDir 补拉（同样 3 层，深了再点再拉）。
      //   **后端不设任何上限**（见 browse_service 常量区红线注释）。
      const r = await fileApi.fetchTree('', { maxDepth: 3, signal });
      treeRef.current = r.nodes;
      setTree(r.nodes);
      setLoadedKeys([]);
      // 2026-10-21 小欧 - 如实告知"结果是否完整"（原先三个标志全丢，用户以为看到的是完整目录）
      setScanNotices(buildScanNotices(r));
      setTreeStatus({ phase: 'ready' });
    } catch (e) {
      // 2026-10-21 小欧 - 被新一轮请求取代/组件卸载：静默丢弃，不误报「加载失败」
      if (isSilentError(e)) return;
      setTreeStatus({ phase: 'error', message: '目录加载失败，请重试' });
    }
  }, [beginTreeReq]);

  useEffect(() => {
    void loadRoot();
  }, [loadRoot]);
  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  // 2026-10-21 小欧 - 组件卸载：取消在途树请求（否则卸载后回调仍在写 state）
  useEffect(() => () => treeAbortRef.current?.abort(), []);

  /** 深链定位：读 ?path=（逐级补拉）+ &line=（交 FilePreview 高亮） */
  const expandToPath = useCallback(
    async (rel: string): Promise<FileNode | null> => {
      // 2026-10-21 小杨 - 工具可能给 Windows 反斜杠或 ./ 前缀；树 key 是 posix，
      //   不归一化会 100% 找不到目标 — 小杨-2026-10-21
      const targetKey = rel
        .replace(/\\/g, '/')
        .replace(/^\.\/+/, '')
        .replace(/\/+/g, '/');
      const segs = targetKey.split('/').filter(Boolean);
      const dirKeys: string[] = [];
      let cur = '';
      for (const s of segs) {
        cur = cur ? `${cur}/${s}` : s;
        let hit = findNode(treeRef.current, cur);
        if (!hit) return null; // 路径不存在 → 调用方给明确提示（失败分支不静默）
        if (hit.type === 'dir' && !hit.children) {
          // 2026-10-21 小欧 - 合并型请求：同键后发者作废先发者（不 abort，不同键并发合法）
          const seq = claimDir(cur);
          // 2026-10-21 小欧 - 补拉也只取 3 层（点开目录时按需补拉，深了再点再拉）
          const r = await fileApi.fetchTree(cur, { maxDepth: 3 });
          if (dirSeqRef.current.get(cur) !== seq) return null; // 过期响应丢弃
          const merged = mergeKids(treeRef.current, cur, r.nodes);
          treeRef.current = merged;
          setTree(merged);
          setLoadedKeys((prev) => (prev.includes(cur) ? prev : [...prev, cur]));
          hit = findNode(treeRef.current, cur);
          if (!hit) return null;
        }
        if (hit.type === 'dir') dirKeys.push(cur);
      }
      const target = findNode(treeRef.current, targetKey);
      if (!target) return null;
      // 2026-10-21 小杨 - 修复：展开集合由本页唯一持有（原先树内还有一份
      //   互不相通的 expanded state → 深链/定位只改页面 state，树纹丝不动）。
      //   用函数式追加，不依赖闭包里的旧 expandedKeys。
      setExpandedKeys((prev) => {
        const add = dirKeys.filter((k) => !prev.includes(k));
        return add.length > 0 ? [...prev, ...add] : prev;
      });
      return target;
    },
    [claimDir]
  );

  /**
   * 统一的"打开一个路径"入口（2026-10-21 小杨 - 收口改造）
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
      // 2026-10-22 小欧 - 滚动定位改信号式（reveal state → FilesTree 提交后 effect 自滚）：
      //   原单次 rAF 与 React 提交存在竞态（rAF 先跑时行未挂载 → querySelector 为 null 静默跳过，
      //   实测 5 次仅 1 次成功）；effect 在提交后必然执行，行必然存在，竞态消除 — 小欧-2026-10-22
      setReveal((prev) => ({ key: hit.key, n: (prev?.n ?? 0) + 1 }));
      if (hit.type === 'dir') {
        // 目录：只展开定位（左侧树已展开到该目录），右侧保持上一份内容
        // 2026-10-21 小杨 - 修复：原实现顺手清空预览，用户定位目录时正在读的文件被无端关掉
        return true;
      }
      setSelected(hit);
      setLineRange(line ?? null);
      // 2026-10-22 小欧 - 窄屏切预览 Tab（与树点击 onSelectFile 对齐）：否则深链/定位框
      //   打开文件后仍停在"文件"Tab，用户以为没反应 — 小欧-2026-10-22
      if (isNarrow) setNarrowTab('preview');
      return true;
    },
    [expandToPath, isNarrow]
  );

  /** 深链进入：?path=…&line=… */
  useEffect(() => {
    // 2026-10-21 小杨 - 先归一反斜杠，避免 Windows 路径深链在 expandToPath 断链
    const rel = params.get('path')?.replace(/\\/g, '/');
    // 2026-10-21 小杨 - 修复（阻断）：原 effect 在**树未就绪**时就跑
    //   （loadTree 是 void 发起，同步段只走到第一个 await → treeRef.current 仍是 []）
    //   → findNode 恒 null → 深链 100% 失效（预览空白、树不定位、无任何提示）。
    //   现在等 treeReady 后再展开。
    if (!rel || !treeReady) return;
    void (async () => {
      const line = params.get('line');
      // 2026-10-22 小杨 - 行号深链既支持"起-止"也支持单行"10"：
      //   只认区间时，用户手敲 ?line=10 会被静默忽略（点了没反应）— 小杨-2026-10-22
      const m = line ? /^(\d+)(?:-(\d+))?$/.exec(line) : null;
      const ok = await openPath(
        rel,
        m
          ? { start: Number(m[1]), end: m[2] ? Number(m[2]) : Number(m[1]) }
          : null
      );
      if (!ok) {
        // 页内留痕（不只弹一下 toast）：否则用户以为"点了没反应"
        setLinkErr(`未找到「${rel}」，请检查路径或从左侧树中选择`);
      } else {
        setLinkErr(null);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, treeReady]);

  /**
   * J3：把目录设为当前会话的工作目录（Agent 产物落点）。
   *
   * 两条后端契约约束：PATCH 是全量覆盖（须先读后写）；路径必须绝对（后端硬拒相对路径）。
   * 422 的 workspace_rejected 逐条如实呈现。
   */
  const setWorkspace = useCallback(
    async (dir: FileNode) => {
      if (!sessionId) {
        showMessage(
          ErrorType.WARNING,
          '尚无会话：请先在对话页发起一次对话，再设置会话工作目录。'
        );
        return;
      }
      const abs = toAbsolutePath(dir.key, projectRoot);
      if (!abs) {
        showMessage(ErrorType.WARNING, '该路径无法定位到项目根，未设置。');
        return;
      }
      try {
        const cur = await sessionApi.getWorkspaces(sessionId);
        const paths = cur.workspaces.map((w) => w.path);
        if (paths.some((p) => samePath(p, abs))) {
          showSuccess(`「${dir.name}」已是会话工作目录`);
          return;
        }
        await sessionApi.patchWorkspaces(sessionId, [...paths, abs]);
        showSuccess(`已设为会话工作目录：${dir.name}`);
      } catch (e: unknown) {
        // 422 信封：{success:false, error:{workspace_rejected:[{path,reason}]}}（全局异常处理器包装）
        const rejected =
          (
            e as {
              response?: {
                data?: { error?: { workspace_rejected?: unknown } };
              };
            }
          )?.response?.data?.error?.workspace_rejected ?? [];
        const items = rejected as { path: string; reason: string }[];
        if (items.length) {
          items.forEach((x) =>
            showMessage(ErrorType.WORKSPACE_REJECTED, `${x.path}：${x.reason}`)
          );
        } else {
          throw e; // 非 422 业务错交全局 handler
        }
      }
    },
    [projectRoot, sessionId]
  );

  /**
   * 三途径统一 push（引用到对话 / 树右键引用 / 引用选区 —— 产物等价）
   *
   * 2026-10-21 小杨 - 设计模型变更（就地收集）：
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

  /** 引用所选（批量）：逐个读正文 → 就地收集；全部成功才清空勾选 */
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
      // 2026-10-21 小欧 - 合并型请求：同键后发者作废先发者（不同键并发合法，不能一 abort 了之）
      const seq = claimDir(key);
      try {
        // 2026-10-21 小杨 - 补拉**到 3 层**（首屏 5 秒开；再深一层由用户点开再拉）
        const r = await fileApi.fetchTree(key, { maxDepth: 3 });
        if (dirSeqRef.current.get(key) !== seq) return null; // 过期响应丢弃
        return r.nodes;
      } catch {
        return null;
      }
    },
    [claimDir]
  );

  const patchNodes = useCallback((parentKey: string, kids: FileNode[]) => {
    const merged = mergeKids(treeRef.current, parentKey, kids);
    treeRef.current = merged;
    setTree(merged);
  }, []);

  /** 工具条刷新：树 + 足迹 + 预览共用一次点击 */
  const refreshAll = useCallback(() => {
    void loadTree();
    void reloadRecent();
    refreshPreviewRef.current?.();
  }, [loadTree, reloadRecent]);

  /**
   * 树 / 预览两个**内容单元**（2026-10-21 小杨 - 单一真源）
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
        flexDirection: 'column',
        alignItems: 'center',
        gap: Spacing.SM,
        padding: Spacing.LG,
        color: Colors.TEXT.SECONDARY,
      }}
    >
      <Spin />
      <span>正在加载目录…</span>
    </div>
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {/* 2026-10-21 小欧 - 扫描不完整提示（结果不全必须让用户看见，不能静默给残缺目录）；
            2026-10-21 小欧 - 按要求**拼接成一行**显示（原先每段各占一行） */}
        {scanNotices.length > 0 && (
          <div
            role="status"
            style={{
              fontSize: chatTokens.fontSM,
              color: Colors.WARNING,
              lineHeight: 1.5,
              whiteSpace: 'normal',
              wordBreak: 'break-word',
              padding: `0 ${Spacing.SM}px ${Spacing.XS}px`,
            }}
          >
            {scanNotices.join('')}
          </div>
        )}
        <FilesTree
          nodes={tree}
          activeKey={selected?.key ?? ''}
          reveal={reveal}
          checkedKeys={multiFiles.map((n) => n.key)}
          recentSet={recentSet}
          expandedKeys={expandedKeys}
          onExpandedKeys={setExpandedKeys}
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
          onSetWorkspace={(d) => {
            void setWorkspace(d);
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
        onSendFile={(content, node, size) =>
          pushRef('file', node.name, node.key, content, size)
        }
        onSendSelection={(content, node, range, size) =>
          pushRef(
            'selection',
            `${node.name} L${range.start}-${range.end}`,
            node.key,
            content,
            size,
            range
          )
        }
      />
    );

  if (rootErr) {
    return (
      <ConfigProvider theme={PAGE_THEME}>
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
    <ConfigProvider theme={PAGE_THEME}>
      <div
        style={{
          padding: Spacing.MD,
          // 2026-10-21 小杨 - 根改为**flex column + 撑满视口**
          //   原中间区 height:calc(100vh-140px) 是手算 —— 收集条一出现就溢出视口 40px。
          //   现在：工具条/收集条 flexShrink:0，中间区 flex:1 → 多一条内容，树/预览自动让位。
          display: 'flex',
          flexDirection: 'column',
          // 2026-10-21 小杨 - 底部空白修复：calc(100vh-100px) 的 100 是拍脑袋
          //   （真实 chrome=Header43+Content padding10≈53px），改 height:100% 由
          //   Layout Content(flex:1+minHeight:0) 给准高度，贴合到底不空截。
          height: '100%',
          // 2026-10-21 小杨 - 修复：height:100% + padding 在 content-box 下多出
          //   上下各 8px，整页比可用高度高 16px（底部被裁）；border-box 让 padding 计入高度
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
      >
        {/* 工具条 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap', // 2026-10-21 小杨 - 6 元素一行，1280 以下换行而非溢出
            gap: Spacing.SM,
            marginBottom: Spacing.MD,
            flexShrink: 0,
          }}
        >
          {/* 2026-10-21 小杨 - 工具条重排：
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
              // 2026-10-21 小杨 - **不显示 UUID 前 8 位**（不可辨识，等于没有信息）
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
          {/* 2026-10-21 小杨 - 手势提示**常驻**（勾选前也要看得见）
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
          <LocateBox onLocate={openPath} />
          <Button onClick={refreshAll} title="重新加载目录与足迹">
            重新加载
          </Button>
        </div>

        {/* 2026-10-21 小杨 - 就地收集：收集条常驻显示"已引用多少 + 何时送走"
          —— 引用不再立刻跳页，用户需要一个明确的"我攒了几个、去哪送"的落点。 */}
        {collectedKeys.length > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.SM,
              marginBottom: Spacing.SM,
              padding: `${Spacing.XS}px ${Spacing.MD}px`,
              flexShrink: 0, // 2026-10-21 小杨 - flex 根布局下不被压缩
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

        {linkErr && (
          <Alert
            type="warning"
            showIcon
            message={linkErr}
            style={{ marginBottom: Spacing.SM }}
            action={
              <Button size="small" onClick={() => setLinkErr(null)}>
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
          <SplitPane left={treePane} right={previewPane} />
        )}
      </div>
    </ConfigProvider>
  );
};

export default FilesPage;
