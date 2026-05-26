import React from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface Props { data: boolean; }

const TimeIsWorkdayView: React.FC<Props> = ({ data }) => {
  const isWorkday = !!data;
  const color = isWorkday ? "#1890ff" : "#52c41a";
  const text = isWorkday ? "是工作日" : "不是工作日";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color, background: isWorkday ? "#e6f7ff" : "#f6ffed" }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>{text}</span>
    </div>
  );
};
export default React.memo(TimeIsWorkdayView);
