/**
 * CopyFileView - copy 工具结果渲染组件
 *
 * 展示文件复制结果：源大小、目标大小、复制状态与摘要。
 * 【北京老陈 2026-07-13 小欧】后端 Phase1 v6.0 后 copy 工具 data 仅含 source_size/mtime，
 * 目标大小在 llm_data.metrics.bytes，摘要在 llm_data.summary；旧 source_path/file_size 字段已不存在。
 *
 * @author 小强
 * @version 1.0.3
 * @since 2026-04-25
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";

interface CopyFileViewProps {
  data: {
    source_size?: number | null;
    mtime?: number | null;
    dest_size?: number | null;
    summary?: string;
  };
  success: boolean;
}

const formatFileSize = (bytes: number | null | undefined): string | null => {
  if (bytes === null || bytes === undefined) return null;
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const INFO_ITEM_STYLE: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const LABEL_STYLE: React.CSSProperties = { minWidth: 80, color: "#8c8c8c", marginRight: 8 };

const CopyFileView: React.FC<CopyFileViewProps> = ({ data, success }) => {
  const {
    source_size,
    dest_size,
    summary,
  } = data || {};

  const processedSourceSize = formatFileSize(source_size);
  const processedDestSize = formatFileSize(dest_size);

  const containerStyle: React.CSSProperties = {
    background: success ? "#f6ffed" : "#fff2f0",
    border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  };

  const titleStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: success ? "#52c41a" : "#ff4d4f",
  };

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {success ? (
          <>
            <CheckCircleOutlined style={{ marginRight: 8 }} />
            文件复制成功
          </>
        ) : (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            文件复制失败
          </>
        )}
      </div>

      {/* 源文件大小 */}
      {processedSourceSize && (
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>源文件大小：</span>
          <span>{processedSourceSize}</span>
        </div>
      )}

      {/* 目标文件大小 */}
      {processedDestSize && (
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>目标文件大小：</span>
          <span>{processedDestSize}</span>
        </div>
      )}

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>
          {summary}
        </div>
      )}
    </div>
  );
};

export default React.memo(CopyFileView);
