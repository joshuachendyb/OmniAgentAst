/**
 * TimeLocalToUtcRenderer - time_local_to_utc 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeLocalToUtcView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeLocalToUtcView from "../../views/TimeLocalToUtcView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeLocalToUtcRendererProps extends BaseRendererProps {}

const TimeLocalToUtcRenderer: React.FC<TimeLocalToUtcRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 时区转换数据为空
      </div>
    );
  }

  return <TimeLocalToUtcView data={data} />;
};

export default React.memo(TimeLocalToUtcRenderer);