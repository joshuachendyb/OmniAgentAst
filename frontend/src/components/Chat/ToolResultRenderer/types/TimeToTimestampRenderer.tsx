import React from "react";
import TimeToTimestampView from "../../views/TimeToTimestampView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimeToTimestampRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>时间戳为空</div>;
  return <TimeToTimestampView data={data as number} />;
};
export default React.memo(TimeToTimestampRenderer);
