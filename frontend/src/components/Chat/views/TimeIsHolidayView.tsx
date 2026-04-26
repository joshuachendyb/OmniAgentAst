/**
 * TimeIsHolidayView - time_is_holiday 工具结果渲染组件
 *
 * 显示是否为节假日
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { CheckCircleOutlined, CloseCircleOutlined, CalendarOutlined, GiftOutlined } from "@ant-design/icons";

interface TimeIsHolidayViewProps {
  data: {
    is_holiday?: boolean;
    holiday_name?: string | null;
    date?: string;
  };
}

/**
 * TimeIsHolidayView 主组件
 */
const TimeIsHolidayView: React.FC<TimeIsHolidayViewProps> = ({ data }) => {
  const {
    is_holiday = false,
    holiday_name = null,
    date = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !date;
  }, [data, date]);

  // 成功/失败样式
  const isHolidayDay = is_holiday;

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: isHolidayDay
      ? "linear-gradient(135deg, #fff1f0 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #f9f0ff 0%, #f5f5f5 100%)",
    border: `1px solid ${isHolidayDay ? "#ffccc7" : "#d3adf7"}`,
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [isHolidayDay]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: isHolidayDay ? "#ff4d4f" : "#722ed1",
  }), [isHolidayDay]);

  // 信息项样式
  const infoItemStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 8,
    fontSize: 13,
    color: "#595959",
  }), []);

  // 标签样式
  const labelStyle = useMemo(() => ({
    minWidth: 80,
    color: "#8c8c8c",
    marginRight: 8,
  }), []);

  // 状态徽章样式
  const badgeStyle = useMemo(() => ({
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 12px",
    borderRadius: 4,
    fontSize: 14,
    fontWeight: 500,
    background: isHolidayDay ? "#fff1f0" : "#f9f0ff",
    color: isHolidayDay ? "#ff4d4f" : "#722ed1",
  }), [isHolidayDay]);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        节假日数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {isHolidayDay ? (
          <>
            <GiftOutlined style={{ marginRight: 8 }} />
            节假日判定
          </>
        ) : (
          <>
            <CalendarOutlined style={{ marginRight: 8 }} />
            节假日判定
          </>
        )}
      </div>

      {/* 状态徽章 */}
      <div style={{ textAlign: "center", marginBottom: 16, padding: "12px 0" }}>
        <div style={badgeStyle}>
          {isHolidayDay ? <CheckCircleOutlined style={{ marginRight: 4 }} /> : <CloseCircleOutlined style={{ marginRight: 4 }} />}
          {isHolidayDay ? "今天是节假日" : "今天不是节假日"}
        </div>
      </div>

      {/* 日期 */}
      <div style={infoItemStyle}>
        <CalendarOutlined style={{ marginRight: 6, color: "#722ed1" }} />
        <span style={labelStyle}>日期：</span>
        <span style={{ fontWeight: 500 }}>{date}</span>
      </div>

      {/* 节假日名称 */}
      {isHolidayDay && holiday_name && (
        <div style={{ ...infoItemStyle, padding: "8px 12px", background: "#fff1f0", borderRadius: 4 }}>
          <GiftOutlined style={{ marginRight: 6, color: "#ff4d4f" }} />
          <span style={{ color: "#ff4d4f", fontWeight: 500 }}>
            {holiday_name}
          </span>
        </div>
      )}
    </div>
  );
};

export default React.memo(TimeIsHolidayView);