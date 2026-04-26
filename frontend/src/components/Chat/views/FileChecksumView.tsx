/**
 * FileChecksumView - file_checksum 工具结果渲染组件
 *
 * 显示文件校验和信息
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { SafetyOutlined, CopyOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";

interface ChecksumItem {
  algorithm?: string;
  value?: string;
}

interface FileChecksumViewProps {
  data: {
    file_path?: string;
    file_size?: number;
    checksums?: ChecksumItem[];
    success?: boolean;
  };
}

/**
 * FileChecksumView 主组件
 */
const FileChecksumView: React.FC<FileChecksumViewProps> = ({ data }) => {
  const {
    file_path = "",
    file_size = 0,
    checksums = [],
    success = true,
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!file_path && checksums.length === 0);
  }, [data, file_path, checksums.length]);

  // 格式化大小
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  };

  // 复制到剪贴板
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: success
      ? "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)"
      : "linear-gradient(135deg, #fff2f0 0%, #f5f5f5 100%)",
    border: `1px solid ${success ? "#b7eb8f" : "#ffa39e"}`,
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

  // 校验和信息行样式
  const checksumRowStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 8,
    padding: "8px",
    background: "#f5f5f5",
    borderRadius: 4,
  }), []);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 校验和数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <SafetyOutlined style={{ marginRight: 8 }} />
        🔐 文件校验
      </div>

      {/* 文件路径 */}
      <div style={{ marginBottom: 8, fontSize: 12, color: "#8c8c8c", wordBreak: "break-all" }}>
        📄 {file_path}
      </div>

      {/* 文件大小 */}
      <div style={{ marginBottom: 16 }}>
        <span style={{ color: "#8c8c8c" }}>📊 大小：</span>
        {formatSize(file_size)}
      </div>

      {/* 校验和列表 */}
      {checksums && checksums.length > 0 && (
        <div>
          {checksums.map((item, index) => (
            <div key={index} style={checksumRowStyle}>
              <div style={{ minWidth: 70, fontWeight: 500, color: "#1890ff" }}>
                {item.algorithm}
              </div>
              <div style={{ flex: 1, fontFamily: "Consolas, Monaco, 'Courier New', monospace", fontSize: 11, wordBreak: "break-all" }}>
                {item.value}
              </div>
              <Tooltip title="复制">
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(item.value || "")}
                  style={{ marginLeft: 8 }}
                />
              </Tooltip>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default React.memo(FileChecksumView);