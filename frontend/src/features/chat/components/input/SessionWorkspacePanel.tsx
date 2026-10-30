/**
 * SessionWorkspacePanel - 事项工作区面板
 *
 * 编辑历史: 2026-10-10 小欧 - 新建（ 四条功能需求 +  UI 视觉规范）
 * 编辑历史: 2026-10-10 小欧 - 修4错：updater外弹框/删空二次确认按后果判/load失败降级/被拒留痕区
 * 编辑历史: 2026-10-10 小欧 - UI优化7项：只读区分行+图标+可复制、路径ellipsis、删除键Tooltip+text danger、
 *   留痕区改中性框、添加按钮只留图标、空态用 Empty、徽标0自动隐藏
 *   ① 展示会话业务特定目录（可用 + 不可用置灰）
 *   ② 可增可减（添加输入框 / 行尾删除 / 删空二次确认）
 *   ③ 保存时非法自动清除 + 提示（422 被拒条目摘除、不入库、逐条提示 + 留痕）
 *   ④ 只读展示项目根 + 授权目录（无增删，决策82）
 *
 * 视觉: 全部复用 antd 原生组件与系统令牌，不自写 CSS
 *   （行高/分割线/hover 由 List 保证；留白由 Spacing 保证）
 * 编辑历史: 2026-10-30 18:36:36 小欧 - 彻底解耦(三条路分开, 见 services/sessionWorkspaceStore 头注):
 *   ①点「确定」= **本地立即关闭** + 把列表交给 workspaceStore.commit 后台提交, 本组件不再持有网络、
 *     不再 await PATCH —— 原实现"成功才关"会让任何一次请求排队/后端变慢变成"弹窗迟迟不消失";
 *   ②取数挂在 open(useEffect + 代际守卫), 不再依赖开启动画回调(重负载下动画回调会迟到/不来,
 *     面板停在空态时点确定=空列表覆盖写); 未读到服务端清单前禁用「确定」;
 *   ③load 不再 setInput('')/覆盖用户已编辑草稿(dirtyRef);
 *   ④被拒留痕改由 store 承载并跨关闭存活(提交与关闭解耦后组件内部 state 活不到下一次打开)。
 *   — 小欧-2026-10-30
 * 编辑历史: 2026-10-28 小欧 - [54]全链路重构: 草稿升 WsDraft[](path+属性+memo+is_default只读);
 *   行内编辑(增/删/改三态); 新增区两行(路径+属性AutoComplete+备注); 属性localStorage自定义值持久化。
 *   保留 store 架构(loadState/dirtyRef/loadSeqRef/notice/本地立即关闭+后台提交)。
 *   — 小欧-2026-10-30
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
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
} from 'antd';
import {
  DeleteOutlined,
  PlusOutlined,
  FolderOutlined,
  LockOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { settingsModalWidth } from '@/theme/settingsTokens';
import { Spacing, FontSize } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
import { sessionApi } from '@/services/api/session.api';
import { handleError } from '@/services/error/handler';
import { workspaceStore } from '../../services/sessionWorkspaceStore';
import type { UnusableEntry } from '@/types/chat';

interface Props {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}

/** 只做绝对路径格式校验；存在性与禁区交后端判（决策74，避免前端造禁区表） */
const isAbsolute = (p: string) => /^[A-Za-z]:[\\/]/.test(p) || /^\\\\/.test(p);

/** 面板内部草稿：path + 属性 + memo + 默认标志（is_default 只读展示，PATCH 不携带） */
type WsDraft = {
  path: string;
  workspace_property: string;
  memo: string;
  is_default: boolean;
};

/** 属性三档预设：机器值 + 中文标签 */
const WS_PROP_PRESETS = [
  { value: 'read_only', label: '读取工作区' },
  { value: 'read_write', label: '读写工作区' },
  { value: 'write', label: '写工作区' },
] as const;
const DEFAULT_WS_PROP = 'read_write';
const CUSTOM_PROPS_KEY = 'ws_custom_props';
const MAX_CUSTOM_PROPS = 16;

/** 属性 Tag 颜色：预设三档 + 自定义灰 */
const PROP_COLORS: Record<string, string> = {
  read_only: 'green',
  read_write: 'blue',
  write: 'orange',
};

/** 属性展示唯一源：机器值 → 中文标签；自定义原样；缺失 → 读写工作区 */
function propLabel(raw?: string | null): string {
  const v = (raw || '').trim();
  if (!v) return '读写工作区';
  const hit = WS_PROP_PRESETS.find((p) => p.value === v || p.label === v);
  return hit ? hit.label : v;
}

/** 属性入库唯一源：缺失/空 → read_write；中文标签 → 机器值；自定义原样 */
function propValue(raw?: string | null): string {
  const v = (raw || '').trim();
  if (!v) return DEFAULT_WS_PROP;
  if (WS_PROP_PRESETS.some((p) => p.value === v)) return v;
  const byLabel = WS_PROP_PRESETS.find((p) => p.label === v);
  return byLabel ? byLabel.value : v;
}

/** 读自定义属性列表（localStorage，失败降级空数组） */
function loadCustomProps(): string[] {
  try {
    const raw = localStorage.getItem(CUSTOM_PROPS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/** 存自定义属性（预设不存、已有不存、FIFO 淘汰、失败静默） */
function saveCustomProp(prop: string): void {
  if (WS_PROP_PRESETS.some((p) => p.value === prop || p.label === prop)) return;
  const list = loadCustomProps();
  if (list.includes(prop)) return;
  list.push(prop);
  if (list.length > MAX_CUSTOM_PROPS) list.shift();
  try {
    localStorage.setItem(CUSTOM_PROPS_KEY, JSON.stringify(list));
  } catch {
    /* 隐私模式/配额满：静默降级，不影响主流程 */
  }
}

export default function SessionWorkspacePanel({
  sessionId,
  open,
  onClose,
}: Props) {
  const [entries, setEntries] = useState<WsDraft[]>([]);
  const [unusable, setUnusable] = useState<UnusableEntry[]>([]);
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

  const wsSnapshot = useSyncExternalStore(
    workspaceStore.subscribe,
    workspaceStore.getSnapshot
  );
  const rejected = wsSnapshot.sessionId === sessionId ? wsSnapshot.notice : [];
  const [loadState, setLoadState] = useState<
    'idle' | 'loading' | 'ready' | 'failed'
  >('idle');
  const dirtyRef = useRef(false);
  const loadSeqRef = useRef(0);

  /** AutoComplete options = 预设 + localStorage 自定义（去重），新增区/编辑区共享 */
  const propOptions = useMemo(() => {
    const base = WS_PROP_PRESETS.map((p) => ({ value: p.value, label: p.label }));
    const extra = loadCustomProps()
      .filter((c) => !WS_PROP_PRESETS.some((p) => p.value === c || p.label === c))
      .map((c) => ({ value: c, label: c }));
    return [...base, ...extra];
  }, []);

  /** 打开即重拉（无暂存：关闭即丢，决策75作废 / 76修订）
   *  ⚠ 失败必须降级并提示，不能让面板空白无反馈（#1 展示是基本要求）
   *  ⚠ 2026-10-30 小欧: 失败时 loadState=failed → 「确定」禁用, 杜绝"空列表覆盖写" */
  const load = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoadState('loading');
    try {
      const r = await sessionApi.getWorkspaces(sessionId);
      if (seq !== loadSeqRef.current) return;
      if (!dirtyRef.current) {
        setEntries(
          r.workspaces.map((w) => ({
            path: w.path,
            workspace_property: propValue(w.workspace_property),
            memo: w.memo || '',
            is_default: Boolean(w.is_default),
          }))
        );
      }
      setUnusable(r.unusable);
      setProjectRoot(r.project_root);
      setAllowedDirs(r.allowed_dirs);
      setInputErr('');
      setEditingPath(null);
      setLoadState('ready');
    } catch {
      if (seq !== loadSeqRef.current) return;
      setUnusable([]);
      setProjectRoot('');
      setAllowedDirs([]);
      setEditingPath(null);
      setLoadState('failed');
      handleError(new Error('读取会话目录失败'));
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

  /** 新增（同路径覆盖属性/memo，不产生重复行） */
  const addEntry = () => {
    const v = input.trim();
    if (!v || !isAbsolute(v)) {
      setInputErr('请输入绝对路径');
      return;
    }
    const p = propValue(propInput);
    const m = memoInput.trim();
    saveCustomProp(p);
    dirtyRef.current = true;
    setEntries((es) =>
      es.some((e) => e.path.toLowerCase() === v.toLowerCase())
        ? es.map((e) =>
            e.path.toLowerCase() === v.toLowerCase()
              ? { ...e, workspace_property: p, memo: m }
              : e
          )
        : [...es, { path: v, workspace_property: p, memo: m, is_default: false }]
    );
    setInput('');
    setPropInput(DEFAULT_WS_PROP);
    setMemoInput('');
    setInputErr('');
  };

  /** 进入编辑态 */
  const startEdit = (e: WsDraft) => {
    setEditingPath(e.path);
    setEditPath(e.path);
    setEditProp(e.workspace_property);
    setEditMemo(e.memo);
    setEditErr('');
  };

  /** 保存编辑：绝对路径 + 同列表去重（改到别的行已占用的路径必须拦住） */
  const saveEdit = () => {
    if (!editingPath) return;
    const v = editPath.trim();
    if (!v || !isAbsolute(v)) {
      setEditErr('请输入绝对路径');
      return;
    }
    const clash = entries.some(
      (e) => e.path !== editingPath && e.path.toLowerCase() === v.toLowerCase()
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
    setEditingPath(null);
  };

  const cancelEdit = () => setEditingPath(null);

  /** 删除（删空二次确认，确认框在 updater 外） */
  const remove = (path: string) => {
    const willEmpty = entries.length === 1 && entries[0].path === path;
    if (willEmpty) {
      Modal.confirm({
        title: '清空目录列表？',
        content:
          '清空后本会话不再有使用目录，产物将退回项目根。磁盘目录不会被删除。',
        okText: '清空',
        cancelText: '取消',
        onOk: () => {
          dirtyRef.current = true;
          setEntries([]);
          setEditingPath(null);
        },
      });
      return;
    }
    dirtyRef.current = true;
    setEntries((es) => es.filter((e) => e.path !== path));
    if (editingPath === path) setEditingPath(null);
  };

  /** 确定 → 本地立即关闭 + 后台提交（不可 await） */
  const confirm = () => {
    if (loadState !== 'ready') return;
    void workspaceStore.commit(
      sessionId,
      entries.map((e) => ({
        path: e.path,
        workspace_property: propValue(e.workspace_property),
        memo: e.memo.trim() || null,
      }))
    );
    onClose();
  };

  return (
    <Modal
      open={open}
      width={settingsModalWidth.display}
      destroyOnHidden
      maskClosable
      okButtonProps={{ disabled: loadState !== 'ready' }}
      title="事项工作区"
      onOk={confirm}
      onCancel={onClose}
      okText="确定"
      cancelText="取消"
    >
      {/* ① 只读区：项目根 + 授权目录，仅显示无增删（决策82） */}
      <div
        style={{
          background: chatTokens.colorPrimaryBg,
          borderRadius: 6,
          padding: Spacing.MD,
          display: 'flex',
          flexDirection: 'column',
          gap: Spacing.XS,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.XS }}>
          <FolderOutlined style={{ color: chatTokens.colorTextSecondary }} />
          <Typography.Text
            style={{
              fontSize: FontSize.SECONDARY,
              color: chatTokens.colorTextSecondary,
              flexShrink: 0,
            }}
          >
            项目根（只读）
          </Typography.Text>
          <Typography.Text
            ellipsis={{ tooltip: projectRoot || '-' }}
            copyable={{ text: projectRoot }}
            style={{ fontSize: FontSize.SECONDARY, flex: 1 }}
          >
            {projectRoot || '-'}
          </Typography.Text>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.XS }}>
          <LockOutlined style={{ color: chatTokens.colorTextSecondary }} />
          <Typography.Text
            style={{
              fontSize: FontSize.SECONDARY,
              color: chatTokens.colorTextSecondary,
              flexShrink: 0,
            }}
          >
            授权目录（只读）
          </Typography.Text>
          <Typography.Text
            ellipsis={{ tooltip: allowedDirs.join('；') || '（未配置）' }}
            copyable={
              allowedDirs.length ? { text: allowedDirs.join('\n') } : false
            }
            style={{ fontSize: FontSize.SECONDARY, flex: 1 }}
          >
            {allowedDirs.length ? allowedDirs.join('；') : '（未配置）'}
          </Typography.Text>
        </div>
      </div>

      {/* ②③ 可用列表 + 不可用置灰列表 */}
      <List
        style={{ marginTop: Spacing.MD }}
        loading={loadState === 'loading'}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="尚未添加目录，进入会话后将自动创建默认目录"
            />
          ),
        }}
        dataSource={[
          ...entries.map((e) => ({
            key: e.path,
            kind: 'ok' as const,
            path: e.path,
            draft: e,
            reason: '',
          })),
          ...unusable.map((u) => ({
            key: `u_${u.path}`,
            kind: 'bad' as const,
            path: u.path,
            draft: null as WsDraft | null,
            reason: u.reason,
          })),
        ]}
        renderItem={(it) => {
          const e = it.draft;
          const editing = !!e && editingPath === e.path;
          return (
            <List.Item
              actions={
                e
                  ? [
                      <Tooltip key="edit" title="编辑该目录">
                        <Button
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => startEdit(e)}
                        />
                      </Tooltip>,
                      <Tooltip key="del" title="移除该目录">
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => remove(e.path)}
                        />
                      </Tooltip>,
                    ]
                  : undefined
              }
            >
              {editing && e ? (
                /* 编辑态：path + 属性 + memo 三字段全可改 */
                <div style={{ width: '100%' }}>
                  <Input
                    value={editPath}
                    placeholder="目录路径"
                    status={editErr ? 'error' : undefined}
                    onChange={(ev) => {
                      setEditPath(ev.target.value);
                      setEditErr('');
                    }}
                    onPressEnter={saveEdit}
                  />
                  {editErr && (
                    <Typography.Text type="danger" style={{ fontSize: FontSize.SECONDARY }}>
                      {editErr}
                    </Typography.Text>
                  )}
                  <Space.Compact style={{ width: '100%', marginTop: 6 }}>
                    <AutoComplete
                      value={editProp}
                      options={propOptions}
                      onChange={setEditProp}
                      style={{ flex: 1 }}
                      placeholder="工作区属性"
                    />
                    <Input
                      value={editMemo}
                      placeholder="备注（可选）"
                      onChange={(ev) => setEditMemo(ev.target.value)}
                      onPressEnter={saveEdit}
                      style={{ flex: 1 }}
                    />
                  </Space.Compact>
                  <Space style={{ marginTop: 6 }}>
                    <Button type="primary" size="small" onClick={saveEdit}>
                      保存
                    </Button>
                    <Button size="small" onClick={cancelEdit}>
                      取消
                    </Button>
                  </Space>
                </div>
              ) : e ? (
                /* 展示态：path + 属性 Tag + memo + 默认标记 */
                <Space size={Spacing.XS} style={{ width: '100%' }}>
                  <Typography.Text
                    ellipsis={{ tooltip: e.path }}
                    style={{ fontSize: FontSize.SECONDARY, flex: 1 }}
                  >
                    {e.path}
                  </Typography.Text>
                  {e.is_default && <Tag color="gold">默认</Tag>}
                  <Tag color={PROP_COLORS[propValue(e.workspace_property)] || 'default'}>
                    {propLabel(e.workspace_property)}
                  </Tag>
                  {e.memo && (
                    <Typography.Text
                      type="secondary"
                      ellipsis={{ tooltip: e.memo }}
                      style={{ fontSize: FontSize.SECONDARY }}
                    >
                      {e.memo}
                    </Typography.Text>
                  )}
                </Space>
              ) : (
                /* 不可用项：原 path + 原因，置灰，无编辑/删除 */
                <>
                  <Typography.Text
                    type="secondary"
                    delete
                    ellipsis={{ tooltip: it.path }}
                    style={{ fontSize: FontSize.SECONDARY }}
                  >
                    {it.path}
                  </Typography.Text>
                  <Typography.Text
                    type="secondary"
                    style={{ marginLeft: Spacing.XS, fontSize: FontSize.SECONDARY }}
                  >
                    {it.reason}
                  </Typography.Text>
                </>
              )}
            </List.Item>
          );
        }}
      />

      {/* 取数失败: 明确告知"暂不能保存"并给重试入口 */}
      {loadState === 'failed' && (
        <div
          style={{
            marginTop: Spacing.SM,
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.SM,
          }}
        >
          <Typography.Text
            type="secondary"
            style={{ fontSize: FontSize.SECONDARY, flex: 1 }}
          >
            目录读取失败，暂不能保存（避免用空列表覆盖已有目录），请重试。
          </Typography.Text>
          <Button size="small" onClick={() => void load()}>
            重试
          </Button>
        </div>
      )}

      {/* 新增输入区：两行 = 路径 + 属性AutoComplete / 备注 + 添加按钮 */}
      <Space.Compact style={{ width: '100%', marginTop: Spacing.SM }}>
        <Input
          style={{ flex: 1 }}
          placeholder="添加已有目录…（绝对路径）"
          status={inputErr ? 'error' : undefined}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setInputErr('');
          }}
          onPressEnter={addEntry}
        />
        <AutoComplete
          value={propInput}
          options={propOptions}
          onChange={setPropInput}
          style={{ width: 130 }}
          placeholder="属性"
        />
      </Space.Compact>
      <Space.Compact style={{ width: '100%', marginTop: 4 }}>
        <Input
          style={{ flex: 1 }}
          placeholder="备注（可选，如：后端源码、产物输出、别碰 legacy）"
          value={memoInput}
          onChange={(e) => setMemoInput(e.target.value)}
          onPressEnter={addEntry}
        />
        <Button
          icon={<PlusOutlined />}
          onClick={addEntry}
          aria-label="添加目录"
        >
          添加
        </Button>
      </Space.Compact>
      {inputErr && (
        <Typography.Text
          style={{ fontSize: FontSize.SECONDARY, color: chatTokens.colorError }}
        >
          {inputErr}
        </Typography.Text>
      )}

      {/* 被拒留痕：自动清除的条目在此可回看 */}
      {rejected.length > 0 && (
        <div
          style={{
            marginTop: Spacing.SM,
            padding: Spacing.SM,
            border: `1px dashed ${chatTokens.colorBorder}`,
            borderRadius: 6,
          }}
        >
          <Typography.Text
            style={{
              fontSize: FontSize.SECONDARY,
              color: chatTokens.colorError,
            }}
          >
            上次保存以下 {rejected.length}{' '}
            项目录被后端拒绝（整单拒绝，本次全部未写入）。磁盘目录不受影响，
            请修正后再次点击「确定」：
          </Typography.Text>
          {rejected.map((r) => (
            <div
              key={r.path}
              style={{
                fontSize: FontSize.SECONDARY,
                color: chatTokens.colorTextSecondary,
              }}
            >
              · {r.path} —— {r.reason}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
