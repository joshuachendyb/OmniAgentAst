/**
 * GetFileInfoView - get_file_info 工具结果渲染组件
 *
 * 显示文件/目录详细信息
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React from "react";
import { FileOutlined, FolderOutlined, ClockCircleOutlined, LockOutlined } from "@ant-design/icons";

interface GetFileInfoViewProps {
  data: {
    name?: string;
    path?: string;
    size?: number;
    created_at?: string;
    modified_at?: string;
    permissions?: string;
    type?: string;
    is_directory?: boolean;
    error_message?: string;
  };
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

const INFO_GRID_STYLE: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px 16px", fontSize: 13 };
const INFO_ITEM_STYLE: React.CSSProperties = { display: "flex", alignItems: "center" };
const LABEL_STYLE: React.CSSProperties = { minWidth: 70, color: "#8c8c8c", marginRight: 8, display: "flex", alignItems: "center" };

const GetFileInfoView: React.FC<GetFileInfoViewProps> = ({ data }) => {
  const { 
    name = "",
    path = "",
    size,
    created_at,
    modified_at,
    permissions = "644",
    type = "",
    is_directory = false,
    error_message 
  } = data;

  const hasError = error_message !== undefined && error_message !== "";

  const containerStyle: React.CSSProperties = {
    background: hasError ? "#fff2f0" : "#fafafa",
    border: hasError ? "1px solid #ffa39e" : "1px solid #d9d9d9",
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
    color: hasError ? "#ff4d4f" : "#262626",
  };

  const processedSize = size !== undefined ? formatFileSize(size) : null;
  const FileIcon = is_directory ? FolderOutlined : FileOutlined;
  const iconColor = is_directory ? "#fa8c16" : "#1890ff";

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <FileIcon style={{ marginRight: 8, color: iconColor }} />
        文件信息
      </div>

      {/* 信息网格 */}
      <div style={INFO_GRID_STYLE}>
        {/* 名称 */}
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>名称：</span>
          <span style={{ fontWeight: 500, color: "#262626" }}>{name}</span>
        </div>

        {/* 类型 */}
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>类型：</span>
          <span style={{ color: "#595959" }}>
            {type || (is_directory ? "目录" : "文件")}
            {type && !is_directory && <span style={{ color: "#8c8c8c" }}> (.{type})</span>}
          </span>
        </div>

        {/* 路径 */}
        <div style={{ ...INFO_ITEM_STYLE, gridColumn: "1 / -1" }}>
          <span style={{ ...LABEL_STYLE, minWidth: 70 }}>路径：</span>
          <span style={{ 
            flex: 1, 
            fontFamily: "Consolas, Monaco, 'Courier New', monospace", 
            fontSize: 12,
            wordBreak: "break-all"
          }}>
            {path}
          </span>
        </div>

        {/* 大小 */}
        {processedSize && (
<div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>大小：</span>
            <span style={{ fontWeight: 500 }}>{processedSize}</span>
          </div>
        )}

        {/* 权限 */}
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}><LockOutlined /> 权限：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>{permissions}</span>
        </div>

        {/* 创建时间 */}
        {created_at && (
          <div style={INFO_ITEM_STYLE}>
            <span style={LABEL_STYLE}><ClockCircleOutlined /> 创建：</span>
            <span>{created_at}</span>
          </div>
        )}

        {/* 修改时间 */}
        {modified_at && (
          <div style={INFO_ITEM_STYLE}>
            <span style={LABEL_STYLE}><ClockCircleOutlined /> 修改：</span>
            <span>{modified_at}</span>
          </div>
        )}
      </div>

      {/* 错误信息 */}
      {hasError && (
        <div style={{
          marginTop: 12,
          padding: "8px 12px",
          background: "#fff2f0",
          border: "1px solid #ffccc7",
          borderRadius: 4,
          color: "#ff4d4f",
          fontSize: 12,
        }}>
          <strong>错误信息：</strong> {error_message}
        </div>
      )}
    </div>
  );
};

export default React.memo(GetFileInfoView);