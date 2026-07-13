/**
 * TimeNowView - timenow 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空，时间结果全在 llm_data.summary 中，直接展示 summary + 成功徽标。
 *   不读不存在的 iso/ timestamp/ format/ timezone/ weekday 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-26
 */

import React from "react";
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimeNowViewProps {
  summary?: string;
  success: boolean;
}

const containerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
  fontSize: 13,
  lineHeight: 1.8,
});

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 8,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const TimeNowView: React.FC<TimeNowViewProps> = ({ summary, success }) => {
  return (
    <div style={containerStyle(success)}>
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <ClockCircleOutlined style={{ marginRight: 6 }} />
        获取当前时间{success ? "成功" : "失败"}
      </div>
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", fontFamily: "Consolas, Monaco, monospace", fontSize: 13 }}>
          {summary}
        </div>
      )}
    </div>
  );
};

export default React.memo(TimeNowView);
