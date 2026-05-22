import React from "react";
import TimestampToTimeView from "../../views/TimestampToTimeView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimestampToTimeRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>时间为空</div>;
  return <TimestampToTimeView data={data} />;
};
export default React.memo(TimestampToTimeRenderer);
