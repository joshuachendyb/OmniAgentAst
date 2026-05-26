/**
 * TimeNowView - get_current_time 工具结果渲染组件
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 * @update 2026-05-10 小健-重写UI，简洁清晰
 */

import React, { useMemo } from "react";
import { ClockCircleOutlined, CalendarOutlined, GlobalOutlined } from "@ant-design/icons";

interface TimeNowViewProps {
  data: {
    iso?: string;
    timestamp?: number;
    format?: string;
    timezone?: string;
    weekday?: string;
    isoweekday?: number;
  };
}

const TimeNowView: React.FC<TimeNowViewProps> = ({ data }) => {
  const {
    format = "",
    timezone = "",
    weekday = "",
    isoweekday = 0,
  } = data || {};

  if (!data || !format) {
    return <div style={{ color: "#999", padding: "8px 12px" }}>时间数据为空</div>;
  }

  const isWeekend = isoweekday >= 6;
  const statusColor = isWeekend ? "#52c41a" : "#1890ff";
  const statusText = isWeekend ? "休息日" : "工作日";

  return (
    <div style={{
      padding: "8px 12px",
      borderRadius: 6,
      background: "#e6f7ff",
      border: "1px solid #91d5ff",
      fontSize: 13,
      lineHeight: "20px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <ClockCircleOutlined style={{ color: "#1890ff" }} />
        <span style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 14, fontWeight: 600, color: "#1890ff" }}>
          {format}
        </span>
        <span style={{ color: statusColor, fontSize: 12, background: isWeekend ? "#f6ffed" : "#e6f7ff", padding: "0 6px", borderRadius: 3 }}>
          {weekday} · {statusText}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, color: "#8c8c8c", fontSize: 12 }}>
        <span><GlobalOutlined style={{ marginRight: 4 }} />UTC{timezone}</span>
      </div>
    </div>
  );
};

export default React.memo(TimeNowView);
