/**
 * TimeDiffRenderer - time_diff 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeDiffView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeDiffView from "../../views/TimeDiffView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeDiffRendererProps extends BaseRendererProps {}

const TimeDiffRenderer: React.FC<TimeDiffRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 时间差数据为空
      </div>
    );
  }

  return <TimeDiffView data={data} />;
};

export default React.memo(TimeDiffRenderer);