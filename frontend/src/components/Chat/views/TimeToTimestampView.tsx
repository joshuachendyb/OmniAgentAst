import React from "react";
import { SwapOutlined } from "@ant-design/icons";

interface Props { data: number; }

const TimeToTimestampView: React.FC<Props> = ({ data }) => {
  const ts = data || 0;
  if (!ts) return <span style={{ color: "#999" }}>时间戳为空</span>;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#595959", background: "#f5f5f5" }}>
      <SwapOutlined />
      <span style={{ fontWeight: 500 }}>时间戳：</span>
      <span style={{ fontFamily: "Consolas, Monaco, monospace" }}>{ts}</span>
    </div>
  );
};
export default React.memo(TimeToTimestampView);
