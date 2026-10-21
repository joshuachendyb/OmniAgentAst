// 编辑历史: 2026-10-21 小杨 - 新建文件足迹面板；改为**右栏下方折叠区**（rightBottom slot）；
//   加载态由 Empty 假冒改 Skeleton；行内嵌 button 的 a11y 冲突修正（行只作鼠标热区，
//   键盘目标收敛为「文件名=打开」「引用=引用」两个真 button）；引用不再跳页（就地收集）— 小杨-2026-10-21
//   2026-10-21 小杨 - 修复：时间字段由 last_seen_at 改用 mtime（后端值一直是文件系统 mtime，
//     旧名会让面板误标"最近访问时间"）— 小杨-2026-10-21
//   2026-10-21 小欧 - 足迹自动刷新：订阅会话快照，步骤数变化即重取（去抖 600ms）；
//     原实现只在挂载时取一次 → Agent 动过新文件后面板仍停在挂载时刻 — 小欧-2026-10-21
/**
 * FileTrailPanel —— 本会话 Agent 动过的文件
 *
 * 与树上的 `●` 标记**同源同型**：同一份数据（`/files/recent-files`）、同一渲染口径，
 *   区别只是"面板是 ● 的列表化"。
 *
 * 数据取数：走共享 hook `useRecentFiles`（模块级缓存）—— 与文件页的树 ● 同源，
 *   同一 sessionId 只发一次请求（避免同一会话触发多次相同请求）。
 *
 * 只读边界：面板**不落任何写操作**（与文件页同一常驻表达）。
 */
import React, { useEffect, useState } from 'react';
import { Empty, Skeleton, Tooltip } from 'antd';
import {
  CaretRightOutlined,
  FileOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import { fileApi, type RecentFile } from '@/services/api/file.api';
import { composerRefStore, newRefId } from '../../streams/composerRefStore';
import { chatStreamStore } from '../../streams/chatStreamStore';
import { useRecentFiles } from '@/hooks/useRecentFiles';
import { buildFileDeepLink } from '@/utils/fileDeepLink';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
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

/** 折叠偏好（跨会话继承；默认展开，有数据时用户第一眼就能看到） */
const EXPAND_KEY = 'file_trail_expanded';
const readExpanded = (): boolean => localStorage.getItem(EXPAND_KEY) !== '0';

export interface FileTrailPanelProps {
  sessionId?: string | null;
}

export const FileTrailPanel: React.FC<FileTrailPanelProps> = ({
  sessionId,
}) => {
  const { files, loading, reload } = useRecentFiles(sessionId);
  const [expanded, setExpanded] = useState(readExpanded);

  /**
   * 2026-10-21 小欧 - 足迹**自动刷新**：
   *   原实现只在挂载时取一次 → 会话里 Agent 动过新文件后，本面板仍停在挂载那一刻的内容
   *   （useRecentFiles 无自动失效，只有文件页工具条显式 reload 才刷新）。
   *   触发源取会话快照的**步骤数**：步骤推进 = 可能动过文件；心跳等无关变更不触发。
   *   去抖 600ms（步骤成簇到达，逐条重取会打出一串请求）。
   */
  useEffect(() => {
    if (!sessionId) return;
    let last =
      chatStreamStore.getSnapshot(sessionId)?.executionSteps?.length ?? 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsub = chatStreamStore.subscribe(sessionId, () => {
      const n =
        chatStreamStore.getSnapshot(sessionId)?.executionSteps?.length ?? 0;
      if (n === last) return;
      last = n;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        void reload();
      }, 600);
    });
    return () => {
      unsub();
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, reload]);

  const toggle = () => {
    setExpanded((v) => {
      const next = !v;
      localStorage.setItem(EXPAND_KEY, next ? '1' : '0');
      return next;
    });
  };

  /**
   * 引用到对话：**就地收集**（2026-10-21 小杨）
   *   本面板就在会话页上，ChatInput 通过 composerRefStore 订阅自动消费 → 无需再 nav
   *   （原实现 nav 到同一路由 → query 变化触发会话切换，属无意义的路由扰动）。
   */
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
      showSuccess(`已引用「${f.name}」到对话`);
    } catch {
      // 10.0.1.1 复用优先/showMessage 统一错误通道：引用失败必须提示，不静默
      showMessage(ErrorType.FILE_READ, '引用内容读取失败，请重试');
    }
  };

  // 2026-10-21 小杨 - **加载态不用 Empty 假冒**（Empty 语义是"没有内容"，
  //   用在加载中会让用户判定"这里没东西"而离开）→ 用骨架屏表达"正在读"。
  if (!sessionId) return <Empty description="无会话" />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* 折叠区头：常驻（收起时也能看到"有多少"），点击展开/收起 */}
      <button
        type="button"
        onClick={toggle}
        aria-expanded={expanded}
        aria-controls="file-trail-body"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.XS,
          width: '100%',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: `${Spacing.SM}px ${Spacing.LG}px`,
          color: Colors.TEXT.STRONG,
          fontSize: chatTokens.fontMD,
          textAlign: 'left',
        }}
      >
        <CaretRightOutlined
          style={{ fontSize: 10 }}
          rotate={expanded ? 90 : 0}
        />
        文件足迹
        <span
          style={{ color: Colors.TEXT.SECONDARY, fontSize: chatTokens.fontSM }}
        >
          {loading && files.length === 0 ? '' : files.length}
        </span>
        <span
          style={{
            marginLeft: 'auto',
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
          }}
        >
          {expanded ? '收起' : '展开'}
        </span>
      </button>

      {expanded && (
        <div
          id="file-trail-body"
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            padding: `0 ${Spacing.LG}px ${Spacing.MD}px`,
          }}
        >
          <div
            style={{
              fontSize: chatTokens.fontSM,
              color: Colors.TEXT.SECONDARY,
              marginBottom: Spacing.SM,
            }}
          >
            本会话中 Agent 读写过的文件 · 点文件名打开，点「引用」加入本轮对话
          </div>
          {loading && files.length === 0 ? (
            <Skeleton active paragraph={{ rows: 3 }} title={false} />
          ) : files.length === 0 ? (
            <div
              style={{
                fontSize: chatTokens.fontSM,
                color: Colors.TEXT.SECONDARY,
              }}
            >
              本会话 Agent 还没有读写过文件
            </div>
          ) : (
            files.map((f) => (
              <div
                key={f.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: Spacing.SM,
                  padding: `${Spacing.XS}px 0`,
                }}
              >
                <FileOutlined
                  style={{ color: Colors.PRIMARY, flexShrink: 0 }}
                />
                {/* 键盘目标①：文件名 = 打开文件（真 button，避免"行 role=button 内嵌 button"的语义冲突） */}
                <Tooltip title={f.path}>
                  <button
                    type="button"
                    /* 2026-10-21 小杨 - **新标签打开**
                       SPA 跳转会丢会话页的滚动/展开状态；深链路径是 SPA 路由, 新标签直达文件页=定位 */
                    onClick={() =>
                      window.open(buildFileDeepLink(f.path), '_blank')
                    }
                    style={{
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      padding: 0,
                      color: Colors.TEXT.PRIMARY,
                      textAlign: 'left',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {f.name}
                  </button>
                </Tooltip>
                {/* ops 徽标**只显前 2 个**，其余折叠为 +N（真实取值域 16 个工具名） */}
                {(f.ops ?? []).slice(0, 2).map((op) => (
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
                {(f.ops ?? []).length > 2 && (
                  <span
                    style={{
                      color: Colors.TEXT.WEAK,
                      fontSize: chatTokens.fontSM,
                    }}
                  >
                    +{(f.ops ?? []).length - 2}
                  </span>
                )}
                <span
                  title="文件最后修改时间"
                  style={{
                    color: Colors.TEXT.SECONDARY,
                    fontSize: chatTokens.fontSM,
                    marginLeft: 'auto',
                  }}
                >
                  {f.mtime}
                </span>
                {/* 键盘目标②：引用（常驻可见，触屏可达） */}
                <button
                  type="button"
                  onClick={() => void sendAsRef(f)}
                  title="引用到对话"
                  aria-label={`把 ${f.name} 引用到对话`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: Colors.PRIMARY,
                    fontSize: chatTokens.fontSM,
                    padding: '2px 4px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <PaperClipOutlined /> 引用
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
