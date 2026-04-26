/**
 * TimeUtcToLocalView - time_utc_to_local 工具结果渲染组件
 *
 * 将UTC时间转换为本地时间显示
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { GlobalOutlined, ArrowRightOutlined } from "@ant-design/icons";

interface TimeUtcToLocalViewProps {
  data: {
    local_time?: string;
    timezone?: string;
    utc_original?: string;
  };
}

/**
 * TimeUtcToLocalView 主组件
 */
const TimeUtcToLocalView: React.FC<TimeUtcToLocalViewProps> = ({ data }) => {
  const {
    local_time = "",
    timezone = "",
    utc_original = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !local_time;
  }, [data, local_time]);

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

  // 大数字样式
  const bigNumberStyle = useMemo(() => ({
    fontSize: 16,
    fontWeight: 600,
    color: "#1890ff",
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
  }), []);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        时区转换数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <GlobalOutlined style={{ marginRight: 8 }} />
        UTC转本地时间
      </div>

      {/* 箭头转换显示 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, padding: "8px 0" }}>
        {/* UTC时间 */}
        <div style={{ textAlign: "center", flex: 1 }}>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>UTC</div>
          <div style={bigNumberStyle}>{utc_original}</div>
        </div>

        {/* 箭头 */}
        <ArrowRightOutlined style={{ margin: "0 16px", color: "#52c41a", fontSize: 20 }} />

        {/* 本地时间 */}
        <div style={{ textAlign: "center", flex: 1 }}>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>本地</div>
          <div style={bigNumberStyle}>{local_time}</div>
        </div>
      </div>

      {/* 时区 */}
      <div style={infoItemStyle}>
        <GlobalOutlined style={{ marginRight: 6, color: "#52c41a" }} />
        <span style={labelStyle}>时区：</span>
        <span style={{ fontWeight: 500, color: "#52c41a" }}>UTC{timezone}</span>
      </div>
    </div>
  );
};

export default React.memo(TimeUtcToLocalView);