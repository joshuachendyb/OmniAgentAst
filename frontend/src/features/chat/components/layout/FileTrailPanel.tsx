// 编辑历史: 2026-10-21 小杨 - 文档[28] 8.2/9.10 新建：文件足迹面板（FT1） — 小杨-2026-10-21
/**
 * FileTrailPanel —— 本会话 Agent 动过的文件（FT1）
 *
 * 与树上的 `●`（T3）**同源同型**：同一份数据（`/files/recent-files`）、同一渲染口径，
 *   区别只是"面板是 ● 的列表化"。
 *
 * 数据取数：走共享 hook `useRecentFiles`（模块级缓存）—— 与文件页的树 ● 同源，
 *   同一 sessionId 只发一次请求（避免同一会话触发 3 次相同请求，见文档[28] 10.2 S1-9）。
 *
 * 只读边界：面板**不落任何写操作**（与文件页 S3 同一常驻表达）。
 */
import React from 'react';
import { Empty, Tooltip } from 'antd';
import { FileOutlined, PaperClipOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { fileApi, type RecentFile } from '@/services/api/file.api';
import { composerRefStore, newRefId } from '../../streams/composerRefStore';
import { useRecentFiles } from '@/hooks/useRecentFiles';
import { buildFileDeepLink } from '@/utils/fileDeepLink';
import { showMessage, ErrorType } from '@/services/error/handler';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';

/**
 * ops 徽标配色/文案 —— ops 的取值域是后端工具**注册名**（FILE_OPERATION_TOOLS，16 个），
 *   故这里只给高频三类着色，其余走弱色原名兜底（前端不自造工具分类）。
 */
const OP_COLOR: Record<string, string> = {
  read: Colors.PRIMARY,
  write: Colors.SUCCESS,
  edit: Colors.WAIT_ACTION,
};
const OP_LABEL: Record<string, string> = {
  read: '读',
  write: '写',
  edit: '改',
};

export interface FileTrailPanelProps {
  sessionId?: string | null;
}

export const FileTrailPanel: React.FC<FileTrailPanelProps> = ({
  sessionId,
}) => {
  const nav = useNavigate();
  const { files, loading } = useRecentFiles(sessionId);

  /** hover 动作：现场重读正文 → push 引用 → 回输入框（与 F4 三途径等价） */
  const sendAsRef = async (f: RecentFile) => {
    try {
      const r = await fileApi.readFile(f.path);
      composerRefStore.push({
        id: newRefId(),
        kind: 'file',
        label: f.name,
        path: f.path,
        content: r.content,
        size: r.size,
      });
      nav(`/?session_id=${encodeURIComponent(sessionId ?? '')}`);
    } catch {
      // 10.0.1.1 复用优先/showMessage 统一错误通道：hover 发送失败必须提示，不静默
      showMessage(ErrorType.FILE_READ, '引用内容读取失败，请重试');
    }
  };

  if (!sessionId) return <Empty description="无会话" />;
  if (loading && files.length === 0)
    return <Empty description="正在读取本会话的文件足迹…" />;
  if (files.length === 0)
    return <Empty description="本会话 Agent 还没有读写过文件" />;

  return (
    <div style={{ padding: Spacing.MD }}>
      {files.map((f) => (
        <Tooltip key={f.path} title={f.path}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.SM,
              padding: `${Spacing.XS}px 0`,
              cursor: 'pointer',
            }}
            tabIndex={0}
            onClick={() => nav(buildFileDeepLink(f.path))}
          >
            <FileOutlined style={{ color: Colors.PRIMARY, flexShrink: 0 }} />{' '}
            <span style={{ color: Colors.TEXT.PRIMARY }}>{f.name}</span>
            {(f.ops ?? []).map((op) => (
              <span
                key={op}
                style={{
                  color: OP_COLOR[op] ?? Colors.TEXT.WEAK,
                  fontSize: chatTokens.fontSM,
                }}
              >
                {OP_LABEL[op] ?? op}
              </span>
            ))}
            <span
              style={{
                color: Colors.TEXT.SECONDARY,
                fontSize: chatTokens.fontSM,
                marginLeft: 'auto',
              }}
            >
              {f.last_seen_at}
            </span>
            <span
              style={{
                color: Colors.PRIMARY,
                fontSize: chatTokens.fontSM,
                whiteSpace: 'nowrap',
              }}
              onMouseDown={(e) => {
                e.stopPropagation();
                void sendAsRef(f);
              }}
            >
              <PaperClipOutlined style={{ marginRight: 4 }} /> 作为引用发送
            </span>
          </div>
        </Tooltip>
      ))}
    </div>
  );
};
