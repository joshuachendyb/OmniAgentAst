// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * WriteFileView - writetext 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   仅展示 data.content_preview（写入预览）+ metrics.bytes_written + summary；
 *   不读不存在的 file_path/ message 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface WriteFileViewProps {
  data: {
    content_preview: string;
  };
  metrics: {
    bytes_written: number;
  };
  summary?: string;
  success: boolean;
}

const formatBytes = (bytes: number): string => {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const writeContainerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter });

const writeTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const previewBackground: React.CSSProperties = {
  background: "#1e1e1e",
  border: "1px solid #303030",
  borderRadius: 8,
  padding: "10px 14px",
  marginTop: 6,
  fontSize: "0.9em",
  lineHeight: 1.6,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
  maxHeight: 300,
  overflow: "auto",
  color: "#d4d4d4",
  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
};

const WriteFileView: React.FC<WriteFileViewProps> = ({ data, metrics, summary, success }) => {
  const { content_preview } = data;
  const { bytes_written } = metrics;

  return (
    <div style={writeContainerStyle(success)}>
      {/* 标题 */}
      <div style={writeTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        写入文件{success ? "成功" : "失败"}
      </div>

      {/* 写入内容预览 */}
      {content_preview && <pre style={previewBackground}>{content_preview}</pre>}

      {/* 字节数 */}
      {bytes_written > 0 && (
        <div style={{ marginTop: 8, fontSize: 13, color: "#595959" }}>
          <span style={{ color: "#8c8c8c", marginRight: 8 }}>写入字节：</span>
          <span style={{ fontWeight: 500 }}>{formatBytes(bytes_written)}</span>
        </div>
      )}

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(WriteFileView);
