import React from "react";
import { ClockCircleOutlined } from "@ant-design/icons";

interface Props { data: Array<{ timer_id?: string; callback?: string; remaining?: number; }>; }

const TimerListView: React.FC<Props> = ({ data }) => {
  const timers = data || [];
  if (!timers.length) return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 4, fontSize: 13, color: "#8c8c8c", background: "#f5f5f5" }}>
      <ClockCircleOutlined />
      <span>无活跃定时器</span>
    </div>
  );
  return (
    <div style={{ padding: "6px 10px", borderRadius: 4, background: "#f5f5f5", fontSize: 13 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#1890ff", fontWeight: 500, marginBottom: timers.length > 1 ? 4 : 0 }}>
        <ClockCircleOutlined />共 {timers.length} 个定时器
      </div>
      {timers.slice(0, 5).map((t, i) => (
        <div key={i} style={{ color: "#595959", fontSize: 12, marginLeft: 20 }}>
          {t.timer_id} — {t.callback || ""}{t.remaining != null ? ` (${t.remaining.toFixed(0)}s)` : ""}
        </div>
      ))}
      {timers.length > 5 && <div style={{ color: "#8c8c8c", fontSize: 12, marginLeft: 20 }}>...还有 {timers.length - 5} 个</div>}
    </div>
  );
};
export default React.memo(TimerListView);
