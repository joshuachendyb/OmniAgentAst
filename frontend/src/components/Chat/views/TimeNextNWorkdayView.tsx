import React from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface Props { data: string[]; }

const TimeNextNWorkdayView: React.FC<Props> = ({ data }) => {
  const dates = data || [];
  if (!dates.length) return <span style={{ color: "#999" }}>无工作日数据</span>;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#1890ff", background: "#e6f7ff" }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>接下来 {dates.length} 个工作日：</span>
      <span>{dates.join("、")}</span>
    </div>
  );
};
export default React.memo(TimeNextNWorkdayView);
