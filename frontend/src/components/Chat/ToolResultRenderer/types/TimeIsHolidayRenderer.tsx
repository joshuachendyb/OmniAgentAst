/**
 * TimeIsHolidayRenderer - time_is_holiday 工具结果渲染器
 *
 * 从ExecutionStep提取数据并调用TimeIsHolidayView渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import TimeIsHolidayView from "../../views/TimeIsHolidayView";
import { BaseRendererProps } from "./BaseRendererProps";

interface TimeIsHolidayRendererProps extends BaseRendererProps {}

const TimeIsHolidayRenderer: React.FC<TimeIsHolidayRendererProps> = ({ step }) => {
  const execResult = step.execution_result;
  const data = (execResult as Record<string, unknown>)?.data || execResult as Record<string, unknown>;

  if (!data) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 节假日数据为空
      </div>
    );
  }

  return <TimeIsHolidayView data={data} />;
};

export default React.memo(TimeIsHolidayRenderer);