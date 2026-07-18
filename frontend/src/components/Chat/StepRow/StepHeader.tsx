/**
 * StepHeader组件 - 步骤头部（编号、标签、图标、时间戳）
 *
 * @author 小沈
 * @version 1.1.0
 * @since 2026-04-21
 * @update 2026-04-28 小强 - 第六步P1：emoji替换为Ant Design图标
 *
 * 编辑历史:
 * 2026-07-18 小欧 FinalStep终态规整: effectiveType按outcome分流cancelled→cancelled/error→error/completed→final
 *   【病根】原effectiveType=step.type, type=final统一显示完成图标✅, 失败/取消也误显为完成;
 *   【改法】effectiveType改写: final+cancelled→cancelled(final配置保留icon), final+failed→error, final+completed→final
 */

import React from 'react';
import {
  RocketOutlined,
  BulbOutlined,
  ToolOutlined,
  FileTextOutlined,
  MessageOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  WarningOutlined,
  SyncOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { formatTimestamp } from '../../../utils/timestamp';
import type { ExecutionStep } from '../../../utils/sse';
import { getTimestampStyle } from '../../../utils/stepStyles';

/**
 * emoji到Ant Design图标的映射（第六步P1优化）
 */
const stepIconMap: Record<string, React.ReactNode> = {
  start: <RocketOutlined />,
  thought: <BulbOutlined />,
  action_tool: <ToolOutlined />,
  observation: <FileTextOutlined />,
  chunk: <MessageOutlined />,
  final: <CheckCircleOutlined />,
  error: <CloseCircleOutlined />,
  paused: <PauseCircleOutlined />,
  resumed: <PlayCircleOutlined />,
  cancelled: <WarningOutlined />,
  retrying: <SyncOutlined />,
};

interface StepHeaderProps {
  step: ExecutionStep;
  badgeStyle: React.CSSProperties;
  labelStyle: React.CSSProperties;
  label: string;
  icon: string;
}

/**
 * StepHeader组件
 * 显示步骤编号、标签图标和时间戳
 * 第六步P1：使用Ant Design图标替代emoji
 */
const StepHeader: React.FC<StepHeaderProps> = ({
  step,
  badgeStyle,
  labelStyle,
  label,
  icon: _icon,
}) => {
  // 获取对应的Ant Design图标
  // 2026-07-18 小欧 FinalStep 终态规整：终态统一 type=final，按 outcome 分流；取消/失败不误显为完成
  const effectiveType =
    step.type === 'final'
      ? step.outcome === 'cancelled'
        ? 'cancelled'
        : step.outcome === 'failed'
          ? 'error'
          : 'final'
      : step.type;
  const stepIcon = stepIconMap[effectiveType] || stepIconMap.thought || null;

  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
      {/* 步骤编号徽章 */}
      {step.step && (
        <span style={{ ...badgeStyle, marginRight: 4 }}>步骤{step.step}</span>
      )}
      {/* 标签带图标 - 第六步P1：使用Ant Design图标 */}
      <span style={labelStyle}>
        {stepIcon} {label}：
      </span>
      <span style={{ flex: 1 }} /> {/* 弹性空间，将timestamp推到右侧 */}
      {/* timestamp放在行右侧，与右侧边框挨着，更醒目 - 第六步P1：使用图标组件 */}
      {step.timestamp && (
        <span style={getTimestampStyle(effectiveType)}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />{' '}
          {formatTimestamp(step.timestamp)}
        </span>
      )}
    </div>
  );
};

export default React.memo(StepHeader);
