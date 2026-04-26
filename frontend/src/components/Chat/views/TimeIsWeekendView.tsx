/**
 * TimeIsWeekendView - time_is_weekend 工具结果渲染组件
 *
 * 显示是否为周末
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { CheckCircleOutlined, CloseCircleOutlined, CalendarOutlined, ClockCircleOutlined, NumberOutlined } from "@ant-design/icons";

interface TimeIsWeekendViewProps {
  data: {
    is_weekend?: boolean;
    weekday?: string;
    isoweekday?: number;
    date?: string;
  };
}

/**
 * TimeIsWeekendView 主组件
 */
const TimeIsWeekendView: React.FC<TimeIsWeekendViewProps> = ({ data }) => {
  const {
    is_weekend = false,
    weekday = "",
    isoweekday = 0,
    date = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !date;
  }, [data, date]);

  // 成功/失败样式
  const isWeekendDay = is_weekend;

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: isWeekendDay
      ? "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #fff7e6 0%, #f5f5f5 100%)",
    border: `1px solid ${isWeekendDay ? "#b7eb8f" : "#ffd591"}`,
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [isWeekendDay]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: isWeekendDay ? "#52c41a" : "#fa8c16",
  }), [isWeekendDay]);

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
    background: isWeekendDay ? "#f6ffed" : "#fff7e6",
    color: isWeekendDay ? "#52c41a" : "#fa8c16",
  }), [isWeekendDay]);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        周末数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {isWeekendDay ? (
          <>
            <CheckCircleOutlined style={{ marginRight: 8 }} />
            周末判定
          </>
        ) : (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            周末判定
          </>
        )}
      </div>

      {/* 状态徽章 */}
      <div style={{ textAlign: "center", marginBottom: 16, padding: "12px 0" }}>
        <div style={badgeStyle}>
          {isWeekendDay ? <CheckCircleOutlined style={{ marginRight: 4 }} /> : <ClockCircleOutlined style={{ marginRight: 4 }} />}
          {isWeekendDay ? "今天是休息日" : "今天是工作日"}
        </div>
      </div>

      {/* 日期 */}
      <div style={infoItemStyle}>
        <CalendarOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
        <span style={labelStyle}>日期：</span>
        <span style={{ fontWeight: 500 }}>{date}</span>
      </div>

      {/* 星期几 */}
      <div style={infoItemStyle}>
        <CalendarOutlined style={{ marginRight: 6, color: isWeekendDay ? "#52c41a" : "#1890ff" }} />
        <span style={labelStyle}>星期：</span>
        <span style={{ color: isWeekendDay ? "#52c41a" : "#1890ff", fontWeight: 500 }}>
          {weekday}
        </span>
      </div>

      {/* ISO星期 */}
      <div style={infoItemStyle}>
        <NumberOutlined style={{ marginRight: 6, color: "#1890ff" }} />
        <span style={labelStyle}>ISO：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
          星期{isoweekday} (1=周一, 7=周日)
        </span>
      </div>
    </div>
  );
};

export default React.memo(TimeIsWeekendView);