// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * FileStatisticsView - file_statistics 工具结果渲染组件
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-26
 * @update 2026-05-10 小健-重写：去掉Card/Statistic，精简为扁平布局
 */

import React from "react";
import { FolderOutlined, FileOutlined } from "@ant-design/icons";

interface FileStatisticsViewProps {
  data: {
    directory?: string;
    total_files?: number;
    total_directories?: number;
    total_size?: number;
    file_types?: Record<string, number>;
  };
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)}KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)}MB`;
  return `${(bytes / 1073741824).toFixed(1)}GB`;
};

const FileStatisticsView: React.FC<FileStatisticsViewProps> = ({ data }) => {
  const {
    directory = "",
    total_files = 0,
    total_directories = 0,
    total_size = 0,
    file_types,
  } = data || {};

  if (!data) return <div style={{ color: "#999", padding: "8px 12px" }}>统计数据为空</div>;

  const topTypes = file_types ? Object.entries(file_types).sort((a, b) => b[1] - a[1]).slice(0, 5) : [];

  return (
    <div style={{ fontSize: 13, lineHeight: "20px" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 4 }}>
        <FolderOutlined style={{ color: "#1677ff" }} />
        {directory && <span style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 12, color: "#595959" }}>{directory}</span>}
        <span style={{ color: "#1677ff", fontWeight: 500 }}><FileOutlined /> {total_files}个文件</span>
        <span style={{ color: "#595959" }}>{total_directories}个目录</span>
        <span style={{ color: "#8c8c8c" }}>{formatSize(total_size)}</span>
      </div>
      {topTypes.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {topTypes.map(([ext, count]) => (
            <span key={ext} style={{ fontSize: 11, padding: "1px 6px", borderRadius: 3, background: "#f5f5f5", color: "#8c8c8c" }}>
              .{ext}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default React.memo(FileStatisticsView);
