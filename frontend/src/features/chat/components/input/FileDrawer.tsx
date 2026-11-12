// 编辑历史: 2026-11-07 小欧 - 新建: 统一文件抽屉 —— 唯一「附件」入口面板, 左栏选来源、右栏点行即加入本轮 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 「我的电脑」改自研浏览器(常用位置/盘符/路径栏/目录列表/授权确认) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 新增 最近用过/已收藏/AI 生成 三栏 + 统一 FileRow + 预览抽屉; ☆ 1 击收藏/取消收藏/
//   删除 409 二次确认/清空最近/分页加载更多/键盘 ↑↓ Space Backspace — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 整改 —— 树 loading 收口独立指标/列表失败不再假空(errScopes+重试)/键盘不劫持
//   BUTTON 的 Space/Enter/busy 丢选择改提示/feed ensureSid 取凭据/跨会话行不开放预览/色值令牌化 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - 项目文件栏右栏标题补【项目根目录】(tree 响应同源 project_root, 不加新请求),
//   与「我的电脑 · hostLabel」一致列明来源地（「来自」文案为用户手改, 保留） — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - 用户定名: 「我的电脑」→「后端电脑」（栏标签/右栏标题/两处说明文案）,
//   消除"客户端还是服务端"歧义; hostLabel 同步展示后端主机名便于核对 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - 左栏标签对准: 「AI 生成」→「任务产物」(nav/SCOPE_FROM/右栏标题/空态文案),
//   session 空态文案明示口径; 后端 session 作用域同步排除溯源行消双栏重叠 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - 后端电脑栏两处「本机文件」→「后端电脑文件」(跨机空态/同机模式说明),
//   消最后两处归属歧义文案 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-10 小欧 - 抽屉顶部新增静态说明: 预先告知支持类型与大小上限、其余类型会被拒绝, 与后端白名单口径一致 — 小欧-2026-11-10
// 编辑历史: 2026-11-10 小欧 - 排版重设计: 顶部常驻文字改标题旁帮助图标(Tooltip), 规则文案上移 ATTACHMENT_RULES 单一真源 — 小欧-2026-11-10
// 编辑历史: 2026-11-10 小欧 - 合集限额接入: 打开时拉取后端 limits 并下发表单(入口置灰), 左栏显示合集数/条目数配额;
//   条目 meta 补引用身份, 右栏标题带上合集用途备注 — 小欧-2026-11-10
// 编辑历史: 2026-11-11 小欧 - 接入 capabilities(accept 白名单/setMaxRefs) + 列表行传 kind(图标按类型) — 小欧-2026-11-11
// 编辑历史: 2026-11-11 小欧 - 列表行补能力徽标(ref_capability_map 只读索引) + 抽取态回显(metaOf)
//   + text/richdoc 真抽取手动重跑(行菜单「重新抽取」) — 小欧-2026-11-11
/**
 * FileDrawer —— 「附件」唯一面板（一个动作：把文件放进本轮；一个仓库：合集）
 *
 * 左栏来源：
 * - 最近用过：resolver 注入过（use_count>0），跨会话共享
 * - 本会话：本会话已提交的附件
 * - 项目文件：项目根文件树（/files/tree）
 * - 我的电脑（后端电脑）：自研浏览器（/fs/drives + /files/external/tree），仅同机，读的是后端进程所在机器的盘
 * - 任务产物（scope=ai）：产物「存为附件」的溯源行（按来源任务），与「本会话」栏互不重叠
 * - 收藏：scope='global'（★ 星标）+ 合集表
 *
 * 交互：点整行 = 加入/移出本轮；文件名 = 预览；☆ = 收藏（1 击）；⋯ = 重命名/删除。
 * 入队唯一实现：附件 enqueue / 文件 quoteFile / 同机 importLocal（内部 enqueue）。
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd';
import type { MenuProps, UploadProps } from 'antd';
import {
  ArrowUpOutlined,
  FolderOpenOutlined,
  FolderOutlined,
  InfoCircleOutlined,
  MoreOutlined,
  UploadOutlined,
} from '@ant-design/icons';

import {
  attachmentApi,
  type AttachmentCapabilities,
  type AttachmentRecord,
} from '@/services/api/attachment.api';
import {
  materialPackApi,
  type MaterialPack,
  type MaterialPackItem,
  type MaterialPackLimits,
} from '@/services/api/materialPack.api';
import {
  fileApi,
  type FileNode,
  type SearchHit,
} from '@/services/api/file.api';
import {
  fsApi,
  type AuthDir,
  type FsDrive,
  type QuickPath,
} from '@/services/api/fs.api';
import {
  enqueue,
  uploadAttachments,
  MAX_BATCH,
  ATTACHMENT_RULES,
} from '@/features/refs/uploadAttachment';
import { quoteFile } from '@/features/refs/quote';
import { getLocalCapability, importLocal } from '@/features/refs/localImport';
import { refLimitText, setMaxRefs, type ComposerRef } from '@/features/refs/store';
import {
  showMessage,
  showSuccess,
  handleApiError,
  errorCodeOf,
  ErrorType,
} from '@/services/error/handler';
import { formatBytes } from '@/utils/format';
import { formatRelativeTime } from '@/utils/time';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { FileRow, type FileRowProps } from './FileRow';
// 2026-11-11 小欧 - 行内能力徽标(ref_capability_map 只读索引) — 小欧-2026-11-11
import {
  chipCapState,
  useRefCapabilityMap,
} from '@/features/chat/hooks/useRefCapabilityMap';
import { PreviewDrawer } from './PreviewDrawer';
import { MaterialPackSaveForm } from './MaterialPackSaveForm';

/** 左栏来源 + 合集仓库 */
type SourceKey =
  | 'recent'
  | 'session'
  | 'project'
  | 'local'
  | 'ai'
  | 'fav'
  | 'pack';

/** 附件作用域（后端 list scope 同名） */
type ScopeKey = 'session' | 'recent' | 'global' | 'ai';

const SCOPES: ScopeKey[] = ['session', 'recent', 'global', 'ai'];
/** 单页条数（后端上限 200） */
const PAGE = 50;

const NAV: Array<{ key: SourceKey; label: string }> = [
  { key: 'recent', label: '最近用过' },
  { key: 'session', label: '本会话' },
  { key: 'project', label: '项目文件' },
  { key: 'local', label: '后端电脑' },
  { key: 'ai', label: '任务产物' },
];

const SCOPE_FROM: Record<ScopeKey, string> = {
  session: '本会话',
  recent: '最近用过',
  global: '已收藏',
  ai: '任务产物',
};

/** 项目根文件树拍平为文件列表（目录只用于展开，不占行） */
function flattenFiles(nodes: FileNode[], out: FileNode[] = []): FileNode[] {
  for (const n of nodes) {
    if (n.type === 'file') out.push(n);
    else if (n.children) flattenFiles(n.children, out);
  }
  return out;
}

/** 目录绝对路径 + 相对 posix key → 绝对路径（Windows 分隔符） */
function joinAbs(dir: string, key: string): string {
  const base = dir.replace(/[\\/]+$/, '');
  return base ? `${base}\\${key.split('/').join('\\')}` : key;
}

/** 归一化目录路径：盘符根保留反斜杠，其余去掉尾部反斜杠 */
function normalizeDir(raw: string): string {
  const t = raw.trim();
  if (/^[A-Za-z]:[\\/]?$/.test(t)) return `${t.slice(0, 2)}\\`;
  return t.replace(/[\\/]+$/, '');
}

/** 上一级目录（盘符根保持不变） */
function parentOf(path: string): string {
  const t = normalizeDir(path);
  if (/^[A-Za-z]:\\$/.test(t)) return t;
  const i = t.lastIndexOf('\\');
  return i <= 2 ? `${t.slice(0, 2)}\\` : t.slice(0, i);
}

/** 目录优先 + 名称排序（资源管理器习惯） */
function sortEntries(nodes: FileNode[]): FileNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
    return a.name.localeCompare(b.name, 'zh-CN');
  });
}

/** 次行「类型」标签：优先扩展名，其次 mime 大类 */
function typeLabel(mime: string, name: string): string {
  const ext = (name.split('.').pop() || '').toUpperCase();
  if (mime === 'application/pdf') return 'PDF';
  if (mime.startsWith('image/')) return ext || '图片';
  if (mime.startsWith('video/')) return ext || '视频';
  if (mime.startsWith('text/') || mime.includes('json')) return ext || '文本';
  return ext || '文件';
}

/** 列表行次行：类型 · 大小 · 来源 · 相对时间 · 抽取态(text/richdoc 真抽取回显) */
function metaOf(rec: AttachmentRecord, from: string): string {
  const parts = [
    typeLabel(rec.mime, rec.original_name),
    formatBytes(rec.size),
    from,
    formatRelativeTime(rec.last_used_at ?? rec.created_at),
  ];
  // 2026-11-11 小欧 - 真抽取态回显: ok=字数, failed=标注失败(重试在行菜单) — 小欧-2026-11-11
  if (rec.kind === 'text' || rec.kind === 'richdoc') {
    if (rec.extract_status === 'ok') parts.push(`已抽取 ${rec.extract_chars} 字`);
    else if (rec.extract_status === 'failed') parts.push('抽取失败');
  }
  return parts.join(' · ');
}

/** RowSpec = FileRow 的全部入参（active/rowRef 由列表层注入）+ key */
type RowSpec = Omit<FileRowProps, 'active' | 'rowRef'> & { key: string };

const metaStyle: React.CSSProperties = {
  fontSize: FontSize.CAPTION,
  color: Colors.TEXT.SECONDARY,
};

const nameStyle: React.CSSProperties = {
  fontSize: FontSize.PRIMARY,
  color: Colors.TEXT.STRONG,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

interface FileDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 当前会话 ID；为空表示新会话（选中文件后才建会话） */
  sessionId?: string | null;
  /** D1 唯一实现：无会话时创建并回填，返回新 sessionId；失败返回 null */
  ensureSession?: () => Promise<string | null>;
  /** 本轮文件（「已加入」判定 + 底部计数） */
  refs: ComposerRef[];
  /** 按 chip id 移出本轮（抽屉内点已行 = 取消加入） */
  onRemoveRef?: (refId: string) => void;
  disabled?: boolean;
}

const emptyTextOf = (scope: ScopeKey, hasSession: boolean): string => {
  if (scope === 'session') {
    return hasSession
      ? '本会话还没有附件；上传或导入的文件会列在这里'
      : '还没有会话，先上传或加入一个文件';
  }
  if (scope === 'recent') return '还没有用过文件；加入并发送一次就会出现在这里';
  if (scope === 'global') return '还没有收藏；点行尾 ☆ 即可跨会话保留';
  return '还没有任务产物；把 AI 产物「存为附件」后会列在这里';
};

const FileDrawer: React.FC<FileDrawerProps> = ({
  open,
  onClose,
  sessionId,
  ensureSession,
  refs,
  onRemoveRef,
  disabled = false,
}) => {
  const [source, setSource] = useState<SourceKey>('recent');
  const [keyword, setKeyword] = useState('');
  /** 项目树加载（独立状态, 不再与合集加载互踩清 spinner — 2026-11-07） */
  const [treeLoading, setTreeLoading] = useState(false);
  const [lists, setLists] = useState<Record<ScopeKey, AttachmentRecord[]>>({
    session: [],
    recent: [],
    global: [],
    ai: [],
  });
  const listsRef = useRef(lists);
  const [hasMore, setHasMore] = useState<Record<ScopeKey, boolean>>({
    session: false,
    recent: false,
    global: false,
    ai: false,
  });
  const [scopeLoading, setScopeLoading] = useState<ScopeKey | null>(null);
  /** 各作用域列表失败标记（非阻断：空态改「加载失败+重试」，不再与真空态难辨 — 2026-11-07） */
  const [errScopes, setErrScopes] = useState<
    Partial<Record<ScopeKey, boolean>>
  >({});
  const [activeIndex, setActiveIndex] = useState(-1);
  const [preview, setPreview] = useState<AttachmentRecord | null>(null);
  const [renamingAtt, setRenamingAtt] = useState<AttachmentRecord | null>(null);
  const [attNameValue, setAttNameValue] = useState('');
  const [projectFiles, setProjectFiles] = useState<FileNode[]>([]);
  /** 项目根绝对路径(tree 响应同源下发), 右栏标题【】展示来源地 */
  const [projectRoot, setProjectRoot] = useState('');
  const [packs, setPacks] = useState<MaterialPack[]>([]);
  const [activePack, setActivePack] = useState<MaterialPack | null>(null);
  const [canLocal, setCanLocal] = useState(false);
  const [hostLabel, setHostLabel] = useState<string | null>(null);
  const [drives, setDrives] = useState<FsDrive[]>([]);
  const [quick, setQuick] = useState<QuickPath[]>([]);
  const [authDirs, setAuthDirs] = useState<AuthDir[]>([]);
  /** 当前浏览目录（盘符绝对路径）；空串 = 尚未选择位置 */
  const [cwd, setCwd] = useState('');
  const [pathDraft, setPathDraft] = useState('');
  const [entries, setEntries] = useState<FileNode[]>([]);
  const [localLoading, setLocalLoading] = useState(false);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState(false);
  const [feedBusy, setFeedBusy] = useState(false);
  const [renamingPack, setRenamingPack] = useState<MaterialPack | null>(null);
  const [packNameValue, setPackNameValue] = useState('');
  /** 合集限额(后端 get_limits 单一真源), 用于入口置灰与计数展示 */
  const [packLimits, setPackLimits] = useState<MaterialPackLimits | null>(null);
  const rowsRef = useRef<RowSpec[]>([]);
  const activeElRef = useRef<HTMLDivElement | null>(null);
  // 上传白名单/上限唯一出口(后端 capabilities); 打开抽屉时刷新一次 — 小欧-2026-11-11
  const [caps, setCaps] = useState<AttachmentCapabilities | null>(null);
  useEffect(() => {
    if (!open) return;
    let alive = true;
    void attachmentApi
      .capabilities()
      .then((c) => {
        if (!alive) return;
        setCaps(c);
        setMaxRefs(c.limits.max_refs);
      })
      .catch(() => void 0);
    return () => {
      alive = false;
    };
  }, [open]);

  // 上传批量收集（与 AttachmentArea 原实现同口径：antd beforeUpload 逐文件回调 + 末个触发）
  const [busy, setBusy] = useState(0);
  const busyRef = useRef(0);
  const pendingFiles = useRef<File[]>([]);

  /** 写回某一作用域（append=在已加载尾部追加） */
  const applyScope = useCallback(
    (
      scope: ScopeKey,
      items: AttachmentRecord[],
      append: boolean,
      more: boolean
    ): void => {
      const next = append ? [...listsRef.current[scope], ...items] : items;
      listsRef.current = { ...listsRef.current, [scope]: next };
      setLists(listsRef.current);
      setHasMore((prev) => ({ ...prev, [scope]: more }));
    },
    []
  );

  /** 拉取一个作用域（offset 取已加载条数，单一真源 listsRef） */
  const loadScope = useCallback(
    async (scope: ScopeKey, append = false): Promise<void> => {
      if (scope === 'session' && !sessionId) {
        applyScope('session', [], false, false);
        return;
      }
      setScopeLoading(scope);
      try {
        const offset = append ? listsRef.current[scope].length : 0;
        const items = await attachmentApi.list(sessionId, {
          scope,
          limit: PAGE,
          offset,
        });
        setErrScopes((prev) => ({ ...prev, [scope]: false }));
        applyScope(scope, items, append, items.length >= PAGE);
      } catch (e) {
        // 失败不清旧列表也不造假空态：标 err 让空态改「加载失败+重试」（2026-11-07）
        setErrScopes((prev) => ({ ...prev, [scope]: true }));
        void e;
      } finally {
        setScopeLoading((prev) => (prev === scope ? null : prev));
      }
    },
    [sessionId, applyScope]
  );

  /** 四个作用域全刷（收藏/删除/上传后保持各处标记一致） */
  const refreshAll = useCallback(async (): Promise<void> => {
    await Promise.all(SCOPES.map((s) => loadScope(s)));
  }, [loadScope]);

  const reloadProject = useCallback(async (): Promise<void> => {
    setTreeLoading(true);
    try {
      const res = await fileApi.fetchTree('', { maxDepth: 2 });
      setProjectRoot(res.project_root ?? '');
      setProjectFiles(flattenFiles(res.nodes).slice(0, 300));
    } catch {
      setProjectRoot('');
      setProjectFiles([]);
    } finally {
      setTreeLoading(false);
    }
  }, []);

  const reloadPacks = useCallback(async (): Promise<void> => {
    try {
      setPacks(await materialPackApi.list());
    } catch {
      /* 全局错误处理器已提示 */
    }
  }, []);

  /** 删除/取消收藏后全刷：合集被 force 摘掉条目，左栏计数必须同步（否则残留旧数） */
  const refreshAfterWrite = useCallback(async (): Promise<void> => {
    await Promise.all([refreshAll(), reloadPacks()]);
  }, [refreshAll, reloadPacks]);
  // 2026-11-11 小欧 - 行内能力徽标数据源 + 真抽取手动重跑(text/richdoc) — 小欧-2026-11-11
  const capMap = useRefCapabilityMap(sessionId);
  const retryExtract = useCallback(
    async (rec: AttachmentRecord) => {
      if (!sessionId) return;
      try {
        await attachmentApi.reextract(rec.id, sessionId);
        await refreshAll();
      } catch {
        /* 重试失败保持原抽取态, 不打断抽屉 */
      }
    },
    [sessionId, refreshAll]
  );

  // 打开才拉：抽屉外不做任何预取（合集列表一并在开时拉，否则左栏先显示「暂无合集」）
  useEffect(() => {
    if (!open) return;
    void getLocalCapability().then(setCanLocal);
    void refreshAll();
    void reloadPacks();
    void materialPackApi
      .limits()
      .then(setPackLimits)
      .catch(() => {
        /* 限额加载失败不阻断抽屉使用, 后端仍会校验 */
      });
  }, [open, refreshAll, reloadPacks]);

  useEffect(() => {
    if (!open) return;
    if (source === 'project') void reloadProject();
  }, [open, source, reloadProject]);

  // 「我的电脑」首屏：常用位置 + 磁盘 + 已授权目录
  useEffect(() => {
    if (!open || source !== 'local' || !canLocal) return;
    let alive = true;
    void fsApi
      .drives()
      .then((r) => {
        if (!alive) return;
        setHostLabel(r.host_label);
        setDrives(r.drives);
        setQuick(r.quick);
      })
      .catch(() => {
        if (alive) setDrives([]);
      });
    void fsApi
      .listAuthorized()
      .then((dirs) => {
        if (alive) setAuthDirs(dirs);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [open, source, canLocal]);

  // 列当前目录（单层，不递归；深层由用户逐级进入）
  useEffect(() => {
    if (!open || source !== 'local' || !canLocal || !cwd) return;
    let alive = true;
    setLocalLoading(true);
    fileApi
      .fetchExternalTree(cwd, { maxDepth: 1 })
      .then((res) => {
        if (alive) setEntries(sortEntries(res.nodes ?? []));
      })
      .catch(() => {
        if (!alive) return;
        setEntries([]);
        showMessage(ErrorType.WARNING, `无法打开「${cwd}」，请检查路径或权限`);
      })
      .finally(() => {
        if (alive) setLocalLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, source, canLocal, cwd]);

  // 搜索当前目录（防抖 300ms，后端 /files/search?root=）
  useEffect(() => {
    if (!open || source !== 'local' || !cwd) return;
    const kw = keyword.trim();
    if (!kw) {
      setHits([]);
      setSearching(false);
      return;
    }
    let alive = true;
    setSearching(true);
    const timer = window.setTimeout(() => {
      fileApi
        .searchFiles(kw, { limit: 100, root: cwd })
        .then((r) => {
          if (alive) setHits(r.results);
        })
        .catch(() => {
          if (alive) setHits([]);
        })
        .finally(() => {
          if (alive) setSearching(false);
        });
    }, 300);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [open, source, cwd, keyword]);

  const totalSize = useMemo(
    () => refs.reduce((sum, r) => sum + (r.size ?? 0), 0),
    [refs]
  );

  /** 本轮已加入的附件 id */
  const addedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const r of refs) {
      if (r.kind === 'attachment' && r.attachment_id) ids.add(r.attachment_id);
    }
    return ids;
  }, [refs]);

  /** 本轮已加入附件的 sha（跨会话/收藏行同一文件不同 id 也判已加入） */
  const addedShas = useMemo(() => {
    const shas = new Set<string>();
    for (const scope of SCOPES) {
      for (const rec of lists[scope]) {
        if (addedIds.has(rec.id)) shas.add(rec.sha256);
      }
    }
    return shas;
  }, [lists, addedIds]);

  const isAdded = useCallback(
    (rec: AttachmentRecord): boolean =>
      addedIds.has(rec.id) || addedShas.has(rec.sha256),
    [addedIds, addedShas]
  );

  /** 本机已导入的源路径（附件记录 source_path）——「我的电脑」行的「已加入」判定 */
  const addedLocal = useMemo(() => {
    return new Set(
      lists.session
        .filter((f) => f.source_path && addedIds.has(f.id))
        .map((f) => f.source_path as string)
    );
  }, [lists.session, addedIds]);

  /** 移出本轮：按附件 id + 同 sha 兄弟行一并摘掉 */
  const removeRefsFor = useCallback(
    (rec: AttachmentRecord): void => {
      if (!onRemoveRef) return;
      const ids = new Set<string>([rec.id]);
      for (const scope of SCOPES) {
        for (const r of listsRef.current[scope]) {
          if (r.sha256 === rec.sha256) ids.add(r.id);
        }
      }
      for (const r of refs) {
        if (
          r.kind === 'attachment' &&
          r.attachment_id &&
          ids.has(r.attachment_id)
        ) {
          onRemoveRef(r.id);
        }
      }
    },
    [onRemoveRef, refs]
  );

  /** 行点击：已加入则移出，否则入队（唯一入队口 enqueue） */
  const toggleAttachment = useCallback(
    (rec: AttachmentRecord): void => {
      if (!rec.available) {
        showMessage(ErrorType.WARNING, '源文件已不存在，无法加入本轮');
        return;
      }
      if (isAdded(rec)) {
        removeRefsFor(rec);
        return;
      }
      if (!enqueue(rec)) showMessage(ErrorType.WARNING, refLimitText());
    },
    [isAdded, removeRefsFor]
  );

  /** 取消收藏：删全局行（被合集引用时 409 → 二次确认 force） */
  const unpromote = useCallback(
    async (rec: AttachmentRecord, force = false): Promise<void> => {
      try {
        await attachmentApi.remove(rec.global_id ?? rec.id, sessionId, {
          purge: true,
          force,
        });
        showSuccess('已取消收藏');
        await refreshAfterWrite();
      } catch (e) {
        if (errorCodeOf(e) === 'ATTACHMENT_IN_USE' && !force) {
          Modal.confirm({
            title: '取消收藏？',
            content: '该文件仍被合集引用，取消收藏会一并移除合集里的这条记录。',
            okText: '继续',
            cancelText: '取消',
            onOk: () => unpromote(rec, true),
          });
          return;
        }
        handleApiError(e, { message: '取消收藏失败，请稍后重试' });
      }
    },
    [sessionId, refreshAfterWrite]
  );

  /** ☆ 收藏开关（1 击，无弹窗；无会话时按钮已置灰, 回调内 fail-closed 兜底——收藏必须带会话凭据） */
  const toggleStar = useCallback(
    (rec: AttachmentRecord): void => {
      if (!sessionId) return;
      if (rec.favorited) {
        void unpromote(rec);
        return;
      }
      void (async () => {
        try {
          await attachmentApi.promote(rec.id, sessionId);
          showSuccess('已收藏（跨会话可用）');
          await refreshAll();
        } catch (e) {
          handleApiError(e, { message: '收藏失败，请稍后重试' });
        }
      })();
    },
    [sessionId, unpromote, refreshAll]
  );

  /** 删除附件记录（409 被合集引用 → 二次确认 force） */
  const confirmDelete = useCallback(
    async (rec: AttachmentRecord, force = false): Promise<void> => {
      try {
        await attachmentApi.remove(rec.id, sessionId, { purge: true, force });
        removeRefsFor(rec);
        showSuccess('已删除');
        await refreshAfterWrite();
      } catch (e) {
        if (errorCodeOf(e) === 'ATTACHMENT_IN_USE' && !force) {
          Modal.confirm({
            title: `删除「${rec.original_name}」？`,
            content: '该文件仍被合集引用，确认后将一并移除合集里的这条记录。',
            okText: '删除',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: () => confirmDelete(rec, true),
          });
          return;
        }
        handleApiError(e, { message: '删除失败，请稍后重试' });
      }
    },
    [sessionId, removeRefsFor, refreshAfterWrite]
  );

  const clearRecent = useCallback(async (): Promise<void> => {
    try {
      const { cleared } = await attachmentApi.clearRecent();
      showSuccess(
        cleared ? `已清空 ${cleared} 条使用记录` : '没有可清空的记录'
      );
      await refreshAll();
    } catch {
      /* 全局错误处理器已提示 */
    }
  }, [refreshAll]);

  /** 重命名展示名（磁盘文件名不变） */
  const doRenameAtt = useCallback(async (): Promise<void> => {
    if (!renamingAtt) return;
    const name = attNameValue.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '名称不能为空');
      return;
    }
    try {
      await attachmentApi.rename(renamingAtt.id, name, sessionId);
      setRenamingAtt(null);
      showSuccess('已重命名');
      await refreshAll();
    } catch {
      /* 全局错误处理器已提示 */
    }
  }, [renamingAtt, attNameValue, sessionId, refreshAll]);

  /** 普通文件路径：已加入则摘掉，否则走 quoteFile（唯一引用入口） */
  const togglePath = useCallback(
    async (path: string, label: string): Promise<void> => {
      const existing = refs.find(
        (r) => r.path === path && r.kind !== 'attachment'
      );
      if (existing) {
        onRemoveRef?.(existing.id);
        return;
      }
      const r = await quoteFile(path, { label });
      if (!r.ok) showMessage(ErrorType.WARNING, refLimitText());
    },
    [refs, onRemoveRef]
  );

  const collectAndUpload = (): void => {
    const files = pendingFiles.current;
    pendingFiles.current = [];
    busyRef.current += files.length;
    setBusy(busyRef.current);
    void uploadAttachments(files, { sessionId, ensureSession }).then(() => {
      busyRef.current = Math.max(0, busyRef.current - files.length);
      setBusy(busyRef.current);
      if (sessionId) void refreshAll();
    });
  };

  const beforeUpload: NonNullable<UploadProps['beforeUpload']> = (
    file,
    batch
  ) => {
    // busyRef 即时生效：setBusy 到 re-render 有间隙，间隙内再次选择会混入 pendingFiles
    if (busyRef.current > 0) {
      showMessage(ErrorType.WARNING, '上传进行中，请稍候再选择');
      return Upload.LIST_IGNORE;
    }
    if (batch.length > MAX_BATCH) {
      showMessage(ErrorType.WARNING, `一次最多选择 ${MAX_BATCH} 个文件`);
      return Upload.LIST_IGNORE;
    }
    pendingFiles.current.push(file);
    if (pendingFiles.current.length === batch.length) collectAndUpload();
    return false; // 阻止 antd 自动上传（统一交 uploadAttachments）
  };

  /** 同机导入：只传路径，落盘目标由后端计算（TR-3） */
  const ensureSid = async (): Promise<string | null> =>
    sessionId || (await ensureSession?.()) || null;

  /** 授权确认：目录未授权时弹一次，授权后原样重试导入 */
  const askAuthorize = (sid: string, abs: string): void => {
    const dir = parentOf(abs);
    Modal.confirm({
      title: '需要授权读取该目录',
      content: `「${dir}」尚未授权。授权后可直接读取其中文件，也可在「已授权」里随时撤销。`,
      okText: '授权并导入',
      cancelText: '取消',
      onOk: async () => {
        try {
          setAuthDirs(await fsApi.authorize(dir));
          if ((await importLocal(sid, abs)).ok) void refreshAll();
        } catch {
          /* 受保护目录(400) 由全局错误处理器提示 */
        }
      },
    });
  };

  const openLocalFile = async (abs: string): Promise<void> => {
    if (importing) return;
    if (addedLocal.has(abs)) {
      // 已导入过：按 source_path 找到记录并移出本轮
      const rec = listsRef.current.session.find((f) => f.source_path === abs);
      if (rec) removeRefsFor(rec);
      return;
    }
    setImporting(true);
    try {
      const sid = await ensureSid();
      if (!sid) {
        showMessage(ErrorType.UNKNOWN, '会话创建失败，附件未导入');
        return;
      }
      const r = await importLocal(sid, abs);
      if (r.ok) void refreshAll();
      else if (r.code === 'LOCAL_READ_DENIED') askAuthorize(sid, abs);
    } finally {
      setImporting(false);
    }
  };

  const revokeDir = async (path: string): Promise<void> => {
    try {
      setAuthDirs(await fsApi.revoke(path));
      showSuccess(`已撤销「${path}」的读取授权（已导入的附件不受影响）`);
    } catch {
      /* 全局错误处理器已提示 */
    }
  };

  const navigate = (raw: string): void => {
    const dir = normalizeDir(raw);
    if (!dir) return;
    setPathDraft(dir);
    setCwd(dir);
  };

  /** 合集单条加入本轮（附件按 id 恢复附件语义，跨会话由后端自动 promote） */
  const feedOne = async (it: MaterialPackItem): Promise<void> => {
    if (it.kind === 'attachment' && it.attachment_id) {
      const sid = await ensureSid();
      if (!sid) return; // ensureSession 已提示建会话失败
      try {
        const rec = await attachmentApi.get(it.attachment_id, sid);
        if (!enqueue(rec)) showMessage(ErrorType.WARNING, refLimitText());
      } catch {
        showMessage(ErrorType.WARNING, `「${it.label || it.path}」已失效`);
      }
      return;
    }
    await togglePath(it.path, it.label || it.path);
  };

  /** 整组加入本轮：按条目身份分流（附件按 id 恢复附件语义） */
  const feedPack = async (pack: MaterialPack): Promise<void> => {
    const sid = await ensureSid();
    if (!sid) return; // ensureSession 已提示建会话失败
    setFeedBusy(true);
    let failed = 0;
    try {
      for (const it of pack.items) {
        if (it.kind === 'attachment' && it.attachment_id) {
          try {
            const rec = await attachmentApi.get(it.attachment_id, sid);
            if (!enqueue(rec)) failed += 1;
          } catch {
            failed += 1; // 源文件已不存在
          }
          continue;
        }
        const r = await quoteFile(it.path, { label: it.label });
        if (!r.ok) failed += 1;
      }
      if (failed === 0) {
        showSuccess(
          `已将「${pack.name}」的 ${pack.items.length} 个文件加入本轮`
        );
      } else {
        showMessage(
          ErrorType.WARNING,
          `「${pack.name}」有 ${failed} 个文件已失效，其余已加入本轮`
        );
      }
      void loadScope('global');
    } finally {
      setFeedBusy(false);
    }
  };

  const removePack = async (pack: MaterialPack): Promise<void> => {
    try {
      await materialPackApi.remove(pack.id);
      showSuccess(`已删除合集「${pack.name}」（磁盘文件不受影响）`);
      if (activePack?.id === pack.id) setActivePack(null);
      await reloadPacks();
    } catch {
      /* 全局错误处理器已提示 */
    }
  };

  const doRenamePack = async (): Promise<void> => {
    if (!renamingPack) return;
    const name = packNameValue.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '名称不能为空');
      return;
    }
    try {
      const updated = await materialPackApi.update(renamingPack.id, { name });
      showSuccess('已重命名合集');
      setRenamingPack(null);
      if (activePack?.id === updated.id) setActivePack(updated);
      await reloadPacks();
    } catch {
      /* 409 同名由全局处理器提示 */
    }
  };

  const kw = keyword.trim().toLowerCase();
  const match = (name: string): boolean =>
    !kw || name.toLowerCase().includes(kw);

  const projectShown = projectFiles.filter((f) => match(f.name));
  const packShown = (activePack?.items ?? []).filter((it) =>
    match(it.label || it.path)
  );
  /** 「我的电脑」目录行（不可加入，点进入；搜索态复用 hits 里的 dir） */
  const localDirs = (): Array<{ key: string; name: string; abs: string }> => {
    if (source !== 'local' || !canLocal || !cwd) return [];
    if (kw.length > 0) {
      return hits
        .filter((h) => h.type === 'dir' && !!h.abs)
        .map((h) => ({
          key: h.abs as string,
          name: h.name,
          abs: h.abs as string,
        }));
    }
    return entries
      .filter((n) => n.type === 'dir')
      .map((n) => ({ key: n.key, name: n.name, abs: joinAbs(cwd, n.key) }));
  };

  const navItemStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 10px',
    borderRadius: 6,
    cursor: 'pointer',
    background: active ? Colors.BG.SELECTED : 'transparent',
    borderLeft: active
      ? `2px solid ${Colors.PRIMARY}`
      : '2px solid transparent',
    color: active ? Colors.PRIMARY : Colors.TEXT.PRIMARY,
    fontSize: FontSize.PRIMARY,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  });

  /** 附件作用域的列表行（最近/本会话/已收藏/AI 共用） */
  const buildAttachRows = (scope: ScopeKey): RowSpec[] =>
    lists[scope]
      .filter((rec) => match(rec.original_name))
      .map((rec) => {
        const added = isAdded(rec);
        const canManage =
          rec.scope === 'global' || rec.session_id === sessionId;
        // 预览端点(/raw /text)已改严格只读: 跨会话 session 行不再开放预览, 须先☆成全局资产
        const canPreview =
          !!sessionId &&
          (rec.scope === 'global' || rec.session_id === sessionId);
        const moreItems: MenuProps['items'] = [];
        if (added) moreItems.push({ key: 'remove', label: '移出本轮' });
        if (canManage) {
          if (moreItems.length > 0) moreItems.push({ type: 'divider' });
          moreItems.push({ key: 'rename', label: '重命名' });
          // 2026-11-11 小欧 - 真抽取手动重跑(text/richdoc, 抽取失败/未抽取均可重试) — 小欧-2026-11-11
          if (rec.kind === 'text' || rec.kind === 'richdoc') {
            moreItems.push({ key: 'reextract', label: '重新抽取' });
          }
          moreItems.push({ key: 'delete', label: '删除', danger: true });
        }
        return {
          key: rec.id,
          name: rec.original_name,
          meta: metaOf(rec, SCOPE_FROM[scope]),
          mime: rec.mime,
          kind: rec.kind,
          // 2026-11-11 小欧 - 行内能力徽标(ref_capability_map 只读索引, 查不到不显示) — 小欧-2026-11-11
          capState: capMap
            ? chipCapState(capMap, {
                kind: 'attachment',
                path: rec.original_name,
                mime: rec.mime,
              })
            : undefined,
          added,
          favorited: rec.favorited,
          invalid: !rec.available,
          starDisabled: !sessionId,
          onToggle: () => toggleAttachment(rec),
          onPreview: canPreview ? () => setPreview(rec) : undefined,
          onStar: () => toggleStar(rec),
          moreItems,
          onMoreClick: (key: string) => {
            if (key === 'remove') removeRefsFor(rec);
            else if (key === 'rename') {
              setRenamingAtt(rec);
              setAttNameValue(rec.original_name);
            } else if (key === 'reextract') {
              void retryExtract(rec);
            } else if (key === 'delete') {
              void confirmDelete(rec);
            }
          },
        };
      });

  /** 当前右栏行（键盘导航共用同一份） */
  const buildRows = (): RowSpec[] => {
    if (source === 'project') {
      return projectShown.map((node) => {
        const added = refs.some(
          (r) => r.path === node.key && r.kind !== 'attachment'
        );
        return {
          key: node.key,
          name: node.name,
          meta: `${node.key} · ${formatBytes(node.size ?? 0)}`,
          added,
          onToggle: () => void togglePath(node.key, node.name),
        };
      });
    }
    if (source === 'pack') {
      return packShown.map((it) => {
        const added =
          it.kind === 'attachment'
            ? refs.some((r) => r.attachment_id === it.attachment_id)
            : refs.some((r) => r.path === it.path && r.kind !== 'attachment');
        return {
          key: `${it.seq}-${it.path}`,
          name: it.label || it.path,
          meta: `${it.kind === 'attachment' ? '附件' : '文件'} · ${it.path}`,
          added,
          onToggle: () => void feedOne(it),
        };
      });
    }
    if (source === 'local') {
      if (!canLocal) return [];
      if (kw.length > 0) {
        return hits
          .filter((h) => h.type !== 'dir')
          .map((h) => ({
            key: h.abs ?? h.path,
            name: h.name,
            meta: h.abs ?? h.path,
            added: !!h.abs && addedLocal.has(h.abs),
            onToggle: () => {
              if (h.abs) void openLocalFile(h.abs);
            },
          }));
      }
      return entries
        .filter((n) => n.type !== 'dir')
        .map((n) => {
          const abs = joinAbs(cwd, n.key);
          return {
            key: n.key,
            name: n.name,
            meta: abs,
            added: addedLocal.has(abs),
            onToggle: () => void openLocalFile(abs),
          };
        });
    }
    const scope: ScopeKey = source === 'fav' ? 'global' : source;
    return buildAttachRows(scope);
  };

  const rows = buildRows();
  rowsRef.current = rows;
  const localDirRows = localDirs();
  /** 合集数达上限：入口置灰(上限未加载时不预判, 后端兜底校验) */
  const atPackLimit =
    packLimits !== null && packs.length >= packLimits.max_packs;

  const currentScope: ScopeKey | null =
    source === 'project' || source === 'local' || source === 'pack'
      ? null
      : source === 'fav'
        ? 'global'
        : source;

  // 键盘：↑↓ 移动焦点、Space 加入/移出、Enter 预览、Backspace 移出
  useEffect(() => {
    if (!open || preview) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === 'INPUT' ||
          t.tagName === 'TEXTAREA' ||
          t.isContentEditable ||
          // 焦点在按钮/链接上时让控件自己响应 Space/Enter, 键盘不劫持(2026-11-07)
          (t.closest('button, a') as HTMLElement | null) !== null)
      ) {
        return;
      }
      const list = rowsRef.current;
      if (list.length === 0) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => {
          if (e.key === 'ArrowDown') return Math.min(list.length - 1, i + 1);
          return i < 0 ? list.length - 1 : Math.max(0, i - 1);
        });
        return;
      }
      if (activeIndex < 0 || activeIndex >= list.length) return;
      const row = list[activeIndex];
      if (e.key === ' ') {
        e.preventDefault();
        row.onToggle();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        row.onPreview?.();
      } else if (e.key === 'Backspace' && row.added) {
        e.preventDefault();
        row.onToggle();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, preview, activeIndex]);

  // 高亮行滚入可视区
  useEffect(() => {
    if (activeIndex < 0) return;
    activeElRef.current?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const renderList = (list: RowSpec[]): React.ReactNode =>
    list.map((spec, i) => {
      const { key, ...rest } = spec;
      return (
        <FileRow
          key={key}
          {...rest}
          active={i === activeIndex}
          rowRef={
            i === activeIndex
              ? (el) => {
                  activeElRef.current = el;
                }
              : undefined
          }
        />
      );
    });

  const renderRows = (): React.ReactNode => {
    if (source === 'local' && !canLocal) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="当前为远程访问，无法直接读取后端电脑文件，请用上方「上传文件」"
        />
      );
    }
    if (source === 'local' && !cwd) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="选择上方位置或输入路径开始浏览"
        />
      );
    }
    if (source === 'project' && treeLoading)
      return <Spin style={{ marginTop: Spacing.MD }} />;
    if (source === 'local' && (localLoading || (kw.length > 0 && searching))) {
      return <Spin style={{ marginTop: Spacing.MD }} />;
    }
    if (currentScope && scopeLoading === currentScope && rows.length === 0) {
      return <Spin style={{ marginTop: Spacing.MD }} />;
    }
    if (rows.length === 0) {
      if (currentScope && errScopes[currentScope]) {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="列表加载失败，后端未返回数据"
          >
            <Button
              size="small"
              type="link"
              onClick={() => void loadScope(currentScope)}
            >
              重试
            </Button>
          </Empty>
        );
      }
      if (source === 'pack' && !activePack) {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="左栏选择一个合集"
          />
        );
      }
      if (source === 'project') {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="项目根没有可加入的文件"
          />
        );
      }
      if (source === 'local' && localDirRows.length === 0) {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              kw.length > 0
                ? `「${keyword.trim()}」无匹配文件`
                : '该目录为空或无法读取'
            }
          />
        );
      }
      if (source === 'pack') {
        return (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="该合集没有文件"
          />
        );
      }
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={emptyTextOf(currentScope as ScopeKey, !!sessionId)}
        />
      );
    }
    return (
      <>
        {renderList(rows)}
        {currentScope && hasMore[currentScope] && (
          <div style={{ textAlign: 'center', marginTop: Spacing.SM }}>
            <Button
              type="text"
              size="small"
              loading={scopeLoading === currentScope}
              onClick={() => void loadScope(currentScope, true)}
            >
              加载更多（已显示 {rows.length} 条）
            </Button>
          </div>
        )}
      </>
    );
  };

  const paneTitle = (): string => {
    if (source === 'pack') {
      if (!activePack) return '合集';
      return activePack.note
        ? `${activePack.name} · ${activePack.note}`
        : activePack.name;
    }
    if (source === 'local') {
      return hostLabel ? `后端电脑 · ${hostLabel}` : '后端电脑';
    }
    if (source === 'fav') return '已收藏';
    if (source === 'project')
      return projectRoot ? `项目文件【来自：${projectRoot}】` : '项目文件';
    if (source === 'ai') return '任务产物';
    if (source === 'recent') return '最近用过';
    return '本会话';
  };

  const favLabel = `★ 已收藏${
    lists.global.length > 0
      ? ` (${lists.global.length}${hasMore.global ? '+' : ''})`
      : ''
  }`;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={720}
      title={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          附件
          <Tooltip title={ATTACHMENT_RULES}>
            <InfoCircleOutlined
              style={{ color: Colors.TEXT.SECONDARY, fontSize: FontSize.CAPTION }}
              aria-label="附件规则说明"
            />
          </Tooltip>
        </span>
      }
      footer={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={metaStyle}>
            已加入 {refs.length} 项 · 共 {formatBytes(totalSize)}
          </span>
          <div style={{ marginLeft: 'auto' }}>
            <Button type="primary" onClick={onClose}>
              完成
            </Button>
          </div>
        </div>
      }
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: Spacing.SM }}
      >
        <div style={{ display: 'flex', gap: 8 }}>
          <Input
            allowClear
            placeholder="搜索文件名…"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setActiveIndex(-1);
            }}
          />
          <Upload
            multiple
            accept={caps?.accept}
            showUploadList={false}
            disabled={disabled || busy > 0}
            beforeUpload={beforeUpload}
          >
            <Button icon={<UploadOutlined />} loading={busy > 0}>
              上传文件
            </Button>
          </Upload>
        </div>

        <div style={{ display: 'flex', gap: Spacing.SM }}>
          {/* 左栏：来源 + 收藏 + 合集仓库 */}
          <div
            style={{
              width: 176,
              flexShrink: 0,
              borderRight: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingRight: Spacing.XS,
            }}
          >
            {NAV.map((n) => (
              <div
                key={n.key}
                style={navItemStyle(source === n.key)}
                onClick={() => {
                  setSource(n.key);
                  setActivePack(null);
                  setActiveIndex(-1);
                }}
              >
                {n.label}
              </div>
            ))}
            <div
              style={{
                margin: `${Spacing.SM}px 0 ${Spacing.XS}px`,
                fontSize: FontSize.CAPTION,
                color: Colors.TEXT.SECONDARY,
              }}
            >
              收藏与合集
            </div>
            <div
              style={navItemStyle(source === 'fav')}
              onClick={() => {
                setSource('fav');
                setActivePack(null);
                setActiveIndex(-1);
              }}
            >
              {favLabel}
            </div>
            {packLimits && (
              <div
                style={{
                  margin: `${Spacing.XS}px 0 2px`,
                  padding: '0 10px',
                  fontSize: FontSize.CAPTION,
                  color: Colors.TEXT.SECONDARY,
                }}
              >
                {`合集 ${packs.length}/${packLimits.max_packs}`}
              </div>
            )}
            <div style={{ maxHeight: 220, overflowY: 'auto' }}>
              {packs.length === 0 ? (
                <div style={{ ...metaStyle, padding: '2px 10px' }}>
                  暂无合集
                </div>
              ) : (
                packs.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      ...navItemStyle(
                        source === 'pack' && activePack?.id === p.id
                      ),
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                    onClick={() => {
                      setSource('pack');
                      setActivePack(p);
                      setActiveIndex(-1);
                    }}
                  >
                    <FolderOpenOutlined />
                    <span
                      style={{
                        flex: 1,
                        minWidth: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {p.name}
                    </span>
                    <span style={metaStyle}>
                      {packLimits
                        ? `${p.items.length}/${packLimits.max_items}`
                        : p.items.length}
                    </span>
                    <Dropdown
                      trigger={['click']}
                      menu={{
                        items: [
                          { key: 'rename', label: '重命名' },
                          { key: 'remove', label: '删除合集' },
                        ],
                        onClick: ({ key, domEvent }) => {
                          domEvent.stopPropagation();
                          if (key === 'rename') {
                            setRenamingPack(p);
                            setPackNameValue(p.name);
                          } else {
                            void removePack(p);
                          }
                        },
                      }}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<MoreOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Dropdown>
                  </div>
                ))
              )}
            </div>
            <div style={{ marginTop: Spacing.XS }}>
              <MaterialPackSaveForm
                refs={refs}
                onSaved={reloadPacks}
                limits={packLimits}
                atLimit={atPackLimit}
              />
            </div>
          </div>

          {/* 右栏：来源内容 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: Spacing.XS,
                marginBottom: Spacing.XS,
              }}
            >
              {source === 'pack' && activePack && (
                <Button
                  size="small"
                  type="text"
                  onClick={() => setActivePack(null)}
                >
                  ← 返回
                </Button>
              )}
              <Typography.Text strong>{paneTitle()}</Typography.Text>
              {source === 'recent' && lists.recent.length > 0 && (
                <Popconfirm
                  title="清空最近使用记录？"
                  description="只清空使用记录，不会删除任何文件。"
                  okText="清空"
                  cancelText="取消"
                  onConfirm={() => void clearRecent()}
                >
                  <Button
                    size="small"
                    type="text"
                    style={{ marginLeft: 'auto' }}
                  >
                    清空记录
                  </Button>
                </Popconfirm>
              )}
              {source === 'pack' && activePack && (
                <Button
                  size="small"
                  style={{ marginLeft: 'auto' }}
                  loading={feedBusy}
                  disabled={activePack.items.length === 0}
                  onClick={() => void feedPack(activePack)}
                >
                  全部加入本轮
                </Button>
              )}
            </div>

            {source === 'local' && canLocal && (
              <div style={{ marginBottom: Spacing.XS }}>
                <Typography.Text style={metaStyle}>
                  同机模式：直接读取后端电脑文件，不传输、不占额外空间
                  {importing ? ' · 导入中…' : ''}
                </Typography.Text>

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 6,
                    marginTop: Spacing.XS,
                  }}
                >
                  {quick.map((q) => (
                    <Button
                      key={q.path}
                      size="small"
                      onClick={() => navigate(q.path)}
                    >
                      {q.label}
                    </Button>
                  ))}
                  {drives.map((d) => (
                    <Tooltip
                      key={d.path}
                      title={
                        d.ready
                          ? `可用 ${formatBytes(d.free)} / 共 ${formatBytes(d.total)}`
                          : '不可用'
                      }
                    >
                      <Button
                        size="small"
                        disabled={!d.ready}
                        onClick={() => navigate(d.path)}
                      >
                        {d.path.slice(0, 2)}
                        {d.label ? ` ${d.label}` : ''}
                      </Button>
                    </Tooltip>
                  ))}
                </div>

                <div style={{ display: 'flex', gap: 6, marginTop: Spacing.XS }}>
                  <Button
                    size="small"
                    icon={<ArrowUpOutlined />}
                    disabled={!cwd}
                    onClick={() => navigate(parentOf(cwd))}
                  />
                  <Input
                    size="small"
                    allowClear
                    value={pathDraft}
                    placeholder="盘符路径，如 D:\资料"
                    onChange={(e) => setPathDraft(e.target.value)}
                    onPressEnter={() => navigate(pathDraft)}
                  />
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => navigate(pathDraft)}
                  >
                    转到
                  </Button>
                </div>

                {authDirs.length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      gap: 6,
                      marginTop: Spacing.XS,
                    }}
                  >
                    <span style={metaStyle}>已授权</span>
                    {authDirs.map((a) => (
                      <Tag
                        key={a.path}
                        closable
                        onClose={(e) => {
                          e.preventDefault();
                          void revokeDir(a.path);
                        }}
                      >
                        {a.path}
                      </Tag>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 目录（不可加入，点进入） */}
            {localDirRows.length > 0 && (
              <div style={{ marginBottom: Spacing.XS }}>
                {localDirRows.map((d) => (
                  <div
                    key={d.key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '6px 8px',
                      borderRadius: 6,
                      cursor: 'pointer',
                    }}
                    onClick={() => navigate(d.abs)}
                  >
                    <FolderOutlined style={{ color: Colors.TEXT.SECONDARY }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={nameStyle}>{d.name}</div>
                      <div style={metaStyle}>文件夹</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ maxHeight: 440, overflowY: 'auto' }}>
              {renderRows()}
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={!!renamingPack}
        title="重命名合集"
        okText="保存"
        cancelText="取消"
        onOk={() => void doRenamePack()}
        onCancel={() => setRenamingPack(null)}
      >
        <Input
          value={packNameValue}
          autoFocus
          onChange={(e) => setPackNameValue(e.target.value)}
          onPressEnter={() => void doRenamePack()}
        />
      </Modal>

      <Modal
        open={!!renamingAtt}
        title="重命名文件"
        okText="保存"
        cancelText="取消"
        onOk={() => void doRenameAtt()}
        onCancel={() => setRenamingAtt(null)}
      >
        <Input
          value={attNameValue}
          autoFocus
          onChange={(e) => setAttNameValue(e.target.value)}
          onPressEnter={() => void doRenameAtt()}
        />
      </Modal>

      <PreviewDrawer
        record={preview}
        sessionId={sessionId}
        added={preview ? isAdded(preview) : false}
        onClose={() => setPreview(null)}
        onAdd={(rec) => {
          if (!isAdded(rec)) toggleAttachment(rec);
          setPreview(null);
        }}
        onDelete={(rec) => {
          setPreview(null);
          void confirmDelete(rec);
        }}
      />
    </Drawer>
  );
};

export { FileDrawer };
