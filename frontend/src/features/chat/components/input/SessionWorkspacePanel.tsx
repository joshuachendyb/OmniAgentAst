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
 */
import { useState } from 'react';
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
import { showMessage, handleError, ErrorType } from '@/services/error/handler';
import type { UnusableEntry } from '@/types/chat';

interface Props {
  sessionId: string;
  open: boolean;
  onClose: () => void;
  onSaved: (list: { path: string }[]) => void;
}

/** 只做绝对路径格式校验；存在性与禁区交后端判（决策74，避免前端造禁区表） */
const isAbsolute = (p: string) => /^[A-Za-z]:[\\/]/.test(p) || /^\\\\/.test(p);

export default function SessionWorkspacePanel({
  sessionId,
  open,
  onClose,
  onSaved,
}: Props) {
  const [paths, setPaths] = useState<string[]>([]);
  const [unusable, setUnusable] = useState<UnusableEntry[]>([]);
  const [projectRoot, setProjectRoot] = useState('');
  const [allowedDirs, setAllowedDirs] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [inputErr, setInputErr] = useState('');
  // 2026-10-10 小欧: 被拒条目留痕（#3"提示"要能回看，toast 一闪而过不够）
  const [rejected, setRejected] = useState<{ path: string; reason: string }[]>(
    []
  );
  const [saving, setSaving] = useState(false);

  /** 打开即重拉（无暂存：关闭即丢，决策75作废 / 76修订）
   *  ⚠ 失败必须降级为空列表并提示，不能让面板空白无反馈（#1 展示是基本要求） */
  const load = async () => {
    try {
      const r = await sessionApi.getWorkspaces(sessionId);
      setPaths(r.workspaces.map((w) => w.path));
      setUnusable(r.unusable);
      setProjectRoot(r.project_root); // 只读区（决策82）
      setAllowedDirs(r.allowed_dirs); // 只读区（决策82）
      setInput('');
      setInputErr('');
      setRejected([]); // 重新打开清掉上轮留痕
    } catch {
      setPaths([]);
      setUnusable([]);
      setProjectRoot('');
      setAllowedDirs([]);
      handleError(new Error('读取会话目录失败'));
    }
  };

  const addInput = () => {
    const v = input.trim();
    if (!v || !isAbsolute(v)) {
      setInputErr('请输入绝对路径');
      return;
    }
    setInputErr('');
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
        onOk: () => setPaths([]),
      });
      return; // 确认前不真的清空
    }
    setPaths((ps) => ps.filter((x) => x !== p));
  };

  /** 确定 → PATCH；422 被拒条目自动摘除 + 逐条提示（决策81） */
  const confirm = async () => {
    setSaving(true);
    try {
      await sessionApi.patchWorkspaces(sessionId, paths);
      onSaved(paths.map((p) => ({ path: p })));
      onClose();
    } catch (e: unknown) {
      // 422 信封：{success:false, error:{workspace_rejected:[{path,reason}]}}（全局异常处理器包装）
      const rejected =
        (
          e as {
            response?: { data?: { error?: { workspace_rejected?: unknown } } };
          }
        )?.response?.data?.error?.workspace_rejected ?? [];
      const items = rejected as { path: string; reason: string }[];
      if (items.length) {
        const bad = new Set(items.map((x) => x.path));
        setPaths((ps) => ps.filter((p) => !bad.has(p))); // 自动清除，不入库
        setRejected(items); // 留痕：toast 一闪而过，列表内要能回看丢了什么
        items.forEach((x) =>
          // 统一错误通道：走 showMessage（查表+去重+分级），禁自造 notify/裸调 message
          showMessage(ErrorType.WORKSPACE_REJECTED, `${x.path}：${x.reason}`)
        );
      } else {
        throw e; // 非 422 业务错交全局 handler
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      width={settingsModalWidth.display}
      destroyOnHidden
      maskClosable
      confirmLoading={saving}
      title="会话事务空间"
      onOk={confirm}
      onCancel={onClose}
      okText="确定"
      cancelText="取消"
      afterOpenChange={(visible) => {
        if (visible) void load();
      }}
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
            以下 {rejected.length}{' '}
            项已被移除，未存入会话目录表（后端整单拒绝，其余条目也尚未保存，
            请确认后再次点击「确定」）：
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
