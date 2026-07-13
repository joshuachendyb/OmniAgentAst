/**
 * GetDirectoryTreeView - tree 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data.tree: 递归目录结构 {name,path,type,children:[]}（仅 directory 有 children）；
 *   data.statistics: {file_count,dir_count,total_size}。
 *   渲染可折叠目录树 + 统计；不读不存在的 root/ success/ error 字段。
 *
 * @author 小健
 * @version 2.0.0
 * @since 2026-05-11
 */

import React, { useState } from "react";
import { CheckCircleOutlined, CloseCircleOutlined, FileOutlined, FolderOutlined, DownOutlined, RightOutlined } from "@ant-design/icons";

interface TreeNode {
  name?: string;
  path?: string;
  type?: "file" | "directory";
  children?: TreeNode[];
}

interface TreeStatistics {
  file_count: number;
  dir_count: number;
  total_size: number;
}

interface GetDirectoryTreeViewProps {
  data: {
    tree: TreeNode | null;
    statistics: TreeStatistics;
  };
  summary?: string;
  success: boolean;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === null || bytes === undefined || bytes === 0) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
};

const containerStyle = (success: boolean): React.CSSProperties => ({
  background: success ? "#f6ffed" : "#fff2f0",
  border: success ? "1px solid #b7eb8f" : "1px solid #ffa39e",
  borderRadius: 8,
  padding: "12px 16px",
  marginTop: 6,
});

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const TreeNodeItem: React.FC<{ node: TreeNode; depth: number }> = ({ node, depth }) => {
  const isDirectory = node.type === "directory";
  const hasChildren = isDirectory && node.children && node.children.length > 0;
  const [expanded, setExpanded] = useState(depth < 2);

  return (
    <div style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 13 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "1px 0",
          cursor: hasChildren ? "pointer" : "default",
          borderRadius: 2,
        }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        <span style={{ width: depth * 16, display: "inline-block" }} />
        {hasChildren ? (
          <span style={{ marginRight: 4, fontSize: 10, color: "#8c8c8c" }}>
            {expanded ? <DownOutlined /> : <RightOutlined />}
          </span>
        ) : (
          <span style={{ marginRight: 4, width: 10, display: "inline-block" }} />
        )}
        {isDirectory ? (
          <FolderOutlined style={{ marginRight: 6, fontSize: 14, color: "#faad14" }} />
        ) : (
          <FileOutlined style={{ marginRight: 6, fontSize: 14, color: "#1890ff" }} />
        )}
        <span style={{ color: isDirectory ? "#333" : "#595959", fontWeight: isDirectory ? 500 : 400 }}>
          {node.name || "(未命名)"}
        </span>
      </div>

      {expanded && hasChildren && (
        <div>
          {(node.children as TreeNode[]).map((child, idx) => (
            <TreeNodeItem key={`${child.path || child.name}-${depth}-${idx}`} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

const GetDirectoryTreeView: React.FC<GetDirectoryTreeViewProps> = ({ data, summary, success }) => {
  const { tree, statistics } = data;

  if (!tree) {
    return (
      <div style={containerStyle(success)}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          获取目录树{success ? "成功" : "失败"}
        </div>
        <div style={{ color: "#888", fontStyle: "italic" }}>目录树为空</div>
      </div>
    );
  }

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <FolderOutlined style={{ marginRight: 6, color: "#faad14" }} />
        目录树结构
      </div>

      {/* 树内容 */}
      <div style={{ maxHeight: 400, overflow: "auto", background: "#fafafa", borderRadius: 6, padding: "8px 12px" }}>
        <TreeNodeItem node={tree} depth={0} />
      </div>

      {/* 统计 */}
      <div style={{ marginTop: 8, fontSize: 12, color: "#595959" }}>
        文件 {statistics.file_count} / 目录 {statistics.dir_count}，总大小 {formatFileSize(statistics.total_size)}
      </div>

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(GetDirectoryTreeView);
