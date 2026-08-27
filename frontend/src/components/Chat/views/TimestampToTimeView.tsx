// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
import React from "react";
import { ClockCircleOutlined } from "@ant-design/icons";

interface Props { data: { datetime?: string; timezone?: string; }; }

const TimestampToTimeView: React.FC<Props> = ({ data }) => {
  const { datetime = "", timezone = "" } = data || {};
  if (!datetime) return <span style={{ color: "#999" }}>时间为空</span>;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#1677ff", background: "#e6f7ff" }}>
      <ClockCircleOutlined />
      <span style={{ fontWeight: 500, fontFamily: "Consolas, Monaco, monospace" }}>{datetime}</span>
      <span style={{ fontSize: 11, color: "#8c8c8c" }}>UTC{timezone}</span>
    </div>
  );
};
export default React.memo(TimestampToTimeView);
