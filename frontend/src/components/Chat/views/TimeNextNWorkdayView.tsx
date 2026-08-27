// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
import React from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface Props { data: string[]; }

const TimeNextNWorkdayView: React.FC<Props> = ({ data }) => {
  const dates = data || [];
  if (!dates.length) return <span style={{ color: "#999" }}>无工作日数据</span>;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#1677ff", background: "#e6f7ff" }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>接下来 {dates.length} 个工作日：</span>
      <span>{dates.join("、")}</span>
    </div>
  );
};
export default React.memo(TimeNextNWorkdayView);
