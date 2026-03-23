/**
 * ReadFileView - read_file 工具结果渲染组件
 *
 * 显示文件内容，支持带行号显示
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";

interface ReadFileViewProps {
  data: {
    content?: string;
    total_lines?: number;
    has_more?: boolean;
    file_path?: string;
  };
}

/**
 * ReadFileView 主组件
 */
const ReadFileView: React.FC<ReadFileViewProps> = ({ data }) => {
  const { content = "", total_lines = 0, file_path = "" } = data;

  if (!content) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        📄 文件为空
      </div>
    );
  }

  // 文件内容背景样式
  const contentBackground = {
    background: "#1e1e1e",
    border: "1px solid #303030",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.6,
    whiteSpace: "pre-wrap" as const,
    wordBreak: "break-all" as const,
    maxHeight: 400,
    overflow: "auto" as const,
    color: "#d4d4d4",
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
  };

  // 文件信息栏样式
  const fileInfoStyle = {
    marginBottom: 8,
    fontSize: 12,
    color: "#666",
    background: "#f5f5f5",
    padding: "4px 8px",
    borderRadius: 4,
  };

  return (
    <div>
      {/* 文件路径信息 */}
      {file_path && (
        <div style={fileInfoStyle}>
          📄 文件：{file_path}
        </div>
      )}

      {/* 文件内容 - 带行号 */}
      <div style={contentBackground}>
        {content.split("\n").map((line, index) => (
          <div
            key={index}
            style={{
              display: "flex",
              lineHeight: 1.6,
            }}
          >
            <span
              style={{
                minWidth: 40,
                color: "#858585",
                textAlign: "right",
                marginRight: 12,
                userSelect: "none",
              }}
            >
              {String(index + 1).padStart(4, " ")}
            </span>
            <span style={{ flex: 1 }}>{line || " "}</span>
          </div>
        ))}
      </div>

      {/* 总行数信息 */}
      {total_lines > 0 && (
        <div
          style={{
            marginTop: 8,
            fontSize: 12,
            color: "#666",
          }}
        >
          <span
            style={{
              background: "#e6f7ff",
              padding: "2px 8px",
              borderRadius: 4,
              color: "#1890ff",
              fontWeight: 500,
            }}
          >
            📊 共 {total_lines} 行
          </span>
        </div>
      )}
    </div>
  );
};

export default ReadFileView;
