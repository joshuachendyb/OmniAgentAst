import React from "react";
import TimeCompareView from "../../views/TimeCompareView";
import { BaseRendererProps } from "./BaseRendererProps";
interface Props extends BaseRendererProps {}
const TimeCompareRenderer: React.FC<Props> = ({ step }) => {
  const r = step.execution_result;
  const data = (r as Record<string, unknown>)?.data || r as Record<string, unknown>;
  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>比较结果为空</div>;
  return <TimeCompareView data={data} />;
};
export default React.memo(TimeCompareRenderer);
