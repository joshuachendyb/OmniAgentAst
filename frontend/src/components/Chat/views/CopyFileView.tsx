/**
 * CopyFileView - copy_file 工具结果渲染组件
 *
 * 显示文件复制结果，包括源路径、目标路径、复制状态
 *
 * @author 小强
 * @version 1.0.2
 * @since 2026-04-25
 */

import React, { useMemo } from "react";
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

/**
 * 格式化文件大小
 */
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

/**
 * CopyFileView 主组件
 */
const CopyFileView: React.FC<CopyFileViewProps> = ({ data }) => {
  // 数据提取（包含默认值）
  const {
    source_path = "",
    destination_path = "",
    success = true,
    file_size,
    elapsed_time,
    error_message
  } = data || {};

  // 空数据检查 - 在useMemo之前
  const isEmpty = useMemo(() => {
    return !data || (!source_path && !destination_path);
  }, [data, source_path, destination_path]);

  // 处理文件大小
  const processedFileSize = useMemo(() => {
    return file_size !== undefined ? formatFileSize(file_size) : null;
  }, [file_size]);

  // 容器样式 - 使用useMemo缓存
  const containerStyle = useMemo(() => ({
    background: success
      ? "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)",
    border: success
      ? "1px solid #b7eb8f"
      : "1px solid #ffa39e",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [success]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: success ? "#52c41a" : "#ff4d4f",
  }), [success]);

  // 信息项样式
  const infoItemStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 8,
    fontSize: 13,
    color: "#595959",
  }), []);

  // 标签样式
  const labelStyle = useMemo(() => ({
    minWidth: 80,
    color: "#8c8c8c",
    marginRight: 8,
  }), []);

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
      <div style={infoItemStyle}>
        <span style={labelStyle}>源文件：</span>
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
      <div style={infoItemStyle}>
        <span style={labelStyle}>目标文件：</span>
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
        <div style={infoItemStyle}>
          <span style={labelStyle}>文件大小：</span>
          <span>{processedFileSize}</span>
        </div>
      )}

      {/* 复制耗时 */}
      {elapsed_time !== undefined && (
        <div style={infoItemStyle}>
          <span style={labelStyle}>复制耗时：</span>
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