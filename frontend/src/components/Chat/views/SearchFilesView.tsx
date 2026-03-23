/**
 * SearchFilesView - search_files 工具结果渲染组件
 *
 * 显示文件搜索结果，包含匹配详情
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React from "react";
import { List, Tag } from "antd";
import { FileTextOutlined } from "@ant-design/icons";

interface Match {
  file_path: string;
  line_number?: number;
  line_content?: string;
}

interface SearchFilesViewProps {
  data: {
    files_matched?: number;
    total_matches?: number;
    matches?: Match[];
    search_pattern?: string;
  };
}

/**
 * SearchFilesView 主组件
 */
const SearchFilesView: React.FC<SearchFilesViewProps> = ({ data }) => {
  const {
    files_matched = 0,
    total_matches = 0,
    matches = [],
    search_pattern = "",
  } = data;

  if (files_matched === 0 && matches.length === 0) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        🔍 未找到匹配结果
      </div>
    );
  }

  // 搜索结果背景样式
  const searchResultStyle = {
    background: "linear-gradient(135deg, #fff7e6 0%, #f5f5f5 100%)",
    border: "1px solid #ffd591",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.8,
    maxHeight: 400,
    overflow: "auto",
  };

  return (
    <div>
      {/* 搜索统计信息 */}
      <div
        style={{
          marginBottom: 8,
          fontSize: 12,
          color: "#666",
        }}
      >
        <Tag color="orange" style={{ marginRight: 8 }}>
          🔍 搜索模式：{search_pattern}
        </Tag>
        <span
          style={{
            background: "#e6f7ff",
            padding: "2px 8px",
            borderRadius: 4,
            color: "#1890ff",
            fontWeight: 500,
            marginRight: 8,
          }}
        >
          📁 {files_matched} 个文件
        </span>
        <span
          style={{
            background: "#f6ffed",
            padding: "2px 8px",
            borderRadius: 4,
            color: "#52c41a",
            fontWeight: 500,
          }}
        >
          🔎 {total_matches} 处匹配
        </span>
      </div>

      {/* 匹配详情列表 */}
      {matches.length > 0 && (
        <div style={searchResultStyle}>
          <List
            dataSource={matches}
            size="small"
            renderItem={(match: Match, index: number) => (
              <List.Item
                key={`match-${index}`}
                style={{
                  padding: "8px 12px",
                  borderBottom:
                    index < matches.length - 1
                      ? "1px solid #e8e8e8"
                      : "none",
                }}
              >
                <div style={{ width: "100%" }}>
                  {/* 文件路径 */}
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <FileTextOutlined
                      style={{ color: "#1890ff", marginRight: 6 }}
                    />
                    <code
                      style={{
                        background: "#f5f5f5",
                        padding: "2px 6px",
                        borderRadius: 4,
                        fontFamily:
                          "Consolas, Monaco, 'Courier New', monospace",
                        fontSize: 12,
                      }}
                    >
                      {match.file_path}
                    </code>
                    {match.line_number && (
                      <Tag style={{ marginLeft: 8 }}>
                        行 {match.line_number}
                      </Tag>
                    )}
                  </div>

                  {/* 匹配内容 */}
                  {match.line_content && (
                    <div
                      style={{
                        marginTop: 6,
                        background: "#1e1e1e",
                        padding: "6px 10px",
                        borderRadius: 4,
                        color: "#d4d4d4",
                        fontFamily:
                          "Consolas, Monaco, 'Courier New', monospace",
                        fontSize: 12,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                      }}
                    >
                      {match.line_content}
                    </div>
                  )}
                </div>
              </List.Item>
            )}
          />
        </div>
      )}
    </div>
  );
};

export default SearchFilesView;
