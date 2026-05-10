import React from "react";
import TimeIsWorkdayView from "../../views/TimeIsWorkdayView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimeIsWorkdayRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (data === undefined || data === null) return <div style={{ color: "#999", padding: "8px 12px" }}>工作日数据为空</div>;
  return <TimeIsWorkdayView data={data as boolean} />;
};
export default React.memo(TimeIsWorkdayRenderer);
