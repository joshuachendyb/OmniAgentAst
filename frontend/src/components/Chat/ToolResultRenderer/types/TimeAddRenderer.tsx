import React from "react";
import TimeAddView from "../../views/TimeAddView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimeAddRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>计算结果为空</div>;
  return <TimeAddView data={data} />;
};
export default React.memo(TimeAddRenderer);
