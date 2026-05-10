/**
 * TimeIsWeekendView - time_is_weekend 工具结果渲染组件
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 * @update 2026-05-10 小健-重写UI，简洁清晰
 */

import React, { useMemo } from "react";
import { CalendarOutlined } from "@ant-design/icons";

interface TimeIsWeekendViewProps {
  data: {
    is_weekend?: boolean;
    weekday?: string;
    isoweekday?: number;
    date?: string;
  };
}

const TimeIsWeekendView: React.FC<TimeIsWeekendViewProps> = ({ data }) => {
  const {
    is_weekend = false,
    weekday = "",
    date = "",
  } = data || {};

  if (!data || !date) {
    return <div style={{ color: "#999", padding: "8px 12px" }}>周末数据为空</div>;
  }

  const color = is_weekend ? "#52c41a" : "#fa8c16";
  const text = is_weekend ? `${date} 是休息日（${weekday}）` : `${date} 是工作日（${weekday}）`;

  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "4px 10px",
      borderRadius: 4,
      fontSize: 13,
      color,
      background: is_weekend ? "#f6ffed" : "#fff7e6",
    }}>
      <CalendarOutlined />
      <span style={{ fontWeight: 500 }}>{text}</span>
    </div>
  );
};

export default React.memo(TimeIsWeekendView);
