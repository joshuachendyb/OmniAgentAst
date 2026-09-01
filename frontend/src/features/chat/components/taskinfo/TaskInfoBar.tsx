// 编辑历史: 2026-08-26 小欧 - 修复A3(接受detail派生历史任务动态信息/7.6+4.5.1)+B2(执行中实时计时/7.6②)+C2(上下文截断文字/7.9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.4 useRef仅首次锚定start, 去frames.startTimestamp防抖动, 切换复位
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P0-2/边距-P0-2: 去整框留淡底(border→none,background#fafafa,radius6,padding8px); 内层过程区加滚动细线borderTop#f5f5f5+scrollbarWidth; 外层gap2→8主节奏
// 编辑历史: 2026-08-28 小欧 - ①C/c1: 去胶囊改透明+borderTop#f0f0f0, gap12→8, 数值加粗#595959 500, Tag→Text轻量化
// 编辑历史: 2026-08-30 小欧 - 13.14 8处Typography.Text→span+双组token本轮/任务累计(P/C/T后端直发) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 13.14 TrustPanel移至TaskInfoBar第一行尾部集成（第一行尾巴） - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复×不显眼: DeleteOutlined→文本×、色#999→#595959、字号12→14加粗 - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - TaskInfoBar一线三组最佳重排: 左主节奏(状态/耗时/步轮·重试) 中Token合一T(P/C) 右信任/收起 gap12/8 减半宽 - 小欧-2026-09-01
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

import React, { useCallback, useEffect, useState, useRef } from 'react';
import { Badge, Tooltip } from 'antd';
import type { ExecutionStep } from '../../../../types/execution';
import type { TaskMetaFrames } from '@/types/sse';
import type { TaskDetail } from '../../../../services/api/task.api';
import { trustApi } from '../../../../services/api/task.api';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { useTaskInfo } from '../../hooks/useTaskInfo';

interface TaskInfoBarProps {
  steps: ExecutionStep[];
  frames: TaskMetaFrames; // 统计类元信息帧（8.4.14）
  receiving: boolean;
  detail?: TaskDetail | null; // 【A3】选中历史任务时由其详情派生动态信息
  sessionId?: string | null; // 13.14 TrustPanel第一行尾部需会话ID
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
  sessionId,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const info = useTaskInfo(steps, frames, receiving, detail);
  const b = BADGE_MAP[info.badge];
  const [trustExpanded, setTrustExpanded] = useState(false);
  const [trustTools, setTrustTools] = useState<string[]>([]);
  const trustReqIdRef = useRef(0);
  const loadTrust = useCallback(async () => {
    if (!sessionId) return;
    const reqId = ++trustReqIdRef.current;
    try {
      const fetched = await trustApi.getTrust(sessionId);
      if (reqId === trustReqIdRef.current) setTrustTools(fetched);
    } catch {
      if (reqId === trustReqIdRef.current) setTrustTools([]);
    }
  }, [sessionId]);
  useEffect(() => {
    void loadTrust();
  }, [loadTrust]);
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{ sessionId: string }>;
      if (ce.detail?.sessionId === sessionId) void loadTrust();
    };
    window.addEventListener('omni-trust-changed', handler as EventListener);
    return () =>
      window.removeEventListener(
        'omni-trust-changed',
        handler as EventListener
      );
  }, [sessionId, loadTrust]);
  const revokeTrust = async (toolName: string) => {
    if (!sessionId) return;
    await trustApi.revokeTrust(sessionId, toolName);
    await loadTrust();
  };

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
        () =>
          setLiveElapsed(Math.max(0, Math.round((Date.now() - start) / 1000))),
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
        background: 'transparent',
        border: 'none',
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        padding: '8px 0 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        textAlign: 'left',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          cursor: 'pointer',
          flexWrap: 'nowrap',
        }}
        onClick={() => setCollapsed((v) => !v)}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          <Badge status={b.status} text={b.text} />
          <span
            style={{
              fontSize: 12,
              color: Colors.TEXT.PRIMARY,
              fontWeight: 500,
            }}
          >
            耗时 {Math.round(shownElapsed)}s
          </span>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
            步骤 {info.stepCount} / 轮次 {info.llmCallCount}
          </span>
          {info.retryCount > 0 && (
            <span style={{ fontSize: 12, color: Colors.WARNING }}>
              · 重试 {info.retryCount}
            </span>
          )}
          {info.stuckWarning && (
            <span style={{ fontSize: 12, color: Colors.WARNING }}>
              · 疑似卡死
            </span>
          )}
          {info.truncatedTip && (
            <span style={{ fontSize: 12, color: Colors.WARNING }}>
              · ⚠ {info.truncatedTip}
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flex: 1,
            minWidth: 0,
            justifyContent: 'center',
          }}
        >
          <Tooltip
            title={`本轮 P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0} / T ${info.roundUsage?.total ?? 0}`}
          >
            <span
              style={{
                fontSize: 12,
                color: Colors.TEXT.PRIMARY,
                fontWeight: 500,
              }}
            >
              本轮 T{info.roundUsage?.total ?? 0} (P
              {info.roundUsage?.prompt ?? 0}/C
              {info.roundUsage?.completion ?? 0})
            </span>
          </Tooltip>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
          <Tooltip
            title={`任务累计 P ${info.taskAccumulated?.prompt_tokens ?? info.usage.prompt} / C ${info.taskAccumulated?.completion_tokens ?? info.usage.completion} / T ${info.taskAccumulated?.total_tokens ?? info.usage.total}`}
          >
            <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
              累计 T{info.taskAccumulated?.total_tokens ?? info.usage.total} (P
              {info.taskAccumulated?.prompt_tokens ?? info.usage.prompt}/C
              {info.taskAccumulated?.completion_tokens ?? info.usage.completion}
              )
            </span>
          </Tooltip>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
          {typeof info.overview === 'string' ? (
            <Tooltip title={info.overview}>
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文摘要
              </span>
            </Tooltip>
          ) : info.overview ? (
            <Tooltip
              title={`${info.overview.summary}\n消息数 ${info.overview.message_count ?? '-'} · 估算 ${info.overview.estimated_tokens ?? '-'} tok`}
            >
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文 {info.overview.estimated_tokens ?? '-'}tok
                {info.overview.truncated && ' 🔴'}
              </span>
            </Tooltip>
          ) : frames.contextSummary ? (
            <Tooltip title={frames.contextSummary}>
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文摘要
              </span>
            </Tooltip>
          ) : (
            <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
              上下文 {0}tok
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
            marginLeft: 'auto',
          }}
        >
          <span
            onClick={(e) => {
              e.stopPropagation();
              setTrustExpanded((v) => !v);
            }}
            style={{
              fontSize: 12,
              color:
                trustTools.length > 0
                  ? Colors.TEXT.PRIMARY
                  : Colors.TEXT.TERTIARY,
              cursor: 'pointer',
            }}
          >
            {trustExpanded ? '▾' : '▸'} 信任({trustTools.length})
          </span>
          <span
            onClick={() => setCollapsed((v) => !v)}
            style={{
              color: Colors.TEXT.TERTIARY,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {collapsed ? '展开' : '收起'}
          </span>
        </div>
      </div>
      {trustExpanded && trustTools.length > 0 && (
        <div
          style={{
            maxHeight: 70,
            overflow: 'auto',
            paddingTop: Spacing.XS,
            borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
            marginTop: 4,
          }}
        >
          {trustTools.map((tool) => (
            <div
              key={tool}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: `${Spacing.XS - 2}px 0`,
              }}
            >
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
                }}
              >
                {tool}
              </span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  void revokeTrust(tool);
                }}
                style={{
                  fontSize: 14,
                  color: Colors.TEXT.PRIMARY,
                  cursor: 'pointer',
                  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
                  padding: '0 4px',
                  fontWeight: 500,
                }}
                title="撤销信任"
              >
                ×
              </span>
            </div>
          ))}
        </div>
      )}

      {!collapsed && info.processEvents.length > 0 && (
        <div
          style={{
            maxHeight: 72,
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
            paddingTop: 8,
            marginTop: 0,
          }}
        >
          {info.processEvents.map((e, i) => (
            <div key={i} style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
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
