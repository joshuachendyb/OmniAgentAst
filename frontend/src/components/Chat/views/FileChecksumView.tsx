/**
 * FileChecksumView - file_checksum 工具结果渲染组件
 *
 * 显示文件校验和信息
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React from "react";
import { SafetyOutlined, CopyOutlined, WarningOutlined } from "@ant-design/icons";
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

const CHECKSUM_ROW_STYLE: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, padding: 8, background: "#f5f5f5", borderRadius: 4 };

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const FileChecksumView: React.FC<FileChecksumViewProps> = ({ data }) => {
  const {
    file_path = "",
    file_size = 0,
    checksums = [],
    success = true,
  } = data || {};

  const isEmpty = !data || (!file_path && checksums.length === 0);

  const containerStyle: React.CSSProperties = {
    background: success ? "#f6ffed" : "#fff2f0",
    border: `1px solid ${success ? "#b7eb8f" : "#ffa39e"}`,
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

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        <WarningOutlined style={{ marginRight: 6 }} />
        校验和数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>
        <SafetyOutlined style={{ marginRight: 8 }} />
        文件校验
      </div>

      <div style={{ marginBottom: 8, fontSize: 12, color: "#8c8c8c", wordBreak: "break-all" }}>
        {file_path}
      </div>

      <div style={{ marginBottom: 16 }}>
        <span style={{ color: "#8c8c8c" }}>大小：</span>
        {formatSize(file_size)}
      </div>

      {checksums && checksums.length > 0 && (
        <div>
          {checksums.map((item, index) => (
            <div key={index} style={CHECKSUM_ROW_STYLE}>
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