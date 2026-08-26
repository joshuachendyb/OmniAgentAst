/**
 * RightViewer - 右侧查看区（right slot，当前锚定任务流水线 + 静态统计块）
 *
 * 【小欧 2026-08-26 8.5 / R1 修正】
 * - B4：执行中的当前任务(isCurrentLive)禁拉 REST，纯走 liveSteps 回放同一 PipelineRenderer；
 * - B9：渲染入口 splitSteps().business 分流（meta 不进查看区，7.10）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useRef, useState } from 'react';
import { Spin } from 'antd';
import type { ExecutionStep } from '../../../utils/sse';
import {
  executionApi,
  sessionApi,
  type TaskDetail,
} from '../../../services/api';
import { PipelineRenderer } from '../pipeline';
import { splitSteps } from '../pipeline/steps';
import { StaticStatsBlock } from './StaticStatsBlock';

interface RightViewerProps {
  activeTaskId: string | null;
  sessionId: string | null;
  serverTaskId: string | null;
  receiving: boolean;
  liveSteps: ExecutionStep[];
  liveErrorText: string | null; // useSSE onError.error_message（8.10）
  highlightToolName: string | null;
  onSettledRefresh?: () => void; // 结束沿通知外层刷新任务列表
}

const RightViewer: React.FC<RightViewerProps> = ({
  activeTaskId,
  sessionId,
  serverTaskId,
  receiving,
  liveSteps,
  liveErrorText,
  highlightToolName,
  onSettledRefresh,
}) => {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [historySteps, setHistorySteps] = useState<ExecutionStep[]>([]);
  const [loading, setLoading] = useState(false);
  const prevReceivingRef = useRef(false);

  const isCurrentLive =
    activeTaskId != null && activeTaskId === serverTaskId && receiving;

  // 拉取历史任务：C1+C2 并行；C2 空则 C3 按 message 降级（静态块降级为空，契约无通道）
  useEffect(() => {
    if (!activeTaskId || isCurrentLive) return; // B4：执行中不拉 REST
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [d, s] = await Promise.all([
          executionApi.getTaskDetail(activeTaskId),
          executionApi.getTaskSteps(activeTaskId),
        ]);
        if (cancelled) return;
        setDetail(d);
        if (s.steps.length > 0) {
          setHistorySteps(s.steps as ExecutionStep[]);
        } else if (sessionId) {
          const msgResp = await sessionApi.getSessionMessages(sessionId);
          if (cancelled) return;
          const fallback: ExecutionStep[] = [];
          for (const m of msgResp.messages) {
            for (const st of m.execution_steps ?? []) fallback.push(st);
          }
          setHistorySteps(fallback);
        } else {
          setHistorySteps([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTaskId, sessionId, isCurrentLive]);

  // B16：锚定的当前任务结束沿 -> 补取 C1 终态详情并刷新外层列表
  useEffect(() => {
    if (
      prevReceivingRef.current &&
      !receiving &&
      activeTaskId === serverTaskId &&
      activeTaskId
    ) {
      executionApi
        .getTaskDetail(activeTaskId)
        .then((d) => setDetail(d))
        .catch(() => undefined);
      onSettledRefresh?.();
    }
    prevReceivingRef.current = receiving;
  }, [receiving, activeTaskId, serverTaskId, onSettledRefresh]);

  const displaySteps = isCurrentLive ? liveSteps : historySteps;

  return (
    <Spin spinning={loading}>
      <PipelineRenderer
        steps={splitSteps(displaySteps).business}
        streaming={isCurrentLive}
        highlightToolName={highlightToolName}
      />
      {liveErrorText && (
        <div style={{ color: '#cf1322', fontSize: 13, margin: '4px 0' }}>
          ❌ {liveErrorText}
        </div>
      )}
      <StaticStatsBlock detail={detail} />
    </Spin>
  );
};

export { RightViewer };
