/**
 * TimerSetView - timer_set 工具结果渲染组件
 *
 * 显示定时器设置结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimerSetViewProps {
  data: {
    timer_id?: string;
    delay?: number;
    trigger_at?: string;
    callback?: string;
  };
}

/**
 * TimerSetView 主组件
 */
const TimerSetView: React.FC<TimerSetViewProps> = ({ data }) => {
  const {
    timer_id = "",
    delay = 0,
    trigger_at = "",
    callback = "",
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !timer_id;
  }, [data, timer_id]);

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
    fontSize: 24,
    fontWeight: 600,
    color: "#1890ff",
  }), []);

  // 格式化延迟时间
  const formatDelay = (seconds: number): string => {
    if (seconds < 60) return `${seconds}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`;
    return `${(seconds / 3600).toFixed(1)}小时`;
  };

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        定时器数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <CheckCircleOutlined style={{ marginRight: 8, color: "#52c41a" }} />
        定时器已设置
      </div>

      {/* 定时器ID */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>ID：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
          {timer_id}
        </span>
      </div>

      {/* 延迟时间 */}
      <div style={{ ...infoItemStyle, textAlign: "center", marginBottom: 16, padding: "12px 0" }}>
        <div style={bigNumberStyle}>{formatDelay(delay)}</div>
        <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 4 }}>延迟时间</div>
      </div>

      {/* 触发时间 */}
      {trigger_at && (
        <div style={infoItemStyle}>
          <ClockCircleOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
          <span style={labelStyle}>触发于：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
            {trigger_at}
          </span>
        </div>
      )}

      {/* 回调说明 */}
      {callback && (
        <div style={infoItemStyle}>
          <span style={labelStyle}>回调：</span>
          <span style={{ fontSize: 12, color: "#595959" }}>{callback}</span>
        </div>
      )}
    </div>
  );
};

export default React.memo(TimerSetView);