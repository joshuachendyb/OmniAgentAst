/**
 * StepHeader组件 - 步骤头部（编号、标签、图标、时间戳）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import { formatTimestamp } from "../../../utils/timestamp";
import type { ExecutionStep } from "../../../utils/sse";
import { getTimestampStyle } from "../../../utils/stepStyles";

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
 */
const StepHeader: React.FC<StepHeaderProps> = ({ 
  step, 
  badgeStyle, 
  labelStyle, 
  label, 
  icon 
}) => {
  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap" }}>
      {/* 步骤编号徽章 */}
      {step.step && (
        <span style={badgeStyle}>
          步骤{step.step}
        </span>
      )}
      {/* 标签带图标 */}
      <span style={labelStyle}>
        {icon} {label}：
      </span>
      <span style={{ flex: 1 }} />  {/* 弹性空间，将timestamp推到右侧 */}
      {/* timestamp放在行右侧，与右侧边框挨着，更醒目 */}
      {step.timestamp && (
        <span style={getTimestampStyle(step.type as any)}>
          ⏰ {formatTimestamp(step.timestamp)}
        </span>
      )}
    </div>
  );
};

export default React.memo(StepHeader);
