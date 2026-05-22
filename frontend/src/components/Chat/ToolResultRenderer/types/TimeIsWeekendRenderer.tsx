/**
 * TimeIsWeekendRenderer - time_is_weekend 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeIsWeekendView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeIsWeekendView from "../../views/TimeIsWeekendView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeIsWeekendRendererProps extends BaseRendererProps {}

const TimeIsWeekendRenderer: React.FC<TimeIsWeekendRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 周末数据为空
      </div>
    );
  }

  return <TimeIsWeekendView data={data} />;
};

export default React.memo(TimeIsWeekendRenderer);