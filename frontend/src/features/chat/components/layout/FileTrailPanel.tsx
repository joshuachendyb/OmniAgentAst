// 编辑历史: 2026-10-21 小杨 - 新建文件足迹面板；改为**右栏下方折叠区**（rightBottom slot）；
//   加载态由 Empty 假冒改 Skeleton；行内嵌 button 的 a11y 冲突修正（行只作鼠标热区，
//   键盘目标收敛为「文件名=打开」「引用=引用」两个真 button）；引用不再跳页（就地收集）— 小杨-2026-10-21
//   2026-10-21 小杨 - 修复：时间字段由 last_seen_at 改用 mtime（后端值一直是文件系统 mtime，
//     旧名会让面板误标"最近访问时间"）— 小杨-2026-10-21
//   2026-10-21 小欧 - 足迹自动刷新：订阅会话快照，步骤数变化即重取（去抖 600ms）；
//     原实现只在挂载时取一次 → Agent 动过新文件后面板仍停在挂载时刻 — 小欧-2026-10-21
//   2026-10-21 小杨 - 引用按钮仅文本文件显示（图片由查看器处理，文本通道不读取）— 小杨-2026-10-21
//   2026-10-21 小欧 - 导出 OP_LABEL/OP_COLOR：ops 徽标映射口径易被改坏，导出供测试断言 — 小欧-2026-10-21
//   2026-10-22 小欧 - 将说明文字 "本会话中 Agent 读写过的文件..." 移到标题 "文件足迹" 同一行 — 小欧-2026-10-22
//   2026-10-22 小欧 - 移除文件名 Tooltip：f.name 仅文件名不含路径，一个文件一行可完整显示，悬停提示冗余 — 小欧-2026-10-22
//   2026-10-23 小欧 - 行内改显全路径 f.path（北京老陈要求）：不截断、超宽折行（wordBreak+pre-wrap），
//     去 ellipsis/nowrap；同名不同目录的文件靠路径可区分 — 小欧-2026-10-23
//   2026-10-23 小欧 - 目录深链补尾分隔符：Files 页以尾分隔符判定目录，避免外部目录被误当文件预览 — 小欧-2026-10-23
//   2026-10-24 小欧 - 点文件路径改 SPA 导航（useOptionalNavigate），不再新标签页打开；与正文 PathLink/FileRefChip 对齐 — 小欧-2026-10-24
//   2026-10-30 小欧 - 引用提示统一走 quoteWithToast(成功/超限/读取失败三分支唯一实现): 原实现漏 too_many 分支,
//     超上限被报成"读取失败", 用户会去检查一个根本没坏的文件 — 小欧-2026-10-30
//   2026-11-02 小欧 - 行内路径改复用唯一链接组件 PathLink（删自建 button+nav+渲染期根解析）：
//     原实现是第二套「路径点击 → 跳转」，用渲染期根，而 PathLink 用点击实时根，口径会漂；
//     图标/可点性/不可链接降级一并交给 PathLink — 小欧-2026-11-02

//   2026-11-13 商量 - 折叠区标题行固定 24px(原 6px 上下留白撑到约 34px, 与 taskinfo/按钮行失衡):
//     定高 + 说明文案单行省略, 窄栏不折行 — 商量-2026-11-13

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
import { Empty, Skeleton } from 'antd';
import { CaretRightOutlined, PaperClipOutlined } from '@ant-design/icons';
import { type RecentFile } from '@/services/api/file.api';
// 2026-10-22 小欧 - 引用入口统一，不再直接调 composerRefStore
import { quoteWithToast } from '@/features/refs/quoteToast'; // 引用提示三分支唯一实现 — 小欧 2026-10-30
import { chatStreamStore } from '../../streams/chatStreamStore';
import { useRecentFiles } from '@/hooks/useRecentFiles';
// 2026-11-02 小欧 - 路径渲染复用唯一链接组件（判据/图标/点击口径/降级全在组件内）— 小欧-2026-11-02
import { PathLink } from '@/components/PathLink';
import { chatTokens } from '@/theme/tokens';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
// 2026-11-13 商量 - 标题行高度取全站控件刻度唯一真源(小号档 24px), 不写字面量 — 商量-2026-11-13
import { CONTROL_HEIGHT_SM } from '@/theme/controlScale';

/**
 * ops 徽标配色/文案 —— ops 的取值域是后端工具**注册名**（FILE_OPERATION_TOOLS，16 个），
 *   故这里只给高频三类着色，其余走弱色原名兜底（前端不自造工具分类）。
 *
 * 2026-10-21 小欧 - 导出供测试断言（徽标映射口径易被改坏）— 小欧-2026-10-21
 */
export const OP_COLOR: Record<string, string> = {
  read: Colors.PRIMARY,
  write: Colors.SUCCESS,
  edit: Colors.WAIT_ACTION,
};
export const OP_LABEL: Record<string, string> = {
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
    // 2026-10-22 小欧 - 引用入口统一（读盘+组装+入队只有一份）
    // 2026-10-30 小欧 - 提示也统一(quoteWithToast): 原实现漏 too_many 分支, 超上限被报成"读取失败"
    await quoteWithToast(f.path, null, { label: f.name });
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
          // 2026-11-13 商量 - 标题行取全站小号控件刻度 CONTROL_HEIGHT_SM(24px), 与按钮行同高:
          //   原 6px 上下留白把行撑到约 34px, 与 taskinfo(≈27)/按钮行(24)失衡;
          //   定高后由 flex 居中, 不再另写行高; 说明文案单行省略保证窄栏不折行破高度
          height: CONTROL_HEIGHT_SM,
          boxSizing: 'border-box',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: `0 ${Spacing.LG}px`,
          color: Colors.TEXT.STRONG,
          fontSize: chatTokens.fontMD,
          textAlign: 'left',
        }}
      >
        <CaretRightOutlined
          style={{ fontSize: FontSize.CAPTION }}
          rotate={expanded ? 90 : 0}
        />
        文件足迹
        <span
          style={{
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
            marginLeft: Spacing.XS,
            // 2026-11-13 商量 - 说明文案单行省略: 保证标题行恒为 24px, 窄栏也不折行撑高
            flex: '1 1 auto',
            minWidth: 0,
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
          }}
        >
          本会话中 Agent 读写过的文件 · 点文件路径打开，点「引用」加入本轮对话
        </span>
        <span
          style={{
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
            marginLeft: Spacing.XS,
          }}
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
            files.map((f) => {
              // 2026-11-02 小欧 - ops 兜底取一次：原 `(f.ops ?? [])` 在本行内写三遍 — 小欧-2026-11-02
              const ops = f.ops ?? [];
              return (
                <div
                  key={f.path}
                  style={{
                    display: 'flex',
                    /* 2026-10-23 小欧 - 路径折多行时 center 会让图标/徽标/时间/引用悬在行中间
                       错开首行 → flex-start 对齐首行（单行时两者等价） — 小欧-2026-10-23 */
                    alignItems: 'flex-start',
                    gap: Spacing.SM,
                    padding: `${Spacing.XS}px 0`,
                  }}
                >
                  {/* 键盘目标①：文件路径 = 打开文件。2026-11-02 小欧 - 改复用唯一链接组件 PathLink：
                      图标/可点性/点击实时取根/不可链接降级全在组件内，本面板不再自建 button+nav — 小欧-2026-11-02 */}
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <PathLink
                      rawPath={f.path}
                      dirHint={f.type === 'dir'}
                      variant="inline"
                      tooltip
                    />
                  </span>
                  {/* ops 徽标**只显前 2 个**，其余折叠为 +N（真实取值域 16 个工具名） */}
                  {ops.slice(0, 2).map((op) => (
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
                  {ops.length > 2 && (
                    <span
                      style={{
                        color: Colors.TEXT.WEAK,
                        fontSize: chatTokens.fontSM,
                      }}
                    >
                      +{ops.length - 2}
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
                  {/* 键盘目标②：引用（仅文本；图片由查看器处理，文本通道不读取）— 小杨-2026-10-21 */}
                  {f.preview === 'text' && (
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
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
