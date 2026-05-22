/**
 * TimerClearRenderer - timer_clear 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimerClearView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimerClearView from "../../views/TimerClearView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimerClearRendererProps extends BaseRendererProps {}

const TimerClearRenderer: React.FC<TimerClearRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 定时器数据为空
      </div>
    );
  }

  return <TimerClearView data={data} />;
};

export default React.memo(TimerClearRenderer);