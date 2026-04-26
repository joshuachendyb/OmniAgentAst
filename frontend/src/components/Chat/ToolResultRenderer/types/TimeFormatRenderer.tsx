/**
 * TimeFormatRenderer - time_format 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeFormatView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeFormatView from "../../views/TimeFormatView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeFormatRendererProps extends BaseRendererProps {}

const TimeFormatRenderer: React.FC<TimeFormatRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 格式化时间数据为空
      </div>
    );
  }

  return <TimeFormatView data={data} />;
};

export default React.memo(TimeFormatRenderer);