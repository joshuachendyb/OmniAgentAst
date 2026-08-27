// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
import React from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface Props { data: boolean; }

const TimeIsWorkdayView: React.FC<Props> = ({ data }) => {
  const isWorkday = !!data;
  const color = isWorkday ? "#1677ff" : "#52c41a";
  const text = isWorkday ? "是工作日" : "不是工作日";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color, background: isWorkday ? "#e6f7ff" : "#f6ffed" }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>{text}</span>
    </div>
  );
};
export default React.memo(TimeIsWorkdayView);
