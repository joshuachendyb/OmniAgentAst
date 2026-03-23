/**
 * MoveFileView - move_file 工具结果渲染组件
 *
 * 显示文件/文件夹移动结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined } from "@ant-design/icons";

interface MoveFileViewProps {
  data: {
    source?: string;
    destination?: string;
    message?: string;
  };
}

/**
 * MoveFileView 主组件
 */
const MoveFileView: React.FC<MoveFileViewProps> = ({ data }) => {
  const { source = "", destination = "", message = "" } = data;

  if (!source && !destination && !message) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        📦 移动结果为空
      </div>
    );
  }

  // 移动成功样式
  const moveStyle = {
    background: "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: "1px solid #91d5ff",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.8,
  };

  return (
    <div style={moveStyle}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
        <CheckCircleOutlined style={{ color: "#1890ff", fontSize: 18, marginRight: 8 }} />
        <span style={{ color: "#1890ff", fontWeight: 600 }}>
          文件移动成功
        </span>
      </div>

      {/* 源路径 */}
      {source && (
        <div style={{ marginTop: 8 }}>
          <span style={{ color: "#666" }}>📤 源路径：</span>
          <code
            style={{
              background: "#f5f5f5",
              padding: "2px 6px",
              borderRadius: 4,
              fontFamily: "Consolas, Monaco, 'Courier New', monospace",
              fontSize: 12,
            }}
          >
            {source}
          </code>
        </div>
      )}

      {/* 目标路径 */}
      {destination && (
        <div style={{ marginTop: 8 }}>
          <span style={{ color: "#666" }}>📥 目标路径：</span>
          <code
            style={{
              background: "#f5f5f5",
              padding: "2px 6px",
              borderRadius: 4,
              fontFamily: "Consolas, Monaco, 'Courier New', monospace",
              fontSize: 12,
            }}
          >
            {destination}
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

export default MoveFileView;
