/**
 * CopyFileView - copy_file 工具结果渲染组件
 *
 * 显示文件复制结果，包括源路径、目标路径、复制状态
 *
 * @author 小强
 * @version 1.0.2
 * @since 2026-04-25
 */

import React from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FileOutlined, CopyOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";

interface CopyFileViewProps {
  data: {
    source_path?: string;
    destination_path?: string;
    success?: boolean;
    file_size?: number;
    elapsed_time?: number;
    error_message?: string;
  };
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const INFO_ITEM_STYLE: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const LABEL_STYLE: React.CSSProperties = { minWidth: 80, color: "#8c8c8c", marginRight: 8 };

const CopyFileView: React.FC<CopyFileViewProps> = ({ data }) => {
  const {
    source_path = "",
    destination_path = "",
    success = true,
    file_size,
    elapsed_time,
    error_message
  } = data || {};

  const isEmpty = !data || (!source_path && !destination_path);
  const processedFileSize = file_size !== undefined ? formatFileSize(file_size) : null;

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

  // 空数据返回 - 条件渲染
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        复制操作数据为空
      </div>
    );
  }

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path);
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

      {/* 源文件路径 */}
      <div style={INFO_ITEM_STYLE}>
        <span style={LABEL_STYLE}>源文件：</span>
        <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
          <FileOutlined style={{ marginRight: 6, color: "#1890ff" }} />
          <span style={{ flex: 1, fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
            {source_path}
          </span>
          <Tooltip title="复制路径">
            <Button
              type="text"
              size="small"
              onClick={() => handleCopyPath(source_path)}
              icon={<CopyOutlined />}
              style={{ padding: "0 4px", minWidth: "auto" }}
            />
          </Tooltip>
        </div>
      </div>

      {/* 目标文件路径 */}
      <div style={INFO_ITEM_STYLE}>
        <span style={LABEL_STYLE}>目标文件：</span>
        <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
          <FileOutlined style={{ marginRight: 6, color: "#52c41a" }} />
          <span style={{ flex: 1, fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 12 }}>
            {destination_path}
          </span>
          <Tooltip title="复制路径">
            <Button
              type="text"
              size="small"
              onClick={() => handleCopyPath(destination_path)}
              icon={<CopyOutlined />}
              style={{ padding: "0 4px", minWidth: "auto" }}
            />
          </Tooltip>
        </div>
      </div>

      {/* 文件大小 */}
      {processedFileSize && (
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>文件大小：</span>
          <span>{processedFileSize}</span>
        </div>
      )}

      {/* 复制耗时 */}
      {elapsed_time !== undefined && (
        <div style={INFO_ITEM_STYLE}>
          <span style={LABEL_STYLE}>复制耗时：</span>
          <span>{elapsed_time.toFixed(2)}秒</span>
        </div>
      )}

      {/* 错误信息 */}
      {!success && error_message && (
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

export default React.memo(CopyFileView);