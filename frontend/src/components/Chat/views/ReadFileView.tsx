/**
 * ReadFileView - readtext 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   仅展示 data.content（<pre> 保留格式）+ metrics 行数信息 + summary；
 *   不读不存在的 file_path/ total_lines 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FileTextOutlined, BarChartOutlined } from "@ant-design/icons";

interface ReadFileViewProps {
  data: {
    content: string;
    truncated_lines?: number;
  };
  metrics: {
    lines: number;
    total_lines: number;
    bytes: number;
  };
  summary?: string;
  success: boolean;
}

const readContainerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
});

const readTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const contentBackground: React.CSSProperties = {
  background: "#1e1e1e",
  border: "1px solid #303030",
  borderRadius: 8,
  padding: "10px 14px",
  marginTop: 6,
  fontSize: "0.9em",
  lineHeight: 1.6,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: 400,
  overflow: "auto",
  color: "#d4d4d4",
  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
};

const ReadFileView: React.FC<ReadFileViewProps> = ({ data, metrics, summary, success }) => {
  const { content, truncated_lines } = data;
  const { lines, total_lines, bytes } = metrics;

  if (!content) {
    return (
      <div style={readContainerStyle(success)}>
        <div style={readTitleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          读取文件{success ? "成功" : "失败"}
        </div>
        <div style={{ color: "#888", fontStyle: "italic" }}>
          <FileTextOutlined style={{ marginRight: 8 }} />
          文件内容为空
        </div>
      </div>
    );
  }

  return (
    <div style={readContainerStyle(success)}>
      {/* 标题 */}
      <div style={readTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        读取文件{success ? "成功" : "失败"}
      </div>

      {/* 文件内容 */}
      <pre style={contentBackground}>{content}</pre>

      {/* 行数信息 */}
      <div style={{ marginTop: 8, fontSize: 12, color: "#666", display: "flex", gap: 12, flexWrap: "wrap" }}>
        {lines > 0 && (
          <span style={{ background: "#e6f7ff", padding: "2px 8px", borderRadius: 4, color: "#1890ff", fontWeight: 500 }}>
            <BarChartOutlined style={{ marginRight: 4 }} /> 本次 {lines} 行 / 共 {total_lines} 行
          </span>
        )}
        {bytes > 0 && <span style={{ color: "#8c8c8c" }}>{bytes} 字节</span>}
        {truncated_lines !== undefined && truncated_lines > 0 && (
          <span style={{ color: "#faad14" }}>已截断 {truncated_lines} 行</span>
        )}
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(ReadFileView);
