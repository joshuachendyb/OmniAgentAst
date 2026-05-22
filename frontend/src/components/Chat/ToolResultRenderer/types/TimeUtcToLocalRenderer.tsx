/**
 * TimeUtcToLocalRenderer - time_utc_to_local 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeUtcToLocalView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeUtcToLocalView from "../../views/TimeUtcToLocalView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeUtcToLocalRendererProps extends BaseRendererProps {}

const TimeUtcToLocalRenderer: React.FC<TimeUtcToLocalRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 时区转换数据为空
      </div>
    );
  }

  return <TimeUtcToLocalView data={data} />;
};

export default React.memo(TimeUtcToLocalRenderer);