/**
 * ListDirectoryView - listdir 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   只展示 data.entries（名称/类型图标/大小/修改时间）+ metrics 统计
 *   （总文件数/目录数/总大小）+ llm_data.summary；不读不存在字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FolderOutlined, FileOutlined, InboxOutlined } from "@ant-design/icons";

interface DirEntry {
  name?: string;
  type?: "file" | "directory";
  mtime?: number | string;
  size?: number;
}

interface ListDirectoryViewProps {
  data: {
    entries: DirEntry[];
    truncated?: boolean;
  };
  metrics: {
    total: number;
    dir_count: number;
    file_count: number;
    total_size: number;
  };
  summary?: string;
  success: boolean;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const formatMtime = (mtime?: number | string): string => {
  if (mtime === undefined || mtime === null) return "";
  const d = typeof mtime === "number" ? new Date(mtime * 1000) : new Date(mtime);
  if (isNaN(d.getTime())) return String(mtime);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const containerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
});

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const infoItemStyle: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const labelStyle: React.CSSProperties = { minWidth: 72, color: "#8c8c8c", marginRight: 8 };

const ListDirectoryView: React.FC<ListDirectoryViewProps> = ({ data, metrics, summary, success }) => {
  const entries = data.entries || [];
  const { total, dir_count, file_count, total_size } = metrics;

  if (entries.length === 0) {
    return (
      <div style={containerStyle(success)}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          列出目录{success ? "成功" : "失败"}
        </div>
        <div style={{ color: "#888", fontStyle: "italic" }}>
          <InboxOutlined style={{ marginRight: 6 }} />
          目录为空
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        列出目录{success ? "成功" : "失败"}
      </div>

      {/* 目录项列表 */}
      <div style={{ maxHeight: 360, overflow: "auto", background: "#fafafa", borderRadius: 6, padding: "6px 10px" }}>
        {entries.map((entry, idx) => {
          const isDir = entry.type === "directory";
          const name = entry.name || (isDir ? "(目录)" : "(文件)");
          return (
            <div
              key={`${name}-${idx}`}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "3px 0",
                borderBottom: idx < entries.length - 1 ? "1px solid #f0f0f0" : "none",
                fontSize: 13,
              }}
            >
              {isDir ? (
                <FolderOutlined style={{ color: "#faad14", marginRight: 8 }} />
              ) : (
                <FileOutlined style={{ color: "#1890ff", marginRight: 8 }} />
              )}
              <span style={{ flex: 1, color: "#333", wordBreak: "break-all" }}>{name}</span>
              {entry.size !== undefined && entry.size !== null && (
                <span style={{ color: "#8c8c8c", fontSize: 12, marginRight: 12 }}>{formatFileSize(entry.size)}</span>
              )}
              {entry.mtime !== undefined && entry.mtime !== null && (
                <span style={{ color: "#bfbfbf", fontSize: 12 }}>
                  <InboxOutlined style={{ marginRight: 4, color: "#d9d9d9" }} />
                  {formatMtime(entry.mtime)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* 统计 */}
      <div style={{ ...infoItemStyle, marginTop: 12 }}>
        <span style={labelStyle}>统计：</span>
        <span>
          共 {total} 项（目录 {dir_count} / 文件 {file_count}），总大小 {formatFileSize(total_size)}
        </span>
      </div>

      {data.truncated && (
        <div style={{ color: "#faad14", fontSize: 12, marginTop: 4 }}>结果已截断，仅显示部分</div>
      )}

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(ListDirectoryView);
