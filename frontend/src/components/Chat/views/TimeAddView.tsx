// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * TimeAddView - timeadd 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空，结果时间全在 llm_data.summary 中，直接展示 summary + 成功徽标。
 *   不读不存在的 result_time/ unit_used/ delta_used/ tz 字段。
 *
 * @author 小沈
 * @version 2.0.0
 * @since 2026-04-21
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CalendarOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface TimeAddViewProps {
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

const TimeAddView: React.FC<TimeAddViewProps> = ({ summary, success }) => {
  return (
    <div style={containerStyle(success)}>
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <CalendarOutlined style={{ marginRight: 6 }} />
        时间计算{success ? "成功" : "失败"}
      </div>
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", fontFamily: "Consolas, Monaco, monospace", fontSize: 13 }}>
          {summary}
        </div>
      )}
    </div>
  );
};

export default React.memo(TimeAddView);
