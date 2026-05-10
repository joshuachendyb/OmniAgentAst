import React from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface Props { data: { result_time?: string; unit_used?: string; delta_used?: number; tz?: string; }; }

const TimeAddView: React.FC<Props> = ({ data }) => {
  const { result_time = "", unit_used = "", delta_used = 0, tz = "" } = data || {};
  if (!result_time) return <span style={{ color: "#999" }}>计算结果为空</span>;
  const sign = delta_used >= 0 ? "+" : "";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#1890ff", background: "#e6f7ff" }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>{sign}{delta_used} {unit_used}后 → {result_time}</span>
      <span style={{ fontSize: 11, color: "#8c8c8c" }}>UTC{tz}</span>
    </div>
  );
};
export default React.memo(TimeAddView);
