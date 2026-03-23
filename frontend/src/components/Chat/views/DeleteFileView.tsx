/**
 * DeleteFileView - delete_file 工具结果渲染组件
 *
 * 显示文件删除结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";
import { DeleteOutlined } from "@ant-design/icons";

interface DeleteFileViewProps {
  data: {
    deleted_path?: string;
    message?: string;
  };
}

/**
 * DeleteFileView 主组件
 */
const DeleteFileView: React.FC<DeleteFileViewProps> = ({ data }) => {
  const { deleted_path = "", message = "" } = data;

  if (!deleted_path && !message) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        🗑️ 删除结果为空
      </div>
    );
  }

  // 删除成功样式
  const deleteStyle = {
    background: "linear-gradient(135deg, #fff1f0 0%, #f5f5f5 100%)",
    border: "1px solid #ffa39e",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.8,
  };

  return (
    <div style={deleteStyle}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
        <DeleteOutlined style={{ color: "#ff4d4f", fontSize: 18, marginRight: 8 }} />
        <span style={{ color: "#ff4d4f", fontWeight: 600 }}>
          文件删除成功
        </span>
      </div>

      {/* 删除路径 */}
      {deleted_path && (
        <div style={{ marginTop: 8 }}>
          <span style={{ color: "#666" }}>🗑️ 删除路径：</span>
          <code
            style={{
              background: "#f5f5f5",
              padding: "2px 6px",
              borderRadius: 4,
              fontFamily: "Consolas, Monaco, 'Courier New', monospace",
              fontSize: 12,
            }}
          >
            {deleted_path}
          </code>
        </div>
      )}

      {/* 消息 */}
      {message && (
        <div style={{ marginTop: 8, color: "#666" }}>{message}</div>
      )}
    </div>
  );
};

export default DeleteFileView;
