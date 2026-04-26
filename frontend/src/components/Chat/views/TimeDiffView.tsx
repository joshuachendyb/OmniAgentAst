/**
 * TimeDiffView - time_diff 工具结果渲染组件
 *
 * 显示两个时间之间的差值
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { ClockCircleOutlined, ArrowRightOutlined } from "@ant-design/icons";

interface TimeDiffViewProps {
  data: {
    humanized?: string;
    seconds?: number;
    minutes?: number;
    hours?: number;
    days?: number;
    is_future?: boolean;
  };
}

/**
 * TimeDiffView 主组件
 */
const TimeDiffView: React.FC<TimeDiffViewProps> = ({ data }) => {
  const {
    humanized = "",
    seconds = 0,
    minutes = 0,
    hours = 0,
    days = 0,
    is_future = false,
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!seconds && !humanized);
  }, [data, seconds, humanized]);

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: is_future
      ? "linear-gradient(135deg, #fff7e6 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: `1px solid ${is_future ? "#ffd591" : "#91d5ff"}`,
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [is_future]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: is_future ? "#fa8c16" : "#1890ff",
  }), [is_future]);

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

  // 人性化大数字样式
  const bigNumberStyle = useMemo(() => ({
    fontSize: 24,
    fontWeight: 600,
    color: is_future ? "#fa8c16" : "#1890ff",
  }), [is_future]);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 时间差数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <ClockCircleOutlined style={{ marginRight: 8 }} />
        ⏱️ 时间差
      </div>

      {/* 人性化描述 - 大数字突出显示 */}
      <div style={{ textAlign: "center", marginBottom: 16, padding: "12px 0" }}>
        <div style={bigNumberStyle}>{humanized}</div>
        <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 4 }}>
          {is_future ? "📍 未来时间" : "📍 过去时间"}
        </div>
      </div>

      {/* 详细数值 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>⏰ 总计：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>
          {seconds} 秒
        </span>
      </div>

      {/* 各单位 */}
      {days > 0 && (
        <div style={infoItemStyle}>
          <ArrowRightOutlined style={{ marginRight: 6, color: "#52c41a" }} />
          <span style={labelStyle}>📅 天数：</span>
          <span>{days.toFixed(1)} 天</span>
        </div>
      )}

      {hours > 0 && hours < 24 && (
        <div style={infoItemStyle}>
          <ArrowRightOutlined style={{ marginRight: 6, color: "#1890ff" }} />
          <span style={labelStyle}>⏱️ 小时：</span>
          <span>{hours.toFixed(1)} 小时</span>
        </div>
      )}

      {minutes > 0 && minutes < 60 && (
        <div style={infoItemStyle}>
          <ArrowRightOutlined style={{ marginRight: 6, color: "#722ed1" }} />
          <span style={labelStyle}>⏲ 分钟：</span>
          <span>{minutes.toFixed(1)} 分钟</span>
        </div>
      )}

      {seconds > 0 && seconds < 60 && (
        <div style={infoItemStyle}>
          <ArrowRightOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
          <span style={labelStyle}>🔢 秒数：</span>
          <span>{seconds} 秒</span>
        </div>
      )}
    </div>
  );
};

export default React.memo(TimeDiffView);