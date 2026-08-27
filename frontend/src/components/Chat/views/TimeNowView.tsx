// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
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
import { viewOuter } from './viewTokens';
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimeNowViewProps {
  summary?: string;
  success: boolean;
}

const containerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter, fontSize: 13, lineHeight: 1.8 });

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
