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

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

/**
 * GetFileInfoView 主组件
 */
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

  // 错误状态
  const hasError = error_message !== undefined && error_message !== "";

  // 容器样式 - 与系统设计风格一致
  const containerStyle = {
    background: hasError 
      ? "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%)",
    border: hasError 
      ? "1px solid #ffa39e"
      : "1px solid #d9d9d9",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  };

  // 标题样式
  const titleStyle = {
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: hasError ? "#ff4d4f" : "#262626",
  };

  // 信息网格样式
  const infoGridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "8px 16px",
    fontSize: 13,
  };

  // 每一项样式
  const infoItemStyle = {
    display: "flex",
    alignItems: "center",
  };

  // 标签样式
  const labelStyle = {
    minWidth: 70,
    color: "#8c8c8c",
    marginRight: 8,
    display: "flex",
    alignItems: "center",
  };

  // 处理文件大小
  const processedSize = size !== undefined ? formatFileSize(size) : null;

  // 根据文件类型选择图标
  const FileIcon = is_directory ? FolderOutlined : FileOutlined;
  const iconColor = is_directory ? "#fa8c16" : "#1890ff";

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <FileIcon style={{ marginRight: 8, color: iconColor }} />
        📄 文件信息
      </div>

      {/* 信息网格 */}
      <div style={infoGridStyle}>
        {/* 名称 */}
        <div style={infoItemStyle}>
          <span style={labelStyle}>📝 名称：</span>
          <span style={{ fontWeight: 500, color: "#262626" }}>{name}</span>
        </div>

        {/* 类型 */}
        <div style={infoItemStyle}>
          <span style={labelStyle}>📝 类型：</span>
          <span style={{ color: "#595959" }}>
            {type || (is_directory ? "目录" : "文件")}
            {type && !is_directory && <span style={{ color: "#8c8c8c" }}> (.{type})</span>}
          </span>
        </div>

        {/* 路径 */}
        <div style={{ ...infoItemStyle, gridColumn: "1 / -1" }}>
          <span style={{ ...labelStyle, minWidth: 70 }}>📂 路径：</span>
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
          <div style={infoItemStyle}>
            <span style={labelStyle}>📊 大小：</span>
            <span style={{ fontWeight: 500 }}>{processedSize}</span>
          </div>
        )}

        {/* 权限 */}
        <div style={infoItemStyle}>
          <span style={labelStyle}><LockOutlined /> 权限：</span>
          <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>{permissions}</span>
        </div>

        {/* 创建时间 */}
        {created_at && (
          <div style={infoItemStyle}>
            <span style={labelStyle}><ClockCircleOutlined /> 创建：</span>
            <span>{created_at}</span>
          </div>
        )}

        {/* 修改时间 */}
        {modified_at && (
          <div style={infoItemStyle}>
            <span style={labelStyle}><ClockCircleOutlined /> 修改：</span>
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