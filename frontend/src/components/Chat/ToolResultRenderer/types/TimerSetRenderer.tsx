/**
 * TimerSetRenderer - timer_set 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimerSetView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimerSetView from "../../views/TimerSetView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimerSetRendererProps extends BaseRendererProps {}

const TimerSetRenderer: React.FC<TimerSetRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 定时器数据为空
      </div>
    );
  }

  return <TimerSetView data={data} />;
};

export default React.memo(TimerSetRenderer);