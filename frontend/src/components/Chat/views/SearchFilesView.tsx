/**
 * SearchFilesView - find 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   仅展示 data.matches（路径、大小、类型）+ metrics.total 总数 + summary；
 *   不读不存在的 files_matched/ search_pattern/ pagination 等字段。
 *
 * @author 小强
 * @version 3.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FileOutlined, FolderOutlined, SearchOutlined } from "@ant-design/icons";

interface FileMatch {
  name?: string;
  path?: string;
  relative_path?: string;
  type?: string;
  size?: number;
}

interface SearchFilesViewProps {
  data: {
    matches: FileMatch[];
    total_matches: number;
  };
  metrics: {
    total: number;
  };
  summary?: string;
  success: boolean;
}

const formatFileSize = (bytes?: number): string => {
  if (bytes === undefined || bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const searchContainerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
});

const searchTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const SearchFilesView: React.FC<SearchFilesViewProps> = ({ data, metrics, summary, success }) => {
  const { matches, total_matches } = data;
  const total = metrics.total || total_matches || matches.length;

  if (matches.length === 0) {
    return (
      <div style={searchContainerStyle(success)}>
        <div style={searchTitleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          搜索文件{success ? "成功" : "失败"}
        </div>
        <div style={{ color: "#888", fontStyle: "italic" }}>
          <SearchOutlined style={{ marginRight: 6 }} />
          未找到匹配结果
        </div>
      </div>
    );
  }

  return (
    <div style={searchContainerStyle(success)}>
      {/* 标题 */}
      <div style={searchTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        搜索文件{success ? "成功" : "失败"}
      </div>

      {/* 总数 */}
      <div style={{ marginBottom: 8, fontSize: 12, color: "#595959" }}>
        共匹配 <strong style={{ color: "#1890ff" }}>{total}</strong> 个文件
      </div>

      {/* 匹配列表 */}
      <div style={{ background: "#fafafa", borderRadius: 6, padding: "6px 10px", maxHeight: 360, overflow: "auto" }}>
        {matches.map((m, idx) => {
          const isDir = m.type === "directory";
          const displayPath = m.path || m.relative_path || m.name || "(未知路径)";
          const sizeStr = formatFileSize(m.size);
          return (
            <div
              key={`${displayPath}-${idx}`}
              style={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                padding: "5px 0",
                borderBottom: idx < matches.length - 1 ? "1px solid #f0f0f0" : "none",
                fontSize: 13,
              }}
            >
              {isDir ? (
                <FolderOutlined style={{ color: "#faad14", marginRight: 6 }} />
              ) : (
                <FileOutlined style={{ color: "#1890ff", marginRight: 6 }} />
              )}
              <code
                style={{
                  background: "#e6f7ff",
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                  fontSize: 12,
                  color: "#003a8c",
                  wordBreak: "break-all",
                }}
              >
                {displayPath}
              </code>
              {sizeStr && (
                <span style={{ color: "#8c8c8c", fontSize: 12, marginLeft: 8 }}>{sizeStr}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(SearchFilesView);
