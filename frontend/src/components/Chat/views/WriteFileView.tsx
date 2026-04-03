/**
 * WriteFileView - write_file 工具结果渲染组件
 *
 * 显示文件写入结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined } from "@ant-design/icons";

interface WriteFileViewProps {
  data: {
    file_path?: string;
    bytes_written?: number;
    message?: string;
  };
}

/**
 * WriteFileView 主组件
 */
const WriteFileView: React.FC<WriteFileViewProps> = ({ data }) => {
  const { file_path = "", bytes_written = 0, message = "" } = data;

  if (!file_path && !message) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        ✍️ 写入结果为空
      </div>
    );
  }

  // 成功样式
  const successStyle = {
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.8,
  };

  return (
    <div style={successStyle}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
        <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 18, marginRight: 8 }} />
        <span style={{ color: "#52c41a", fontWeight: 600 }}>
          文件写入成功
        </span>
      </div>

      {/* 文件路径 */}
      {file_path && (
        <div style={{ marginTop: 8 }}>
          <span style={{ color: "#666" }}>📝 文件路径：</span>
          <code
            style={{
              background: "#f5f5f5",
              padding: "2px 6px",
              borderRadius: 4,
              fontFamily: "Consolas, Monaco, 'Courier New', monospace",
              fontSize: 12,
            }}
          >
            {file_path}
          </code>
        </div>
      )}

      {/* 写入字节数 */}
      {bytes_written > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ color: "#666" }}>📊 写入字节：</span>
          <span style={{ fontWeight: 500 }}>{formatBytes(bytes_written)}</span>
        </div>
      )}

      {/* 消息 */}
      {message && (
        <div style={{ marginTop: 8, color: "#666" }}>{message}</div>
      )}
    </div>
  );
};

/**
 * 格式化字节数
 */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024)
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

export default WriteFileView;
