/**
 * TimerClearView - timer_clear 工具结果渲染组件
 *
 * 显示定时器取消结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimerClearViewProps {
  data: {
    timer_id?: string;
    cancelled?: boolean;
  };
}

/**
 * TimerClearView 主组件
 */
const TimerClearView: React.FC<TimerClearViewProps> = ({ data }) => {
  const {
    timer_id = "",
    cancelled = false,
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || !timer_id;
  }, [data, timer_id]);

  // 成功/失败样式
  const isSuccess = cancelled;

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: isSuccess
      ? "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)",
    border: `1px solid ${isSuccess ? "#b7eb8f" : "#ffa39e"}`,
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [isSuccess]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: isSuccess ? "#52c41a" : "#ff4d4f",
  }), [isSuccess]);

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
        {isSuccess ? (
          <>
            <CheckCircleOutlined style={{ marginRight: 8 }} />
            定时器已取消
          </>
        ) : (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            取消失败
          </>
        )}
      </div>

      {/* 定时器ID */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>ID：</span>
        <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
          {timer_id}
        </span>
      </div>

      {/* 状态 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>状态：</span>
        <span style={{ color: isSuccess ? "#52c41a" : "#ff4d4f", fontWeight: 500 }}>
          {cancelled ? "已取消" : "未取消"}
        </span>
      </div>
    </div>
  );
};

export default React.memo(TimerClearView);