/**
 * TimeNowRenderer - time_now 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeNowView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeNowView from "../../views/TimeNowView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeNowRendererProps extends BaseRendererProps {}

const TimeNowRenderer: React.FC<TimeNowRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 时间数据为空
      </div>
    );
  }

  return <TimeNowView data={data} />;
};

export default React.memo(TimeNowRenderer);