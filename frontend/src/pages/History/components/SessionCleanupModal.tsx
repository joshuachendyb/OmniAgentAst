// 编辑历史: 2026-11-18 小欧 - 历史页批量清理弹窗: 预览→确认两段式, 在跑任务跳过提示,
//   天数可选 7/10/30/90 默认 30, 执行后回调清理 Store 与刷新列表 — 小欧-2026-11-18
import { useEffect, useState } from 'react';
import { Alert, Checkbox, Modal, Select, Spin, Tag, Typography } from 'antd';
import {
  sessionApi,
  type SessionCleanupMode,
  type SessionCleanupPreview,
} from '@/services/api/session.api';
import { handleError, showSuccess } from '@/services/error/handler';

const DAY_OPTIONS = [7, 10, 30, 90];

interface SessionCleanupModalProps {
  open: boolean;
  mode: SessionCleanupMode;
  onCancel: () => void;
  onDone: (deletedIds: string[]) => void;
}

/**
 * 历史页批量清理弹窗 — 破坏性操作两段式(先预览命中数/样例, 勾选后执行)。
 * 两种模式共用本组件, mode 由入口按钮决定(days 仅 older 模式有意义)。
 */
export const SessionCleanupModal = ({
  open,
  mode,
  onCancel,
  onDone,
}: SessionCleanupModalProps) => {
  const [days, setDays] = useState(30);
  const [preview, setPreview] = useState<SessionCleanupPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setConfirmed(false);
    setPreview(null);
    sessionApi
      .previewCleanupSessions(mode, days)
      .then((p) => {
        if (!cancelled) setPreview(p);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError('预览失败，请稍后重试');
          handleError(e);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, mode, days]);

  const execute = async () => {
    if (!preview || preview.count === 0 || !confirmed) return;
    setExecuting(true);
    try {
      const result = await sessionApi.cleanupSessions(mode, days);
      showSuccess(`已清理 ${result.deleted} 个会话`);
      onDone(result.session_ids);
    } catch (e) {
      handleError(e);
      setError('清理失败，请稍后重试');
    } finally {
      setExecuting(false);
    }
  };

  const isInvalid = mode === 'invalid';
  const cutoffText = preview?.cutoff
    ? new Date(preview.cutoff).toLocaleString('zh-CN')
    : '';

  return (
    <Modal
      open={open}
      title={isInvalid ? '清理空壳会话' : '清理旧会话'}
      okText={isInvalid ? '确认清理空壳会话' : '确认清理旧会话'}
      cancelText="取消"
      okButtonProps={{
        danger: true,
        loading: executing,
        disabled: loading || !preview || preview.count === 0 || !confirmed,
      }}
      onOk={() => void execute()}
      onCancel={onCancel}
      width={560}
    >
      <Typography.Paragraph type="secondary">
        {isInvalid
          ? '空壳会话 = 没有任何用户消息、也没有任何任务的会话。'
          : '旧会话 = 最后一次活动早于所选天数之前的会话。'}
      </Typography.Paragraph>
      {!isInvalid && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ marginRight: 8 }}>时间阈值：</span>
          <div style={{ display: 'inline-block' }} data-testid="cleanup-days">
            <Select
              value={days}
              onChange={setDays}
              options={DAY_OPTIONS.map((d) => ({
                value: d,
                label: `${d} 天前`,
              }))}
              style={{ width: 140 }}
            />
          </div>
        </div>
      )}
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}
      <div data-testid="cleanup-preview">
        {loading ? (
          <Spin />
        ) : preview ? (
          <>
            <Alert
              type={preview.count > 0 ? 'warning' : 'success'}
              showIcon
              message={
                <span data-testid="cleanup-preview-count">
                  预计清理 {preview.count} 个会话
                  {!isInvalid && cutoffText ? `（${cutoffText} 之前）` : ''}
                </span>
              }
              description={
                <div>
                  {preview.skipped_active > 0 && (
                    <div>
                      跳过 {preview.skipped_active} 个有运行中任务的会话。
                    </div>
                  )}
                  {preview.sample_titles.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      样例：
                      {preview.sample_titles.map((title) => (
                        <Tag key={title}>{title}</Tag>
                      ))}
                    </div>
                  )}
                </div>
              }
            />
            {preview.count === 0 && (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                没有符合清理条件的会话。
              </Typography.Paragraph>
            )}
          </>
        ) : null}
      </div>
      <Checkbox
        checked={confirmed}
        onChange={(e) => setConfirmed(e.target.checked)}
        style={{ marginTop: 12 }}
        disabled={!preview || preview.count === 0}
      >
        我已确认要软删除以上会话（界面不可恢复）
      </Checkbox>
    </Modal>
  );
};
