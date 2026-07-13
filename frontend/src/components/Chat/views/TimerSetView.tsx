/**
 * TimerSetView - timer_set 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   展示 data.trigger_at（触发时间）+ metrics.delay（延迟）+ llm_data.summary；
 *   不读不存在的 timer_id/ callback 字段（timer_id 在 summary 文案中）。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-26
 */

import React from "react";
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimerSetViewProps {
  data: {
    trigger_at: string;
  };
  metrics: {
    delay: number;
  };
  summary?: string;
  success: boolean;
}

const formatDelay = (seconds: number): string => {
  if (seconds === null || seconds === undefined || seconds <= 0) return "-";
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`;
  return `${(seconds / 3600).toFixed(1)} 小时`;
};

const containerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
});

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const infoItemStyle: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const labelStyle: React.CSSProperties = { minWidth: 84, color: "#8c8c8c", marginRight: 8 };

const TimerSetView: React.FC<TimerSetViewProps> = ({ data, metrics, summary, success }) => {
  const { trigger_at } = data;
  const { delay } = metrics;

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        定时器{success ? "已设置" : "设置失败"}
      </div>

      {/* 触发时间 */}
      {trigger_at && (
        <div style={infoItemStyle}>
          <ClockCircleOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
          <span style={labelStyle}>触发于：</span>
          <span style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 12 }}>{trigger_at}</span>
        </div>
      )}

      {/* 延迟 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>延迟：</span>
        <span style={{ fontWeight: 600, color: "#1890ff" }}>{formatDelay(delay)}</span>
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(TimerSetView);
