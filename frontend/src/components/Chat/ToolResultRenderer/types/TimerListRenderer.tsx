import React from "react";
import TimerListView from "../../views/TimerListView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimerListRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>定时器数据为空</div>;
  return <TimerListView data={data as Array<Record<string, unknown>>} />;
};
export default React.memo(TimerListRenderer);
