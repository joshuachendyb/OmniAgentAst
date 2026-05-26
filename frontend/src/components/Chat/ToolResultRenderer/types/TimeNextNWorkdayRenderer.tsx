import React from "react";
import TimeNextNWorkdayView from "../../views/TimeNextNWorkdayView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimeNextNWorkdayRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>工作日数据为空</div>;
  return <TimeNextNWorkdayView data={data as string[]} />;
};
export default React.memo(TimeNextNWorkdayRenderer);
