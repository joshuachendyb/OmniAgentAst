/**
 * CompressFilesView - compress_files 工具结果渲染组件
 *
 * 显示文件压缩结果
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-25
 */

import React, { useMemo } from "react";
import { CloseCircleOutlined, InboxOutlined, DownloadOutlined, RightOutlined } from "@ant-design/icons";
import { Collapse, Button } from "antd";

interface CompressFilesViewProps {
  data: {
    archive_path?: string;
    archive_name?: string;
    original_size?: number;
    compressed_size?: number;
    compression_ratio?: number;
    file_count?: number;
    file_list?: string[];
    success?: boolean;
    error_message?: string;
  };
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 0) bytes = Math.abs(bytes);
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

/**
 * CompressFilesView 主组件
 */
const CompressFilesView: React.FC<CompressFilesViewProps> = ({ data }) => {
  const { 
    archive_path = "",
    archive_name = "",
    original_size,
    compressed_size,
    compression_ratio,
    file_count = 0,
    file_list = [],
    success = true,
    error_message 
  } = data;

  const hasError = !success || (error_message !== undefined && error_message !== "");
  const hasFileList = file_list && file_list.length > 0;

  // 容器样式 - 使用useMemo缓存
  const containerStyle = useMemo(() => ({
    background: hasError 
      ? "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #e6f7ff 0%, #f5f5f5 100%)",
    border: hasError 
      ? "1px solid #ffa39e"
      : "1px solid #91d5ff",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), [hasError]);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: hasError ? "#ff4d4f" : "#1890ff",
  }), [hasError]);

  // 统计卡片样式
  const statsCardStyle = useMemo(() => ({
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 12,
    marginBottom: 12,
    padding: "12px",
    background: "#fafafa",
    borderRadius: 6,
    border: "1px solid #f0f0f0",
  }), []);

  // 统计项样式
  const statItemStyle: React.CSSProperties = useMemo(() => ({
    textAlign: "center",
  }), []);

  // 压缩比样式
  const ratioColor = useMemo(() => compression_ratio !== undefined 
    ? (compression_ratio >= 70 ? "#52c41a" : (compression_ratio >= 30 ? "#faad14" : "#1890ff"))
    : "#595959", [compression_ratio]);

  // 处理原始大小
  const originalFormatted = useMemo(() => original_size !== undefined ? formatFileSize(original_size) : null, [original_size]);
  const compressedFormatted = useMemo(() => compressed_size !== undefined ? formatFileSize(compressed_size) : null, [compressed_size]);
  const compressionRatio = useMemo(() => compression_ratio !== undefined ? compression_ratio.toFixed(1) + "%" : null, [compression_ratio]);

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        {hasError ? (
          <>
            <CloseCircleOutlined style={{ marginRight: 8 }} />
            文件压缩失败
          </>
        ) : (
          <>
            <InboxOutlined style={{ marginRight: 8 }} />
            文件压缩完成
          </>
        )}
      </div>

      {/* 统计卡片 */}
      {!hasError && (
        <>
          <div style={statsCardStyle}>
            {/* 原始大小 */}
            <div style={statItemStyle}>
              <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>
                原始大小
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: "#595959" }}>
                {originalFormatted || "-"}
              </div>
            </div>

            {/* 压缩后大小 */}
            <div style={statItemStyle}>
              <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>
                压缩后
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: "#52c41a" }}>
                {compressedFormatted || "-"}
              </div>
            </div>

            {/* 压缩率 */}
            <div style={statItemStyle}>
              <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 4 }}>
                压缩率
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: ratioColor }}>
                {compressionRatio || "-"}
              </div>
            </div>
          </div>

          {/* 压缩文件信息 */}
          {(archive_path || archive_name) && (
            <div style={{ 
              marginBottom: 12,
              padding: "10px 12px",
              background: "#f6ffed",
              border: "1px solid #b7eb8f",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <div>
                <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 2 }}>
                  压缩文件
                </div>
                <div style={{ fontSize: 13, fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>
                  {archive_name || archive_path}
                </div>
              </div>
              <Button 
                type="primary" 
                size="small" 
                icon={<DownloadOutlined />}
              >
                下载
              </Button>
            </div>
          )}

          {/* 文件列表 */}
          {hasFileList && (
            <Collapse
              ghost
              style={{
                background: "#fafafa",
                border: "1px solid #d9d9d9",
                borderRadius: 6,
              }}
              items={[
                {
                  key: '1',
                  label: (
<span style={{ fontSize: 13, color: "#595959" }}>
                        包含文件（{file_count}个）
                    </span>
                  ),
                  children: (
                    <div style={{ maxHeight: 150, overflowY: "auto" }}>
                      {file_list.map((file, index) => (
                        <div 
                          key={index} 
                          style={{
                            display: "flex",
                            alignItems: "center",
                            padding: "4px 0",
                            fontSize: 12,
                            fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                            color: "#595959",
                            borderBottom: index < file_list.length - 1 ? "1px solid #f5f5f5" : "none",
                          }}
                        >
                          <RightOutlined style={{ marginRight: 8, color: "#8c8c8c", fontSize: 10 }} />
                          {file}
                        </div>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          )}
        </>
      )}

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

export default React.memo(CompressFilesView);