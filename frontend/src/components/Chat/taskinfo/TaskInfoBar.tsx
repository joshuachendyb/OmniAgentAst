// 编辑历史: 2026-08-26 小欧 - 修复A3(接受detail派生历史任务动态信息/7.6+4.5.1)+B2(执行中实时计时/7.6②)+C2(上下文截断文字/7.9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.4 useRef仅首次锚定start, 去frames.startTimestamp防抖动, 切换复位
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P0-2/边距-P0-2: 去整框留淡底(border→none,background#fafafa,radius6,padding8px); 内层过程区加滚动细线borderTop#f5f5f5+scrollbarWidth; 外层gap2→8主节奏
/**
 * TaskInfoBar - 输入框上方任务信息条（taskinfo slot，当前任务动态实时唯一位置）
 *
 * 【小欧 2026-08-26 8.6】7 项信息点（7.6 目标）：①状态徽标(startinfo)②耗时③轮次
 * ④token实时累计(usage)⑤上下文概况(context_overview)⑥过程状态条(start已开始/
 * paused/resumed/retrying)+取消终态⑦truncated提示。可折叠；纯 SSE 收流。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useState, useRef } from 'react';
import { Badge, Tag, Tooltip, Typography } from 'antd';
import type { ExecutionStep } from '../../../types/execution';
import type { TaskMetaFrames } from '../../../utils/sse';
import type { TaskDetail } from '../../../services/api';
import { useTaskInfo } from '../../../hooks/chat/useTaskInfo';

interface TaskInfoBarProps {
  steps: ExecutionStep[];
  frames: TaskMetaFrames; // 统计类元信息帧（8.4.14）
  receiving: boolean;
  detail?: TaskDetail | null; // 【A3】选中历史任务时由其详情派生动态信息
}

const BADGE_MAP = {
  idle: { status: 'default' as const, text: '待命' },
  running: { status: 'processing' as const, text: '执行中' },
  paused: { status: 'warning' as const, text: '已暂停' },
  completed: { status: 'success' as const, text: '已完成' },
  failed: { status: 'error' as const, text: '失败' },
  cancelled: { status: 'default' as const, text: '已取消' },
};

const TaskInfoBar: React.FC<TaskInfoBarProps> = ({
  steps,
  frames,
  receiving,
  detail,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const info = useTaskInfo(steps, frames, receiving, detail);
  const b = BADGE_MAP[info.badge];

  // 【小欧 2026-08-26 修复 B2】执行中实时计时：当前任务(receiving+running)按 start 时刻走表，
  // 历史任务(detail)用后端 duration，不计时。
  const [liveElapsed, setLiveElapsed] = useState(0);
  const startRef = useRef<number | null>(null); // 2026-08-27 小欧 三堂会审: 仅首次锚定start, 防计时抖动
  useEffect(() => {
    if (receiving && info.badge === 'running' && !detail) {
      if (startRef.current == null) {
        startRef.current = frames.startTimestamp || Date.now(); // 2026-08-27 小欧 三堂会审: 首次锚定
      }
      const start = startRef.current;
      const t = setInterval(
        () => setLiveElapsed(Math.max(0, Math.round((Date.now() - start) / 1000))),
        1000
      );
      return () => clearInterval(t);
    }
    setLiveElapsed(0);
    startRef.current = null; // 2026-08-27 小欧 三堂会审: 任务切换复位startRef
    return undefined;
  }, [receiving, info.badge, detail]); // 2026-08-27 小欧 三堂会审: 去frames.startTimestamp防抖动
  const shownElapsed = detail
    ? info.elapsedSec
    : receiving && info.badge === 'running'
      ? liveElapsed
      : info.elapsedSec;

  return (
    <div
      style={{
        border: 'none',
        background: '#fafafa',
        borderRadius: 6,
        padding: '8px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          cursor: 'pointer',
          flexWrap: 'wrap',
        }}
        onClick={() => setCollapsed((v) => !v)}
      >
        <Badge status={b.status} text={b.text} />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          耗时 {Math.round(shownElapsed)}s
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          步骤 {info.stepCount} / 轮次 {info.llmCallCount}
          {info.retryCount > 0 && ` / 重试 ${info.retryCount}`}
        </Typography.Text>
        <Tooltip title={`P ${info.usage.prompt} / C ${info.usage.completion}`}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            本轮/任务 token {info.usage.total}
          </Typography.Text>
        </Tooltip>
        {/* 上下文概况：context_overview 帧优先，start.context_summary 兜底（8.9） */}
        {typeof info.overview === 'string' ? (
          <Tooltip title={info.overview}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              上下文摘要
            </Typography.Text>
          </Tooltip>
        ) : info.overview ? (
          <Tooltip
            title={`${info.overview.summary}\n消息数 ${info.overview.message_count ?? '-'} · 估算 ${info.overview.estimated_tokens ?? '-'} tok`}
          >
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              上下文 {info.overview.estimated_tokens ?? '-'}tok
              {info.overview.truncated && ' 🔴已截断'}
            </Typography.Text>
          </Tooltip>
        ) : frames.contextSummary ? (
          <Tooltip title={frames.contextSummary}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              上下文摘要
            </Typography.Text>
          </Tooltip>
        ) : null}
        {info.stuckWarning && <Tag color="volcano">疑似卡死(llm≫step)</Tag>}
        {info.truncatedTip && <Tag color="orange">⚠ {info.truncatedTip}</Tag>}
        <span style={{ marginLeft: 'auto', color: '#999', fontSize: 12 }}>
          {collapsed ? '展开' : '收起'}
        </span>
      </div>

      {!collapsed && info.processEvents.length > 0 && (
        <div
          style={{
            maxHeight: 72,
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            borderTop: '1px solid #f5f5f5',
            marginTop: 4,
            paddingTop: 4,
          }}
        >
          {info.processEvents.map((e, i) => (
            <div key={i} style={{ fontSize: 12, color: '#999' }}>
              {e.kind === 'started' && '▶️ '}
              {e.kind === 'paused' && '⏸️ '}
              {e.kind === 'resumed' && '▶️ '}
              {e.kind === 'retrying' && '🔁 '}
              {e.text} {new Date(e.time).toLocaleTimeString()}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { TaskInfoBar };
