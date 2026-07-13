/**
 * DeleteFileView - delete 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空，直接展示 llm_data.summary；可选展示 metrics.mode/status。
 *   不读不存在的 deleted_path/ message 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined } from "@ant-design/icons";

interface DeleteFileViewProps {
  metrics: {
    mode: string;
    status: string;
  };
  summary?: string;
  success: boolean;
}

const deleteContainerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
  fontSize: 13,
  lineHeight: 1.8,
});

const deleteTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 8,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const DeleteFileView: React.FC<DeleteFileViewProps> = ({ metrics, summary, success }) => {
  const { mode, status } = metrics;
  const modeText = mode
    ? mode === "permanent"
      ? "永久删除"
      : mode === "send2trash"
      ? "移至回收站"
      : mode
    : status === "already_deleted"
    ? "此前已删除"
    : "";

  return (
    <div style={deleteContainerStyle(success)}>
      <div style={deleteTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <DeleteOutlined style={{ marginRight: 6 }} />
        删除文件{success ? "成功" : "失败"}
      </div>

      {modeText && (
        <div style={{ marginTop: 4, color: "#595959" }}>
          <span style={{ color: "#8c8c8c", marginRight: 8 }}>方式：</span>
          {modeText}
        </div>
      )}

      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(DeleteFileView);
