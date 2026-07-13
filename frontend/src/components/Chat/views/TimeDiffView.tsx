/**
 * TimeDiffView - timediff 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   展示 llm_data.metrics: {seconds,days} + llm_data.summary（中文相对描述）+ 成功徽标。
 *   不读不存在的 humanized/ minutes/ hours/ is_future 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-26
 */

import React from "react";
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimeDiffViewProps {
  metrics: {
    seconds: number;
    days: number;
  };
  summary?: string;
  success: boolean;
}

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

const formatDuration = (totalSeconds: number): string => {
  const abs = Math.abs(totalSeconds);
  const d = Math.floor(abs / 86400);
  const h = Math.floor((abs % 86400) / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;
  const parts: string[] = [];
  if (d > 0) parts.push(`${d} 天`);
  if (h > 0) parts.push(`${h} 小时`);
  if (m > 0) parts.push(`${m} 分`);
  if (s > 0 || parts.length === 0) parts.push(`${s} 秒`);
  return parts.join(" ");
};

const TimeDiffView: React.FC<TimeDiffViewProps> = ({ metrics, summary, success }) => {
  const { seconds, days } = metrics;

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <ClockCircleOutlined style={{ marginRight: 6 }} />
        时间差计算{success ? "成功" : "失败"}
      </div>

      {/* 秒数 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>总计：</span>
        <span style={{ fontFamily: "Consolas, Monaco, monospace" }}>{formatDuration(seconds)}（{seconds} 秒）</span>
      </div>

      {/* 天数 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>天数：</span>
        <span>{days} 天</span>
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(TimeDiffView);
