import React from "react";
import { SwapOutlined } from "@ant-design/icons";

interface Props { data: { result?: string; diff_value?: number; diff_unit?: string; time1?: string; time2?: string; }; }

const resultLabel: Record<string, string> = { lt: "早于", gt: "晚于", eq: "等于" };

const TimeCompareView: React.FC<Props> = ({ data }) => {
  const { result = "", diff_value = 0, diff_unit = "", time1: _time1 = "", time2: _time2 = "" } = data || {};
  if (!result) return <span style={{ color: "#999" }}>比较结果为空</span>;
  const absDiff = Math.abs(diff_value);
  const label = resultLabel[result] || result;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#595959", background: "#f5f5f5" }}>
      <SwapOutlined />
      <span style={{ fontWeight: 500 }}>相差 {absDiff} {diff_unit}（时间1{label}时间2）</span>
    </div>
  );
};
export default React.memo(TimeCompareView);
