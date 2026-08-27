// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * CompressFilesView - compress 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   展示 data: 压缩级别/是否加密/原始大小/压缩率 + metrics: 文件数/压缩后大小/格式 + summary。
 *   不读不存在的 archive_path/ archive_name/ file_list/ error_message 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-25
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CheckCircleOutlined, CloseCircleOutlined, InboxOutlined, LockOutlined } from "@ant-design/icons";

interface CompressFilesViewProps {
  data: {
    compression_level: number;
    encrypted: boolean;
    original_size: number;
    compression_ratio: number;
  };
  metrics: {
    file_count: number;
    compressed_size: number;
    ratio: number;
    format: string;
  };
  summary?: string;
  success: boolean;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === null || bytes === undefined || bytes === 0) return "-";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const containerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter });

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const infoItemStyle: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const labelStyle: React.CSSProperties = { minWidth: 84, color: "#8c8c8c", marginRight: 8 };

const CompressFilesView: React.FC<CompressFilesViewProps> = ({ data, metrics, summary, success }) => {
  const { compression_level, encrypted, original_size, compression_ratio } = data;
  const { file_count, compressed_size, ratio, format } = metrics;

  const ratioColor = ratio >= 70 ? "#52c41a" : ratio >= 30 ? "#faad14" : "#1677ff";

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        文件压缩{success ? "成功" : "失败"}
      </div>

      {/* 压缩级别 / 加密 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>压缩级别：</span>
        <span>{compression_level || "-"}</span>
        {encrypted && (
          <span style={{ marginLeft: 12, color: "#fa8c16" }}>
            <LockOutlined style={{ marginRight: 4 }} />已加密
          </span>
        )}
      </div>

      {/* 原始大小 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>原始大小：</span>
        <span>{formatFileSize(original_size)}</span>
      </div>

      {/* 压缩后大小 / 格式 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>压缩后：</span>
        <span style={{ color: "#52c41a", fontWeight: 500 }}>{formatFileSize(compressed_size)}</span>
        {format && <span style={{ marginLeft: 12, color: "#8c8c8c" }}>格式：{format}</span>}
      </div>

      {/* 压缩率 */}
      <div style={infoItemStyle}>
        <span style={labelStyle}>压缩率：</span>
        <span style={{ color: ratioColor, fontWeight: 600 }}>
          {compression_ratio > 0 ? `${(compression_ratio * 100).toFixed(1)}%` : ratio > 0 ? `${(ratio * 100).toFixed(1)}%` : "-"}
        </span>
      </div>

      {/* 文件数 */}
      {file_count > 0 && (
        <div style={infoItemStyle}>
          <InboxOutlined style={{ marginRight: 6, color: "#1677ff" }} />
          <span style={labelStyle}>包含文件：</span>
          <span>{file_count} 个</span>
        </div>
      )}

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(CompressFilesView);
