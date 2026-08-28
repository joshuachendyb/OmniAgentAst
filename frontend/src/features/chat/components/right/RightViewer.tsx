// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 右侧查看区, 当前任务禁REST走liveSteps, 业务步骤分流(7.10/R1-B4/B9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.1 抽toExecutionSteps收窄unknown[]→ExecutionStep[]替换裸as断言
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审P1-5/边距: 补空/错误三态(Empty暂无执行记录/Skeleton由Spin承载/Alert错误margin8px0#fff2f0隔离); 错误红字与统计块加间距防误读
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
import { Spin, Empty, Alert, Typography } from 'antd';
import type { ExecutionStep } from '../../../../types/execution';
import { Colors } from '@/utils/stepStyles';
import { sessionApi } from '../../../../services/api/session.api';
import {
  executionApi,
  type TaskDetail,
} from '../../../../services/api/task.api';
import { PipelineRenderer } from '../pipeline';
import { splitSteps } from '../pipeline/stepFilter';
import { StaticStatsBlock } from './StaticStatsBlock';

// 2026-08-27 小欧 三堂会审: 收窄 unknown[]→ExecutionStep[], 形状不符回落空数组
const toExecutionSteps = (raw: unknown): ExecutionStep[] => {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is ExecutionStep =>
      typeof s === 'object' && s !== null && 'type' in s
  );
};

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
    if (!activeTaskId || isCurrentLive) {
      // 2026-08-27 小欧 修复#45: 切到实时任务时清空历史detail, 避免StaticStatsBlock残留旧任务统计
      setDetail(null);
      return; // B4：执行中不拉 REST
    }
    let cancelled = false;
    if (!detail) setLoading(true); // 2026-08-27 小欧 修复#47: 仅首次加载显示spinner, 已有旧detail时不遮盖(避免切换任务闪烁)
    (async () => {
      try {
        const [d, s] = await Promise.all([
          executionApi.getTaskDetail(activeTaskId),
          executionApi.getTaskSteps(activeTaskId),
        ]);
        if (cancelled) return;
        setDetail(d);
        if (s.steps.length > 0) {
          // 2026-08-27 小欧 修复#46: 拒绝裸断言, steps 缺失时回落空数组, 避免下游读step字段得undefined
          setHistorySteps(toExecutionSteps(s.steps)); // 2026-08-27 小欧 三堂会审: 收窄unknown[]→ExecutionStep[]
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
      // 2026-08-27 小欧 修复#44: 移除冗余getTaskDetail(上方effect在isCurrentLive变false时已补取), 避免双发REST
      onSettledRefresh?.();
    }
    prevReceivingRef.current = receiving;
  }, [receiving, activeTaskId, serverTaskId, onSettledRefresh]);

  const displaySteps = isCurrentLive ? liveSteps : historySteps;
  const hasSteps = displaySteps.length > 0;

  return (
    <Spin spinning={loading}>
      {!loading && !hasSteps && !liveErrorText ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, color: Colors.TEXT.SECONDARY }}
            >
              暂无执行记录
            </Typography.Text>
          }
          style={{ padding: '24px 0' }}
        />
      ) : (
        <PipelineRenderer
          steps={splitSteps(displaySteps).business}
          streaming={isCurrentLive}
          highlightToolName={highlightToolName}
        />
      )}
      {liveErrorText && (
        <Alert
          type="error"
          showIcon
          message={liveErrorText}
          style={{
            margin: '8px 0',
            fontSize: 12,
            borderRadius: 6,
            background: '#fff2f0',
            border: '1px solid #ffccc7',
          }}
        />
      )}
      <StaticStatsBlock detail={detail} />
    </Spin>
  );
};

export { RightViewer };
