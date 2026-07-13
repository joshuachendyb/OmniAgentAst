/**
 * TimerListView - timer_list 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   展示 data.timers（id、回调、创建时间、触发时间、状态）+ metrics.count；
 *   不读不存在的 remaining 字段。
 *
 * @author 小沈
 * @version 2.0.0
 * @since 2026-04-21
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from "@ant-design/icons";

interface TimerItem {
  timer_id?: string;
  callback?: string;
  created_at?: string;
  trigger_at?: string;
  status?: string;
}

interface TimerListViewProps {
  data: {
    timers: TimerItem[];
  };
  metrics: {
    count: number;
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

const TimerListView: React.FC<TimerListViewProps> = ({ data, metrics, summary, success }) => {
  const timers = data.timers || [];
  const total = metrics.count || timers.length;

  if (timers.length === 0) {
    return (
      <div style={containerStyle(success)}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          定时器列表{success ? "成功" : "失败"}
        </div>
        <div style={{ color: "#888", fontStyle: "italic" }}>无活跃定时器</div>
      </div>
    );
  }

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <ClockCircleOutlined style={{ marginRight: 6 }} />
        定时器列表（{total} 个）
      </div>

      {/* 定时器列表 */}
      <div style={{ background: "#fafafa", borderRadius: 6, padding: "6px 10px" }}>
        {timers.map((t, i) => (
          <div
            key={t.timer_id || i}
            style={{
              padding: "5px 0",
              borderBottom: i < timers.length - 1 ? "1px solid #f0f0f0" : "none",
              fontSize: 13,
              color: "#595959",
            }}
          >
            <span style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 12, color: "#003a8c" }}>{t.timer_id}</span>
            {t.status && <span style={{ marginLeft: 8, color: "#8c8c8c" }}>状态：{t.status}</span>}
            {t.trigger_at && <span style={{ marginLeft: 8, color: "#8c8c8c" }}>触发：{t.trigger_at}</span>}
            {t.callback && <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 2 }}>回调：{t.callback}</div>}
          </div>
        ))}
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(TimerListView);
