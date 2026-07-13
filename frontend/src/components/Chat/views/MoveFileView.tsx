/**
 * MoveFileView - move 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空，直接展示 llm_data.summary（如「移动成功: A -> B」）。
 *   不读不存在的 source/ destination/ message 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, SendOutlined } from "@ant-design/icons";

interface MoveFileViewProps {
  summary?: string;
  success: boolean;
}

const moveContainerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
  fontSize: 13,
  lineHeight: 1.8,
});

const moveTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 8,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const MoveFileView: React.FC<MoveFileViewProps> = ({ summary, success }) => {
  return (
    <div style={moveContainerStyle(success)}>
      <div style={moveTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <SendOutlined style={{ marginRight: 6 }} />
        移动文件{success ? "成功" : "失败"}
      </div>

      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap" }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(MoveFileView);
