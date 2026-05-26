/**
 * TimeIsHolidayView - time_is_holiday 工具结果渲染组件
 *
 * @author 小强
 * @version 1.1.0
 * @since 2026-04-26
 * @update 2026-05-10 小健-重写UI，简洁清晰
 */

import React, { useMemo } from "react";
import { CalendarOutlined, GiftOutlined } from "@ant-design/icons";

interface TimeIsHolidayViewProps {
  data: {
    is_holiday?: boolean;
    holiday_name?: string | null;
    date?: string;
  };
}

const TimeIsHolidayView: React.FC<TimeIsHolidayViewProps> = ({ data }) => {
  const {
    is_holiday = false,
    holiday_name = null,
    date = "",
  } = data || {};

  if (!data || !date) {
    return <div style={{ color: "#999", padding: "8px 12px" }}>节假日数据为空</div>;
  }

  const color = is_holiday ? "#ff4d4f" : "#8c8c8c";
  const icon = is_holiday ? <GiftOutlined /> : <CalendarOutlined />;
  const text = is_holiday
    ? (holiday_name ? `${date} 是${holiday_name}` : `${date} 是节假日`)
    : `${date} 不是节假日`;

  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "4px 10px",
      borderRadius: 4,
      fontSize: 13,
      color,
      background: is_holiday ? "#fff1f0" : "#f5f5f5",
    }}>
      {icon}
      <span style={{ fontWeight: 500 }}>{text}</span>
    </div>
  );
};

export default React.memo(TimeIsHolidayView);
