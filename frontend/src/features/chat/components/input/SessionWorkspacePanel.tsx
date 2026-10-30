/**
 * SessionWorkspacePanel - 会话使用的目录面板（）
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
 */
import {
  useCallback,
  useEffect,
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
} from 'antd';
import {
  DeleteOutlined,
  PlusOutlined,
  FolderOutlined,
  LockOutlined,
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

export default function SessionWorkspacePanel({
  sessionId,
  open,
  onClose,
}: Props) {
  const [paths, setPaths] = useState<string[]>([]);
  const [unusable, setUnusable] = useState<UnusableEntry[]>([]);
  const [projectRoot, setProjectRoot] = useState('');
  const [allowedDirs, setAllowedDirs] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [inputErr, setInputErr] = useState('');
  // 2026-10-10 小欧: 被拒条目留痕（#3"提示"要能回看，toast 一闪而过不够）
  // 2026-10-30 18:36:36 小欧 - 留痕上移到 workspaceStore.notice：提交已与关闭解耦，
  //   组件内部 state 活不到下一次打开（面板 destroyOnHidden），只能存在组件之外。
  const wsSnapshot = useSyncExternalStore(
    workspaceStore.subscribe,
    workspaceStore.getSnapshot
  );
  const rejected = wsSnapshot.sessionId === sessionId ? wsSnapshot.notice : [];
  // 2026-10-30 小欧 - 服务端清单装载态: 只有 ready 才允许「确定」覆盖写(其余状态写库=盲写)
  const [loadState, setLoadState] = useState<
    'idle' | 'loading' | 'ready' | 'failed'
  >('idle');
  // 2026-10-30 小欧 - 用户是否已改动草稿: 改动后, 迟到的 GET 结果不许覆盖列表
  const dirtyRef = useRef(false);
  // 2026-10-30 小欧 - 代际守卫: 关闭/切会话/重试即作废在飞请求, 迟到结果不许写回
  const loadSeqRef = useRef(0);

  /** 打开即重拉（无暂存：关闭即丢，决策75作废 / 76修订）
   *  ⚠ 失败必须降级并提示，不能让面板空白无反馈（#1 展示是基本要求）
   *  ⚠ 2026-10-30 小欧: 失败时 loadState=failed → 「确定」禁用, 杜绝"空列表覆盖写" */
  const load = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoadState('loading');
    try {
      const r = await sessionApi.getWorkspaces(sessionId);
      if (seq !== loadSeqRef.current) return; // 已被关闭/重试作废
      // 用户已动过草稿就不再灌入(否则刚添加的目录被冲掉); 只读区/不可用列表是服务端事实, 照常更新
      if (!dirtyRef.current) setPaths(r.workspaces.map((w) => w.path));
      setUnusable(r.unusable);
      setProjectRoot(r.project_root); // 只读区（决策82）
      setAllowedDirs(r.allowed_dirs); // 只读区（决策82）
      setInputErr('');
      setLoadState('ready');
    } catch {
      if (seq !== loadSeqRef.current) return;
      setUnusable([]);
      setProjectRoot('');
      setAllowedDirs([]);
      setLoadState('failed');
      handleError(new Error('读取会话目录失败'));
    }
  }, [sessionId]);

  // 2026-10-30 小欧 - 取数只认 open/sessionId: 不再依赖开启动画回调(动画回调在重负载下不可靠)
  useEffect(() => {
    if (!open || !sessionId) return;
    dirtyRef.current = false; // 每次打开以服务端为基线
    void load();
    return () => {
      loadSeqRef.current += 1; // 关闭/切换: 作废在飞请求
    };
  }, [open, sessionId, load]);

  const addInput = () => {
    const v = input.trim();
    if (!v || !isAbsolute(v)) {
      setInputErr('请输入绝对路径');
      return;
    }
    setInputErr('');
    dirtyRef.current = true;
    setPaths((ps) => (ps.includes(v) ? ps : [...ps, v]));
    setInput('');
  };

  /** 删除条目（决策78 的本意是"语义突变的操作要确认"：删空列表会退回项目根兜底）
   *  ⚠ v2.0 已删 is_default 字段，后端不告知"哪条是默认目录"，不按行猜测，
   *    改按**操作后果**判定。⚠ 确认框必须在 updater 之外（StrictMode 双调用 updater，
   *    放里面会弹两次；updater 必须是纯函数） */
  const remove = (p: string) => {
    // 先读后写：事件处理函数里读 paths 是安全的（updater 里读才有竞态）
    const willEmpty = paths.length === 1 && paths[0] === p;
    if (willEmpty) {
      Modal.confirm({
        title: '清空目录列表？',
        content:
          '清空后本会话不再有使用目录，产物将退回项目根。磁盘目录不会被删除。',
        okText: '清空',
        cancelText: '取消',
        onOk: () => {
          dirtyRef.current = true;
          setPaths([]);
        },
      });
      return; // 确认前不真的清空
    }
    dirtyRef.current = true;
    setPaths((ps) => ps.filter((x) => x !== p));
  };

  /** 确定 → 关闭与保存彻底分离（三条路，见 services/sessionWorkspaceStore 头注）
   *  2026-10-30 18:36:36 小欧 - 原实现 `await patchWorkspaces()` 成功才 onClose：一次请求排队 /
   *  后端被在跑任务占满，弹窗就一直转圈不消失（axios 60s 超时后仍停在原地）。
   *  改为：本地立即关闭，列表交 workspaceStore 后台提交并裁决结果（200=落地 / 422=逐条点名+留痕 /
   *  其他=全局错误通道+对账），失败也不回弹面板（不制造"弹窗自己弹回来"）。 */
  const confirm = () => {
    // 没拿到服务端清单就覆盖写 = 用空列表清空会话目录，直接拦（不静默丢数据）
    if (loadState !== 'ready') return;
    void workspaceStore.commit(sessionId, paths);
    onClose();
  };

  return (
    <Modal
      open={open}
      width={settingsModalWidth.display}
      destroyOnHidden
      maskClosable
      // 2026-10-30 18:36:36 小欧 - 去掉 confirmLoading：保存已不在弹窗内等待，
      //   按钮不再有"转圈到超时"的中间态（关闭由本地一次点击立即完成）
      // 2026-10-30 小欧 - 未拿到服务端清单(listing 未就绪)一律不许覆盖写
      okButtonProps={{ disabled: loadState !== 'ready' }}
      title="事项工作区"
      onOk={confirm}
      onCancel={onClose}
      okText="确定"
      cancelText="取消"
    >
      {/* ① 只读区：项目根 + 授权目录，仅显示无增删（决策82）
       *  2026-10-10 小欧 UI优化：分行独立 + 长路径省略可复制，不挤版 */}
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
          // 2026-10-10 小欧 UI优化：空态用 Empty 组件（有图标有留白，不空空白框）
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="尚未添加目录，进入会话后将自动创建默认目录"
            />
          ),
        }}
        dataSource={[
          ...paths.map((p) => ({ key: p, path: p, reason: '' })),
          ...unusable.map((u) => ({
            key: `u_${u.path}`,
            path: u.path,
            reason: u.reason,
          })),
        ]}
        renderItem={(it) => {
          const isUnusable = it.reason !== '';
          return (
            <List.Item
              actions={
                isUnusable
                  ? undefined // 不可用项不给删除键，防误操作
                  : [
                      // 2026-10-10 小欧 UI优化：Tooltip hover 反馈 + text 按钮原生 hover 态
                      <Tooltip key="del" title="移除该目录">
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => remove(it.path)}
                        />
                      </Tooltip>,
                    ]
              }
            >
              <List.Item.Meta
                title={
                  // 2026-10-10 小欧 UI优化：长路径省略 + hover 现全路径，× 不会被挤掉
                  <Typography.Text
                    ellipsis={{ tooltip: it.path }}
                    style={{
                      fontSize: FontSize.SECONDARY,
                      color: isUnusable
                        ? chatTokens.colorTextSecondary
                        : chatTokens.colorText,
                    }}
                  >
                    {it.path}
                  </Typography.Text>
                }
                description={
                  // 2026-10-10 小欧: v2.0 已删 is_default 字段，后端不告知"哪条是默认目录"，
                  //   故不渲染"默认"标签（原先用 paths[0] 猜是错的，会随排序失效）
                  isUnusable ? (
                    <Typography.Text
                      type="secondary"
                      style={{ fontSize: FontSize.SECONDARY }}
                    >
                      {it.reason}
                    </Typography.Text>
                  ) : null
                }
              />
            </List.Item>
          );
        }}
      />

      {/* 2026-10-30 小欧 - 取数失败: 明确告知"暂不能保存"并给重试入口, 不放任盲写 */}
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

      {/* ④ 输入区：格式校验在前，不发请求
          2026-10-10 小欧 UI优化：按钮只留图标（不挤），输入框独占余宽 */}
      <Space.Compact style={{ width: '100%' }}>
        <Input
          style={{ flex: 1 }}
          placeholder="添加已有目录…（绝对路径）"
          status={inputErr ? 'error' : undefined}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setInputErr('');
          }}
          onPressEnter={addInput}
        />
        <Button
          icon={<PlusOutlined />}
          onClick={addInput}
          aria-label="添加目录"
        />
      </Space.Compact>
      {inputErr && (
        <Typography.Text
          style={{ fontSize: FontSize.SECONDARY, color: chatTokens.colorError }}
        >
          {inputErr}
        </Typography.Text>
      )}

      {/* 被拒留痕（#3）：自动清除的条目在此可回看，不靠一闪而过的 toast
          2026-10-10 小欧 UI优化：中性虚线框（colorBorder）降噪，标题行保留 colorError */}
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
