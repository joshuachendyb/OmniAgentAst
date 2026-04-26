/**
 * TimeFormatView - time_format 工具结果渲染组件
 *
 * 格式化时间戳显示
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { ClockCircleOutlined, CalendarOutlined } from "@ant-design/icons";

interface TimeFormatViewProps {
  data: {
    formatted?: string;
    iso?: string;
    timestamp?: number;
    pattern_used?: string;
  };
}

/**
 * TimeFormatView 主组件
 */
const TimeFormatView: React.FC<TimeFormatViewProps> = ({ data }) => {
  const {
    formatted = "",
    iso = "",
    timestamp = 0,
    pattern_used = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!timestamp && !formatted);
  }, [data, timestamp, formatted]);

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: "linear-gradient(135deg, #fff7e6 0%, #f5f5f5 100%)",
    border: "1px solid #ffd591",
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
    color: "#fa8c16",
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

  // 大数字样式
  const bigNumberStyle = useMemo(() => ({
    fontSize: 18,
    fontWeight: 600,
    color: "#fa8c16",
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
  }), []);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 格式化时间数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <ClockCircleOutlined style={{ marginRight: 8 }} />
        📝 时间格式化
      </div>

      {/* 格式化后的时间 */}
      <div style={infoItemStyle}>
        <CalendarOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
        <span style={labelStyle}>📅 日期：</span>
        <span style={bigNumberStyle}>{formatted}</span>
      </div>

      {/* 使用的格式 */}
      {pattern_used && (
        <div style={infoItemStyle}>
          <span style={labelStyle}>🔧 格式：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 11 }}>
            {pattern_used}
          </span>
        </div>
      )}

      {/* ISO格式 */}
      {iso && (
        <div style={infoItemStyle}>
          <span style={labelStyle}>📋 ISO：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 11, color: "#8c8c8c" }}>
            {iso}
          </span>
        </div>
      )}

      {/* 时间戳 */}
      {timestamp > 0 && (
        <div style={infoItemStyle}>
          <span style={labelStyle}>🔢 时间戳：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
            {timestamp}
          </span>
        </div>
      )}
    </div>
  );
};

export default React.memo(TimeFormatView);