/**
 * GetDirectoryTreeRenderer - 目录树渲染组件
 * 
 * @author 小健
 * @version 1.1.0
 * @since 2026-05-11
 */

import React, { useState } from "react";
import { FileOutlined, FolderOutlined, DownOutlined, RightOutlined } from "@ant-design/icons";
import { BaseRendererProps } from "./BaseRendererProps";

interface TreeNode {
  name: string;
  type: "file" | "directory";
  children?: TreeNode[];
}

interface Props extends BaseRendererProps {}

/**
 * 层级颜色映射
 */
const getLevelColor = (depth: number): string => {
  const colors = [
    "#1890ff", // 0级 - 蓝色
    "#52c41a", // 1级 - 绿色
    "#faad14", // 2级 - 橙色
    "#722ed1", // 3级 - 紫色
    "#eb2f96", // 4级 - 粉色
    "#13c2c2", // 5级 - 青色
  ];
  return colors[depth % colors.length];
};

/**
 * 目录树节点渲染组件
 */
const TreeNodeItem: React.FC<{
  node: TreeNode;
  depth: number;
  defaultExpandDepth: number;
  isLast: boolean;
  parentPrefix: string;
}> = ({ node, depth, defaultExpandDepth, isLast, parentPrefix }) => {
  const [expanded, setExpanded] = useState(depth < defaultExpandDepth);
  const isDirectory = node.type === "directory";
  const hasChildren = isDirectory && node.children && node.children.length > 0;
  
  // 树形前缀符号
  const currentPrefix = isLast ? "└─ " : "├─ ";
  const childPrefix = isLast ? "    " : "│   ";
  const fullPrefix = depth === 0 ? "" : parentPrefix + currentPrefix;

  const handleClick = () => {
    if (hasChildren) {
      setExpanded(!expanded);
    }
  };

  const levelColor = getLevelColor(depth);

  return (
    <div style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 13 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "1px 0",
          cursor: hasChildren ? "pointer" : "default",
          borderRadius: 2,
          transition: "background 0.15s",
        }}
        onClick={handleClick}
        onMouseEnter={(e) => {
          if (hasChildren) {
            e.currentTarget.style.background = "rgba(0,0,0,0.03)";
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
        }}
      >
        {/* 树形结构前缀 */}
        <span style={{ 
          color: "#bfbfbf", 
          whiteSpace: "pre",
          userSelect: "none",
        }}>
          {fullPrefix}
        </span>

        {/* 展开/折叠箭头 */}
        {hasChildren ? (
          <span style={{ 
            marginRight: 4, 
            fontSize: 10, 
            color: levelColor,
            transition: "transform 0.2s",
          }}>
            {expanded ? <DownOutlined /> : <RightOutlined />}
          </span>
        ) : (
          <span style={{ marginRight: 4, width: 10, display: "inline-block" }} />
        )}

        {/* 图标 */}
        {isDirectory ? (
          <FolderOutlined style={{ marginRight: 6, fontSize: 14, color: "#faad14" }} />
        ) : (
          <FileOutlined style={{ marginRight: 6, fontSize: 14, color: "#1890ff" }} />
        )}

        {/* 名称 */}
        <span style={{ 
          color: isDirectory ? "#333" : "#595959",
          fontWeight: isDirectory ? 500 : 400,
        }}>
          {node.name}
        </span>

        {/* 层级标签 */}
        <span style={{
          marginLeft: 8,
          fontSize: 10,
          color: levelColor,
          background: `${levelColor}15`,
          padding: "0 4px",
          borderRadius: 2,
          fontWeight: 500,
        }}>
          L{depth}
        </span>
      </div>

      {/* 子节点 */}
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child, index) => (
            <TreeNodeItem
              key={`${child.name}-${depth}-${index}`}
              node={child}
              depth={depth + 1}
              defaultExpandDepth={defaultExpandDepth}
              isLast={index === node.children!.length - 1}
              parentPrefix={depth === 0 ? "" : parentPrefix + childPrefix}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * GetDirectoryTreeRenderer组件
 * 
 * 【重要】execution_result结构说明：
 * 后端在StepFactory.create_action_tool_step中只传execution_result.get("data")
 * 所以收到的数据结构是：{ success: true, tree: {...}, root: "..." }
 * 而不是：{ status: "success", data: {...} }
 */
const GetDirectoryTreeRenderer: React.FC<Props> = ({ step }) => {
  // execution_result 就是 data 部分
  const data = step.execution_result as Record<string, unknown>;
  const tree = data?.tree as TreeNode | undefined;
  const root = (data?.root || "") as string;
  const success = data?.success === true;

  if (!success) {
    const errorMsg = (data?.error || "获取目录树失败") as string;
    return (
      <div style={{ padding: 12, background: "#fff2f0", borderRadius: 8, border: "1px solid #ffa39e" }}>
        <span style={{ color: "#ff4d4f" }}>❌ {errorMsg}</span>
      </div>
    );
  }

  if (!tree) {
    return (
      <div style={{ padding: 12, background: "#fafafa", borderRadius: 8 }}>
        <span style={{ color: "#999" }}>目录树为空</span>
      </div>
    );
  }

  return (
    <div
      style={{
        marginTop: 8,
        background: "#fafafa",
        border: "1px solid #e8e8e8",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {/* 标题 */}
      <div
        style={{
          padding: "8px 12px",
          background: "linear-gradient(135deg, #f0f0f0 0%, #fafafa 100%)",
          borderBottom: "1px solid #e8e8e8",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <FolderOutlined style={{ color: "#faad14", fontSize: 16 }} />
        <span style={{ fontWeight: 600, color: "#333" }}>目录树结构</span>
        {root && (
          <span style={{ fontSize: 11, color: "#8c8c8c", background: "#fff", padding: "2px 6px", borderRadius: 4 }}>
            {root}
          </span>
        )}
      </div>

      {/* 图例 */}
      <div style={{
        padding: "6px 12px",
        background: "#fff",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        alignItems: "center",
        gap: 16,
        fontSize: 11,
        color: "#8c8c8c",
      }}>
        <span><FolderOutlined style={{ color: "#faad14", marginRight: 4 }} />文件夹</span>
        <span><FileOutlined style={{ color: "#1890ff", marginRight: 4 }} />文件</span>
        <span style={{ color: "#bfbfbf" }}>├─ └─ 树形结构</span>
        <span style={{ color: "#1890ff" }}>L0-L5 层级</span>
      </div>

      {/* 树内容 */}
      <div
        style={{
          padding: "8px 12px",
          maxHeight: 400,
          overflow: "auto",
          lineHeight: 1.6,
        }}
      >
        <TreeNodeItem 
          node={tree} 
          depth={0} 
          defaultExpandDepth={2} 
          isLast={true}
          parentPrefix=""
        />
      </div>
    </div>
  );
};

export default React.memo(GetDirectoryTreeRenderer);
