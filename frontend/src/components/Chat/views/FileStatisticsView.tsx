/**
 * FileStatisticsView - file_statistics 工具结果渲染组件
 *
 * 显示文件统计信息
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-26
 */

import React, { useMemo } from "react";
import { BarChartOutlined, FolderOutlined, FileOutlined, DatabaseOutlined } from "@ant-design/icons";
import { Card, Statistic } from "antd";

interface FileStatisticsViewProps {
  data: {
    directory?: string;
    total_files?: number;
    total_directories?: number;
    total_size?: number;
    file_types?: Record<string, number>;
  };
}

/**
 * FileStatisticsView 主组件
 */
const FileStatisticsView: React.FC<FileStatisticsViewProps> = ({ data }) => {
  const {
    directory = "",
    total_files = 0,
    total_directories = 0,
    total_size = 0,
    file_types = {},
  } = data || {};

  // 空数据检查
  const isEmpty = useMemo(() => {
    return !data || (!total_files && !total_directories);
  }, [data, total_files, total_directories]);

  // 格式化大小
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  };

  // 容器样式
  const containerStyle = useMemo(() => ({
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
    borderRadius: 8,
    padding: "12px 16px",
    marginTop: 6,
  }), []);

  // 标题样式
  const titleStyle = useMemo(() => ({
    display: "flex",
    alignItems: "center",
    marginBottom: 12,
    fontSize: 14,
    fontWeight: 500,
    color: "#52c41a",
  }), []);

  // 统计卡片行样式
  const statsRowStyle = useMemo(() => ({
    display: "flex",
    gap: 12,
    marginBottom: 16,
  }), []);

  // 空数据返回
  if (isEmpty) {
    return (
      <div style={{ color: "#888", fontStyle: "italic", padding: "12px 16px" }}>
        ⚠️ 统计数据为空
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* 标题 */}
      <div style={titleStyle}>
        <BarChartOutlined style={{ marginRight: 8 }} />
        📊 文件统计
      </div>

      {/* 监控目录 */}
      <div style={{ marginBottom: 16, fontSize: 12, color: "#8c8c8c" }}>
        📁 {directory}
      </div>

      {/* 统计卡片 */}
      <div style={statsRowStyle}>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="文件数"
            value={total_files}
            prefix={<FileOutlined />}
            valueStyle={{ color: "#1890ff" }}
          />
        </Card>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="目录数"
            value={total_directories}
            prefix={<FolderOutlined />}
            valueStyle={{ color: "#52c41a" }}
          />
        </Card>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="总大小"
            value={formatSize(total_size)}
            prefix={<DatabaseOutlined />}
            valueStyle={{ color: "#722ed1" }}
          />
        </Card>
      </div>

      {/* 文件类型分布 */}
      {file_types && Object.keys(file_types).length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 8 }}>文件类型分布：</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Object.entries(file_types).map(([ext, count]) => (
              <div
                key={ext}
                style={{
                  padding: "4px 8px",
                  background: "#f5f5f5",
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                {ext}: {count}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default React.memo(FileStatisticsView);