/**
 * TimeLocalToUtcView - time_local_to_utc 工具结果渲染组件
 *
 * 将本地时间转换为UTC时间显示
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { GlobalOutlined, ArrowRightOutlined } from "@ant-design/icons";

interface TimeLocalToUtcViewProps {
  data: {
    utc_time?: string;
    source_timezone?: string;
    local_original?: string;
  };
}

/**
 * TimeLocalToUtcView 主组件
 */
const TimeLocalToUtcView: React.FC<TimeLocalToUtcViewProps> = ({ data }) => {
  const {
    utc_time = "",
    source_timezone = "",
    local_original = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !utc_time;
  }, [data, utc_time]);

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
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
    color: "#52c41a",
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
    color: "#52c41a",
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
        本地时间转UTC
      </div>

      {/* 箭头转换显示 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, padding: "8px 0" }}>
        {/* 本地时间 */}
        <div style={{ textAlign: "center", flex: 1 }}>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>本地时间</div>
          <div style={bigNumberStyle}>{local_original}</div>
        </div>

        {/* 箭头 */}
        <ArrowRightOutlined style={{ margin: "0 16px", color: "#1890ff", fontSize: 20 }} />

        {/* UTC时间 */}
        <div style={{ textAlign: "center", flex: 1 }}>
          <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>UTC</div>
          <div style={bigNumberStyle}>{utc_time}</div>
        </div>
      </div>

      {/* 源时区 */}
      <div style={infoItemStyle}>
        <GlobalOutlined style={{ marginRight: 6, color: "#1890ff" }} />
        <span style={labelStyle}>源时区：</span>
        <span style={{ fontWeight: 500, color: "#1890ff" }}>UTC{source_timezone}</span>
      </div>
    </div>
  );
};

export default React.memo(TimeLocalToUtcView);