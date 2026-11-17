/**
 * SessionWorkspacePanel - 事项工作区面板
 *
 * 编辑历史:
 * 2026-10-10 小欧 - 新建: 会话目录展示(可用/不可用置灰)、增删、保存校验、只读展示项目根+授权目录
 * 2026-10-10 小欧 - 修4错: updater外弹框、删空二次确认按后果判、load失败降级、被拒留痕区
 * 2026-10-10 小欧 - UI优化7项: 只读区分行+图标+可复制、删除键Tooltip+danger、留痕中性框、添加钮只留图标、空态Empty、徽标0隐藏
 * 2026-10-28 小欧 - 草稿升 WsDraft[](path+属性+memo+is_default只读), 行内编辑增删改,
 *   属性自定义值 localStorage 持久化 — 小欧-2026-10-30
 * 2026-10-30 18:36:36 小欧 - 彻底解耦: 本地立即关闭+后台提交(不 await PATCH), 取数挂 open+代际守卫,
 *   load 不覆盖草稿(dirtyRef), 被拒留痕由 store 跨关闭承载 — 小欧-2026-10-30
 * 2026-10-30 23:49:48 小欧 - 默认行路径改只读(属性/备注仍可改、删除仍允许), 清空确认文案同步 — 小欧-2026-10-30
 * 2026-10-31 00:06:17 小欧 - 只读区两行去掉「只读」字样: 项目根/授权目录是全局配置(设置→通用) — 小欧-2026-10-31
 * 2026-10-31 00:19:05 小欧 - 默认工作区系统内不可删: 不渲染删除钮 + remove() 防御兜底 — 小欧-2026-10-31
 * 2026-11-02 小欧 - 删本地 isAbsolute(自建盘符/UNC 正则), 复用 utils/projectPath.isAbsolutePath — 小欧-2026-11-02
 * 2026-11-02 小欧 - 全量重写: 只读区两行常驻、行结构两行真grid、路径完整折行不裁剪、
 *   属性去色、422草稿恢复、Esc脏确认、三态互斥 — 小欧-2026-11-02
 * 2026-11-02 小欧 - 一致性整改: 路径配对统一 wsPathKey、属性持久化下沉 wsProp、只读区抽 CtxRow、
 *   恢复条按 recovered 常驻(问题改完仍可放弃)、取数显式 prune — 小欧-2026-11-02
 * 2026-11-02 小欧 - 收口: 复制复用 utils/clipboard、读失败透传原始错误、未匹配问题行显式计数、
 *   字号/内边距改引令牌 — 小欧-2026-11-02
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { InputRef } from 'antd';
import type {
  ClipboardEvent as ReactClipboardEvent,
  KeyboardEvent as ReactKeyboardEvent,
  ReactNode,
} from 'react';
import {
  Modal,
  List,
  Input,
  Button,
  Typography,
  Space,
  Empty,
  Tooltip,
  AutoComplete,
  Tag,
  ConfigProvider,
  Skeleton,
} from 'antd';
import {
  PlusOutlined,
  FolderOutlined,
  LockOutlined,
  EditOutlined,
  DeleteOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import {
  settingsModalWidth,
} from '@/theme/settingsTokens';
// 2026-11-12 小欧 - 控件高改读全站刻度(文档[32]):
//   本面板原写死 controlHeight(28) 于 14 处, 且 ConfigProvider 内又硬写
//   controlHeight=28 + borderRadius=4 → 密度对面板无效, 且控件规格真源散落三处。
//   现统一: 面板内控件高取刻度 normal 档(随密度), 圆角取逐页审计结论(全档 4);
//   Modal 的确定/取消按钮在面板 ConfigProvider **之外**渲染, 必须显式给密度感知的高度。
import { useAppearancePrefs } from '@/hooks/useAppearancePrefs';
import {
  controlHeightByDensity,
  pageControlTokens,
} from '@/theme/controlScale';
import {
  Spacing,
  FontSize,
  Colors,
  Radius,
  FontFamily,
  FontWeight,
} from '@/utils/stepStyles';
import { sessionApi } from '@/services/api/session.api';
import {
  handleError,
  showMessage,
  showSuccess,
  ErrorType,
} from '@/services/error/handler';
import { workspaceStore } from '../../services/sessionWorkspaceStore';
/** 只做绝对路径格式校验（全局幂等判据）；存在性与禁区交后端判，前端不造禁区表 */
import { isAbsolutePath } from '@/utils/projectPath';
import { copyTextToClipboard } from '@/utils/clipboard';
import {
  DEFAULT_WS_PROP,
  saveCustomProp,
  wsPathKey,
  wsPropLabel as propLabel,
  wsPropOptions,
  wsPropValue as propValue,
} from '@/utils/wsProp';

interface Props {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}

/** 动作列宽 = 3 个图标钮 32 + 2 个间距 4（固定列，换行不跳） */
const ACTION_COL = 104;
/** 只读区标签列宽（两行标签同列起，值列才可能对齐） */
const CTX_LABEL_WIDTH = 72;

/** 路径文本与次要文字样式：面板内多行复用，避免同一对字色散落十余处 — 小欧-2026-11-02 */
const PATH_TEXT_STYLE = {
  display: 'block',
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.PRIMARY,
  color: Colors.TEXT.STRONG,
  lineHeight: '20px',
  wordBreak: 'break-all',
} as const;

/** 次要文字（正文色 + 12 号）：面板内十余处同款，收成一处 — 小欧-2026-11-02 */
const TEXT_MUTED = {
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.PRIMARY,
} as const;

/** 只读区一行（项目根 / 授权目录）：标签列定宽对齐，值完整折行不裁剪 — 小欧-2026-11-02 */
function CtxRow({
  icon,
  label,
  value,
  copyText,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  copyText: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: Spacing.XS,
        minHeight: 22,
      }}
    >
      <span
        style={{
          fontSize: FontSize.PRIMARY,
          lineHeight: '22px',
          color: Colors.TEXT.SECONDARY,
          flexShrink: 0,
        }}
      >
        {icon}
      </span>
      <Typography.Text
        style={{
          width: CTX_LABEL_WIDTH,
          flexShrink: 0,
          lineHeight: '22px',
          ...TEXT_MUTED,
        }}
      >
        {label}
      </Typography.Text>
      <Typography.Text
        copyable={
          copyText ? { text: copyText, tooltips: ['复制', '已复制'] } : false
        }
        style={{
          fontFamily: FontFamily.MONO,
          lineHeight: '22px',
          minWidth: 0,
          wordBreak: 'break-all',
          ...TEXT_MUTED,
        }}
      >
        {value || '（未配置）'}
      </Typography.Text>
    </div>
  );
}

/** Esc：先掐断冒泡（否则弹窗一起关），再执行就地处理 — 小欧-2026-11-02 */
const stopEsc = (ev: ReactKeyboardEvent, run: () => void) => {
  if (ev.key !== 'Escape') return;
  ev.stopPropagation();
  run();
};

/** 面板内部草稿：is_default 只读展示（PATCH 不携带） */
type WsDraft = {
  path: string;
  workspace_property: string;
  memo: string;
  is_default: boolean;
};

/** 库行/快照项 → 草稿 */
const toDraft = (w: {
  path: string;
  workspace_property?: string | null;
  memo?: string | null;
  is_default?: boolean;
}): WsDraft => ({
  path: w.path,
  workspace_property: propValue(w.workspace_property),
  memo: w.memo || '',
  is_default: Boolean(w.is_default),
});

export default function SessionWorkspacePanel({
  sessionId,
  open,
  onClose,
}: Props) {
  const [entries, setEntries] = useState<WsDraft[]>([]);
  // 2026-11-12 小欧 - 面板控件高取全站刻度 normal 档(随密度); Modal 底栏按钮在面板
  //   ConfigProvider 之外渲染, 故此处取同一数值显式下发(文档[32])。
  const { density } = useAppearancePrefs();
  const controlHeight = controlHeightByDensity(density).normal;
  const [projectRoot, setProjectRoot] = useState('');
  const [allowedDirs, setAllowedDirs] = useState<string[]>([]);
  // 新增区
  const [input, setInput] = useState('');
  const [propInput, setPropInput] = useState(DEFAULT_WS_PROP);
  const [memoInput, setMemoInput] = useState('');
  const [inputErr, setInputErr] = useState('');
  // 编辑态
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const [editPath, setEditPath] = useState('');
  const [editProp, setEditProp] = useState(DEFAULT_WS_PROP);
  const [editMemo, setEditMemo] = useState('');
  const [editErr, setEditErr] = useState('');
  // 保存被拒：path(小写) → 原因；有值即"草稿恢复"态
  const [badMap, setBadMap] = useState<Record<string, string>>({});
  const [recovered, setRecovered] = useState(false);

  const [loadState, setLoadState] = useState<
    'idle' | 'loading' | 'ready' | 'failed'
  >('idle');
  const dirtyRef = useRef(false);
  const loadSeqRef = useRef(0);
  const addPathRef = useRef<InputRef>(null);
  const editPathRef = useRef<InputRef>(null);
  const editMemoRef = useRef<InputRef>(null);
  /** 本次编辑目标是否默认行（默认行路径 disabled，焦点要落备注框） */
  const editTargetIsDefault = useRef(false);

  const badCount = Object.keys(badMap).length;

  /** AutoComplete options = 预设 + 自定义（wsProp 单一真源，面板不重复过滤） — 小欧-2026-11-02 */
  const propOptions = useMemo(() => wsPropOptions(), []);

  /** 打开即重拉（无暂存：关闭即丢）。
   *  422 快照优先于库真值：用户上次提交没通过时，草稿比库更接近他的意图。 */
  const load = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoadState('loading');
    try {
      // prune=true: 只有"用户主动打开面板"才清库；浏览页/对账一律纯读 — 小欧-2026-11-02
      const r = await sessionApi.getWorkspaces(sessionId, true);
      if (seq !== loadSeqRef.current) return;
      setProjectRoot(r.project_root);
      setAllowedDirs(r.allowed_dirs);
      setInputErr('');
      setEditingPath(null);
      if (r.pruned > 0) {
        // 清理不静默：告诉用户发生了什么（磁盘目录未删，随时可重新添加）
        showMessage(
          ErrorType.INFO,
          `已清理 ${r.pruned} 条失效目录（磁盘目录未删除）`
        );
      }
      if (!dirtyRef.current) {
        const snap = workspaceStore.getSnapshot();
        const rec = snap.sessionId === sessionId ? snap.rejected : null;
        if (rec) {
          // is_default 必须按库真值重贴：快照不带该字段，否则默认行会长出删除钮
          const defaults = new Set(
            r.workspaces
              .filter((w) => w.is_default)
              .map((w) => wsPathKey(w.path))
          );
          setEntries(
            rec.items.map((i) => ({
              ...toDraft(i),
              is_default: defaults.has(wsPathKey(i.path)),
            }))
          );
          setBadMap(
            Object.fromEntries(
              rec.bad.map((b) => [wsPathKey(b.path), b.reason])
            )
          );
          setRecovered(true);
        } else {
          setEntries(r.workspaces.map(toDraft));
          setBadMap({});
          setRecovered(false);
        }
      }
      setLoadState('ready');
    } catch (e) {
      if (seq !== loadSeqRef.current) return;
      setProjectRoot('');
      setAllowedDirs([]);
      setEditingPath(null);
      setLoadState('failed');
      // 透传原始错误: 判定分类(超时/离线/404)与后端 detail 都在 e 里, 自造 Error 会全丢 — 小欧-2026-11-02
      handleError(e);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!open || !sessionId) return;
    dirtyRef.current = false;
    void load();
    return () => {
      loadSeqRef.current += 1;
    };
  }, [open, sessionId, load]);

  /** 进编辑即落焦：普通行→路径框，默认行→备注框（路径 disabled，焦点落空等于没动） */
  useEffect(() => {
    if (!editingPath) return;
    (editTargetIsDefault.current ? editMemoRef : editPathRef).current?.focus();
  }, [editingPath]);

  /** 清掉某路径（小写）的问题标记 */
  const dropBad = (p: string) =>
    setBadMap((m) => {
      const k = wsPathKey(p);
      if (!m[k]) return m;
      const next = { ...m };
      delete next[k];
      return next;
    });

  /** 入列共用实现：单条添加与批量粘贴都走这里（输入 state 不在此触碰）。
   *  同路径覆盖属性/备注，不产生重复行 */
  const pushDraft = (v: string, rawProp: string, memo: string) => {
    const p = propValue(rawProp);
    saveCustomProp(p);
    dirtyRef.current = true;
    dropBad(v);
    setEntries((es) =>
      es.some((e) => wsPathKey(e.path) === wsPathKey(v))
        ? es.map((e) =>
            wsPathKey(e.path) === wsPathKey(v)
              ? { ...e, workspace_property: p, memo }
              : e
          )
        : [...es, { path: v, workspace_property: p, memo, is_default: false }]
    );
  };

  /** 单条添加（Enter / [+ 添加] 同走） */
  const addEntry = () => {
    const v = input.trim();
    if (!v || !isAbsolutePath(v)) {
      setInputErr('请输入绝对路径');
      return;
    }
    pushDraft(v, propInput, memoInput.trim());
    setInput('');
    setPropInput(DEFAULT_WS_PROP);
    setMemoInput('');
    setInputErr('');
    addPathRef.current?.focus();
  };

  /** 粘贴收尾：合法条已入列则清备注；非法行留在输入框等修正 */
  const applyPasteResult = (bad: string[], goodCount: number) => {
    setInput(bad.join('\n'));
    if (goodCount > 0) {
      setMemoInput('');
      setInputErr(
        bad.length
          ? `已添加 ${goodCount} 条，${bad.length} 行不是绝对路径（已保留在输入框）`
          : ''
      );
    } else {
      setInputErr(`这 ${bad.length} 行都不是绝对路径，请修正`);
    }
  };

  /** 批量粘贴：多行拆条；合法入列，**非法行原样留在输入框**（输入永不静默丢弃） */
  const handlePaste = (ev: ReactClipboardEvent<HTMLInputElement>) => {
    const text = ev.clipboardData.getData('text');
    if (!/\r?\n/.test(text)) return;
    ev.preventDefault();
    const lines = text
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!lines.length) return;
    const good = lines.filter(isAbsolutePath);
    const bad = lines.filter((l) => !isAbsolutePath(l));
    good.forEach((v) => pushDraft(v, propInput, memoInput.trim()));
    applyPasteResult(bad, good.length);
  };

  /** 行级复制（真需求：粘到资源管理器/终端）；复用 utils/clipboard 唯一实现，成功才提示 — 小欧-2026-11-02 */
  const copyPath = async (p: string) => {
    const r = await copyTextToClipboard(p);
    if (r.ok) {
      showSuccess('已复制路径');
      return;
    }
    showMessage(ErrorType.COPY_FAILED, '复制失败：浏览器未授权剪贴板');
  };

  /** 进入编辑态 */
  const startEdit = (e: WsDraft) => {
    editTargetIsDefault.current = e.is_default;
    setEditingPath(e.path);
    setEditPath(e.path);
    setEditProp(e.workspace_property);
    setEditMemo(e.memo);
    setEditErr('');
  };

  /** 保存编辑：绝对路径 + 同列表去重 */
  const saveEdit = () => {
    if (!editingPath) return;
    const v = editPath.trim();
    if (!v || !isAbsolutePath(v)) {
      setEditErr('请输入绝对路径');
      return;
    }
    const clash = entries.some(
      (e) => e.path !== editingPath && wsPathKey(e.path) === wsPathKey(v)
    );
    if (clash) {
      setEditErr('该目录已在列表中');
      return;
    }
    const p = propValue(editProp);
    saveCustomProp(p);
    dirtyRef.current = true;
    setEntries((es) =>
      es.map((e) =>
        e.path === editingPath
          ? { ...e, path: v, workspace_property: p, memo: editMemo.trim() }
          : e
      )
    );
    dropBad(editingPath);
    dropBad(v);
    setEditingPath(null);
  };

  /** 行级取消：编辑态收起，不改弹窗开关 */
  const cancelEdit = () => setEditingPath(null);

  /** 删除：草稿内操作，「取消」即撤销 —— 不再逐条二次确认（与事务模型一致） */
  const remove = (path: string) => {
    const target = entries.find((e) => e.path === path);
    if (target?.is_default) return; // UI 已不渲染默认行删除钮，此处防御兜底
    dirtyRef.current = true;
    setEntries((es) => es.filter((e) => e.path !== path));
    dropBad(path);
    if (editingPath === path) setEditingPath(null);
  };

  /** 确定 → 本地立即关闭 + 后台提交（不可 await，界面进度不能由网络往返决定） */
  const confirm = () => {
    if (loadState !== 'ready' || badCount > 0) return; // 有未修正的问题行时禁提交
    void workspaceStore.commit(
      sessionId,
      entries.map((e) => ({
        path: e.path,
        workspace_property: propValue(e.workspace_property),
        memo: e.memo.trim() || null,
      }))
    );
    dirtyRef.current = false;
    onClose();
  };

  /** 关闭请求：脏数据先确认（Esc / × / 遮罩 同一入口） */
  const requestClose = () => {
    if (!dirtyRef.current) {
      onClose();
      return;
    }
    Modal.confirm({
      title: '放弃未保存的修改？',
      content: '目录列表的改动尚未保存，关闭后不再保留。',
      okText: '放弃修改',
      cancelText: '继续编辑',
      okButtonProps: { danger: true },
      onOk: onClose,
    });
  };

  /** 放弃被拒草稿 → 清快照 + 按库真值重载 */
  const discardRecovered = () => {
    workspaceStore.clearRejected(sessionId);
    dirtyRef.current = false;
    setBadMap({});
    setRecovered(false);
    void load();
  };

  /** 快照里未能对应到任何行的原因（极少见：后端归一化后路径形态变了） */
  const matchedKeys = new Set(entries.map((e) => wsPathKey(e.path)));
  const unmatchedBad = Object.entries(badMap).filter(
    ([k]) => !matchedKeys.has(k)
  );

  return (
    <Modal
      open={open}
      width={settingsModalWidth.workspace}
      destroyOnHidden
      maskClosable
      title="事项工作区"
      okText="确定"
      cancelText="取消"
      onOk={confirm}
      onCancel={requestClose}
      okButtonProps={{
        disabled: loadState !== 'ready' || badCount > 0,
        style: { height: controlHeight },
      }}
      cancelButtonProps={{ style: { height: controlHeight } }}
      styles={{ body: { paddingTop: Spacing.MD } }}
    >
      <ConfigProvider
        theme={{
          // 2026-11-12 小欧 - 面板控件规格读全站刻度(文档[32]):
          //   原硬写 controlHeight=28 + borderRadius=4, 密度对面板无效, 且缺派生档位
          //   (antd 按 0.75×/1.25× 派生 → small 21px 低于「文字不被压」22px 底线)。
          //   现用页面级预设: normal 随密度、small 与 normal 齐平(逐页审计同源结论)、
          //   圆角全档 4(须显式补发 LG, 否则继承全局 8)。
          token: pageControlTokens(density),
        }}
      >
        {/* 只读区：两行常驻（项目根 / 授权目录）。标签列定宽 → 值列同列起；
            值完整显示、超宽折行 —— 全局配置的路径同样不许裁剪（2026-11-02 小欧） */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: Spacing.XS,
            padding: `${Spacing.XS}px 0`,
          }}
        >
          <CtxRow
            icon={<FolderOutlined />}
            label="项目根"
            value={projectRoot}
            copyText={projectRoot}
          />
          <CtxRow
            icon={<LockOutlined />}
            label="授权目录"
            value={allowedDirs.join('；')}
            copyText={allowedDirs.length ? allowedDirs.join('\n') : ''}
          />
        </div>

        {/* 恢复条：只要草稿来自 422 快照就常驻（问题改完后仍需一个"放弃"出口，
            否则快照会一直留在 store，下次打开又恢复，与"关闭即放弃"直觉冲突） */}
        {recovered && (
          <div
            role="status"
            style={{
              marginTop: Spacing.MD,
              padding: Spacing.MD,
              background: Colors.WARNING_BG,
              border: `1px solid ${Colors.WARNING}`,
              borderRadius: Radius.DEFAULT,
            }}
          >
            <div
              style={{ display: 'flex', alignItems: 'center', gap: Spacing.MD }}
            >
              <Typography.Text style={{ ...TEXT_MUTED, flex: 1 }}>
                {badCount > 0
                  ? `上次保存未通过，已恢复你的修改（${badCount} 条需修正）。修正或移除后才能保存。`
                  : '上次保存未通过，已恢复你的修改。确认无误后点「确定」保存。'}
              </Typography.Text>
              <Button
                type="text"
                size="small"
                style={{ height: controlHeight, flexShrink: 0 }}
                onClick={discardRecovered}
              >
                放弃修改
              </Button>
            </div>
            {unmatchedBad.slice(0, 3).map(([p, r]) => (
              <div
                key={p}
                style={{
                  fontSize: FontSize.SMALL,
                  color: Colors.TEXT.PRIMARY,
                  marginTop: Spacing.XS,
                  wordBreak: 'break-all',
                }}
              >
                · {p}：{r}
              </div>
            ))}
            {unmatchedBad.length > 3 && (
              <div
                style={{
                  fontSize: FontSize.SMALL,
                  color: Colors.TEXT.PRIMARY,
                  marginTop: Spacing.XS,
                }}
              >
                {`另有 ${unmatchedBad.length - 3} 条未显示（「放弃修改」可整体丢弃）`}
              </div>
            )}
          </div>
        )}

        {/* 节标题：已配置目录 + 计数 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: Spacing.XS,
            marginTop: Spacing.XL,
            marginBottom: Spacing.MD,
          }}
        >
          <Typography.Text
            style={{ ...TEXT_MUTED, fontWeight: FontWeight.MEDIUM }}
          >
            已配置目录
          </Typography.Text>
          <Typography.Text
            style={{ fontSize: FontSize.SMALL, color: Colors.TEXT.PRIMARY }}
          >
            {entries.length} 项
          </Typography.Text>
        </div>

        {/* 三态互斥：加载骨架 / 失败只给错误条 / 就绪才出列表 */}
        {loadState === 'loading' && (
          <div aria-hidden>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  minHeight: 48,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: Spacing.XS,
                }}
              >
                <Skeleton.Input
                  active
                  size="small"
                  style={{ width: '70%', height: 16 }}
                />
                <Skeleton.Input
                  active
                  size="small"
                  style={{ width: '40%', height: 14 }}
                />
              </div>
            ))}
          </div>
        )}

        {loadState === 'failed' && (
          <div
            role="alert"
            style={{
              marginTop: Spacing.MD,
              padding: Spacing.MD,
              background: Colors.ERROR_BG,
              border: `1px solid ${Colors.ERROR_BORDER}`,
              borderRadius: Radius.DEFAULT,
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.MD,
            }}
          >
            <Typography.Text
              style={{
                fontSize: FontSize.SECONDARY,
                color: Colors.ERROR_TEXT,
                flex: 1,
              }}
            >
              目录读取失败，暂不能保存（避免用空列表覆盖已有目录）。
            </Typography.Text>
            <Button
              size="small"
              type="text"
              style={{ height: controlHeight, flexShrink: 0 }}
              onClick={() => void load()}
            >
              重试
            </Button>
          </div>
        )}

        {loadState === 'ready' && (
          <List
            dataSource={entries.map((d) => ({ ...d, key: d.path }))}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    <span style={TEXT_MUTED}>
                      此会话尚未配置目录。发送消息后系统会自动创建默认工作区。
                    </span>
                  }
                >
                  <Button
                    ghost
                    type="primary"
                    size="small"
                    style={{ height: controlHeight }}
                    onClick={() => addPathRef.current?.focus()}
                  >
                    添加目录
                  </Button>
                </Empty>
              ),
            }}
            renderItem={(e) => {
              const editing = editingPath === e.path;
              const reason = badMap[wsPathKey(e.path)];
              return (
                <List.Item style={{ padding: 0, minHeight: 48 }}>
                  {/* 真网格：内容列多少字都不影响动作列位置；
                      路径折行时动作列贴顶对齐（图标不随行高漂到中间） */}
                  <div
                    style={{
                      width: '100%',
                      display: 'grid',
                      gridTemplateColumns: `minmax(0, 1fr) ${ACTION_COL}px`,
                      columnGap: Spacing.MD,
                      alignItems: 'start',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      {editing ? (
                        /* 编辑态：行内展开（高度变化是显式动作的结果，不做动画） */
                        <div style={{ width: '100%' }}>
                          <Input
                            ref={editPathRef}
                            value={editPath}
                            placeholder="目录路径"
                            disabled={e.is_default}
                            status={editErr ? 'error' : undefined}
                            style={{ fontFamily: FontFamily.MONO }}
                            onChange={(ev) => {
                              setEditPath(ev.target.value);
                              setEditErr('');
                            }}
                            onPressEnter={saveEdit}
                            onKeyDown={(ev) => stopEsc(ev, cancelEdit)}
                          />
                          {e.is_default && (
                            <Typography.Text
                              style={{
                                ...TEXT_MUTED,
                                display: 'block',
                                marginTop: Spacing.XS,
                              }}
                            >
                              默认工作区路径由系统按项目根生成，不可修改；如需换落点请新增目录。
                            </Typography.Text>
                          )}
                          <Space.Compact
                            style={{ width: '100%', marginTop: Spacing.XS }}
                          >
                            <AutoComplete
                              value={editProp}
                              options={propOptions}
                              onChange={setEditProp}
                              style={{ width: 140 }}
                              placeholder="属性"
                            />
                            <Input
                              ref={editMemoRef}
                              value={editMemo}
                              placeholder="备注（可选）"
                              onChange={(ev) => setEditMemo(ev.target.value)}
                              onPressEnter={saveEdit}
                              onKeyDown={(ev) => stopEsc(ev, cancelEdit)}
                              style={{ flex: 1 }}
                            />
                          </Space.Compact>
                          {editErr && (
                            <Typography.Text
                              style={{
                                display: 'block',
                                marginTop: Spacing.XS,
                                fontSize: FontSize.SMALL,
                                color: Colors.ERROR_TEXT,
                              }}
                            >
                              {editErr}
                            </Typography.Text>
                          )}
                          <Space
                            size={Spacing.MD}
                            style={{ marginTop: Spacing.XS }}
                          >
                            <Button
                              type="primary"
                              size="small"
                              style={{ height: controlHeight }}
                              onClick={saveEdit}
                            >
                              保存
                            </Button>
                            <Button
                              size="small"
                              style={{ height: controlHeight }}
                              onClick={cancelEdit}
                            >
                              取消
                            </Button>
                          </Space>
                        </div>
                      ) : (
                        <>
                          {/* 行1：路径（唯一主信息）—— 完整显示，超宽折行，绝不裁剪 */}
                          <Typography.Text style={PATH_TEXT_STYLE}>
                            {e.path}
                          </Typography.Text>
                          {/* 行2：默认标记 + 属性（分类文字，不上色）+ 备注 */}
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: Spacing.XS,
                              marginTop: 2,
                              minHeight: 16,
                              minWidth: 0,
                            }}
                          >
                            {e.is_default && (
                              <Tag
                                style={{
                                  margin: 0,
                                  padding: `0 ${Spacing.XS}px`,
                                  fontSize: FontSize.SMALL,
                                  lineHeight: '14px',
                                  color: Colors.INFO,
                                  borderColor: Colors.INFO,
                                  background: Colors.BG.PRIMARY,
                                  borderRadius: Radius.SM,
                                  flexShrink: 0,
                                }}
                              >
                                默认
                              </Tag>
                            )}
                            <Typography.Text
                              style={{ ...TEXT_MUTED, flexShrink: 0 }}
                            >
                              {propLabel(e.workspace_property)}
                            </Typography.Text>
                            {(reason || e.memo) && (
                              <Typography.Text
                                aria-hidden
                                style={{
                                  fontSize: FontSize.SMALL,
                                  color: Colors.BORDER.STRONG,
                                }}
                              >
                                ·
                              </Typography.Text>
                            )}
                            {reason ? (
                              <Typography.Text
                                style={{
                                  fontSize: FontSize.SMALL,
                                  color: Colors.ERROR_TEXT,
                                  minWidth: 0,
                                  wordBreak: 'break-all',
                                }}
                              >
                                {reason}
                              </Typography.Text>
                            ) : e.memo ? (
                              <Typography.Text
                                style={{
                                  ...TEXT_MUTED,
                                  minWidth: 0,
                                  wordBreak: 'break-all',
                                }}
                              >
                                {e.memo}
                              </Typography.Text>
                            ) : null}
                          </div>
                        </>
                      )}
                    </div>

                    {/* 动作列：常驻图标（复制/编辑/删除），删除 hover 才红 */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: Spacing.XS,
                      }}
                    >
                      {!editing && (
                        <>
                          <Tooltip title="复制路径">
                            <Button
                              type="text"
                              icon={<CopyOutlined />}
                              aria-label="复制路径"
                              style={{
                                color: Colors.TEXT.SECONDARY,
                                height: controlHeight,
                                width: 32,
                              }}
                              onClick={() => void copyPath(e.path)}
                            />
                          </Tooltip>
                          <Tooltip
                            title={
                              e.is_default
                                ? '编辑属性/备注（默认工作区路径由系统生成）'
                                : '编辑该目录'
                            }
                          >
                            <Button
                              type="text"
                              icon={<EditOutlined />}
                              aria-label="编辑目录"
                              style={{
                                color: Colors.TEXT.SECONDARY,
                                height: controlHeight,
                                width: 32,
                              }}
                              onClick={() => startEdit(e)}
                            />
                          </Tooltip>
                          {!e.is_default && (
                            <Tooltip title="移除该目录">
                              <Button
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                aria-label="移除目录"
                                style={{
                                  color: Colors.TEXT.SECONDARY,
                                  height: controlHeight,
                                  width: 32,
                                }}
                                onClick={() => remove(e.path)}
                              />
                            </Tooltip>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
        )}

        {/* 新增区：就绪才出现（失败态不许用户在"看不到现状"时加东西） */}
        {loadState === 'ready' && (
          <>
            <div
              style={{
                marginTop: Spacing.XL,
                paddingTop: Spacing.MD,
                borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                marginBottom: Spacing.MD,
              }}
            >
              <Typography.Text
                style={{ ...TEXT_MUTED, fontWeight: FontWeight.MEDIUM }}
              >
                新增目录
              </Typography.Text>
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                ref={addPathRef}
                style={{ flex: 1, fontFamily: FontFamily.MONO }}
                placeholder="输入完整路径（绝对路径）"
                status={inputErr ? 'error' : undefined}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setInputErr(
                    e.target.value.trim() &&
                      !isAbsolutePath(e.target.value.trim())
                      ? '请输入绝对路径'
                      : ''
                  );
                }}
                onPaste={handlePaste}
                onPressEnter={addEntry}
                onKeyDown={(ev) => {
                  // 有内容时 Esc=就地清空（不关窗）；空着则交给弹窗关闭 — 小欧-2026-11-02
                  if (input || inputErr) {
                    stopEsc(ev, () => {
                      setInput('');
                      setInputErr('');
                    });
                  }
                }}
              />
              <AutoComplete
                value={propInput}
                options={propOptions}
                onChange={setPropInput}
                style={{ width: 140 }}
                placeholder="属性"
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                style={{ width: 88 }}
                disabled={!input.trim() || !isAbsolutePath(input.trim())}
                onClick={addEntry}
              >
                添加
              </Button>
            </Space.Compact>
            {inputErr && (
              <Typography.Text
                style={{
                  display: 'block',
                  marginTop: Spacing.XS,
                  fontSize: FontSize.SMALL,
                  color: Colors.ERROR_TEXT,
                }}
              >
                {inputErr}
              </Typography.Text>
            )}
            <Input
              style={{ width: '100%', marginTop: Spacing.MD }}
              placeholder="备注（可选，如：后端源码、产物输出）"
              value={memoInput}
              onChange={(e) => setMemoInput(e.target.value)}
              onPressEnter={addEntry}
              onKeyDown={(ev) => {
                if (memoInput) stopEsc(ev, () => setMemoInput(''));
              }}
            />
          </>
        )}
      </ConfigProvider>
    </Modal>
  );
}
