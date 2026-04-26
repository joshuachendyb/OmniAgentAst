/**
 * TimeNowView - time_now 工具结果渲染组件
 *
 * 显示当前系统时间
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { ClockCircleOutlined, CalendarOutlined, GlobalOutlined, NumberOutlined, FileTextOutlined, CheckCircleOutlined } from "@ant-design/icons";

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

/**
 * 空数据检查
 */
const checkEmptyData = (data: TimeNowViewProps["data"]): boolean => {
  return !data || (!data.timestamp && !data.format);
};

/**
 * TimeNowView 主组件
 */
const TimeNowView: React.FC<TimeNowViewProps> = ({ data }) => {
  // 默认值处理
  const {
    iso = "",
    timestamp = 0,
    format = "",
    timezone = "",
    weekday = "",
    isoweekday = 0,
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!timestamp && !format);
  }, [data, timestamp, format]);

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: "1px solid #91d5ff",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), []);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: "#1890ff",
  }), []);

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

  // 工作日/休息日样式
  const isWeekend = isoweekday >= 6;
  const statusStyle = useMemo(() => ({
    color: isWeekend ? "#52c41a" : "#1890ff",
    fontWeight: 500,
  }), [isWeekend]);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        时间数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <ClockCircleOutlined style={{ marginRight: 8 }} />
        当前时间
      </div>

      {/* 时间显示 */}
      <div style={infoItemStyle}>
        <ClockCircleOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
        <span style={labelStyle}>时间：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 14 }}>
          {format}
        </span>
      </div>

      {/* 日期 */}
      <div style={infoItemStyle}>
        <CalendarOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
        <span style={labelStyle}>日期：</span>
        <span>{weekday}</span>
      </div>

      {/* 时区 */}
      <div style={infoItemStyle}>
        <GlobalOutlined style={{ marginRight: 6, color: "#52c41a" }} />
        <span style={labelStyle}>时区：</span>
        <span>UTC{timezone}</span>
      </div>

      {/* 时间戳 */}
      <div style={infoItemStyle}>
        <NumberOutlined style={{ marginRight: 6, color: "#1890ff" }} />
        <span style={labelStyle}>时间戳：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
          {timestamp}
        </span>
      </div>

      {/* ISO格式 */}
      <div style={infoItemStyle}>
        <FileTextOutlined style={{ marginRight: 6, color: "#8c8c8c" }} />
        <span style={labelStyle}>ISO：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 11, color: "#8c8c8c" }}>
          {iso}
        </span>
      </div>

      {/* 星期状态 */}
      <div style={{ ...infoItemStyle, marginTop: 8, paddingTop: 8, borderTop: "1px dashed #d9d9d9" }}>
        <span style={statusStyle}>
          {isWeekend ? <CheckCircleOutlined style={{ marginRight: 4 }} /> : <ClockCircleOutlined style={{ marginRight: 4 }} />}
          {isWeekend ? "今天是休息日" : "今天是工作日"}
        </span>
      </div>
    </div>
  );
};

export default React.memo(TimeNowView);