/**
 * ListDirectoryView - list_directory 工具结果渲染组件
 *
 * 根据 recursive 参数选择不同的显示方案：
 * - 非递归模式（recursive=false）：虚拟列表
 * - 递归模式（recursive=true）：树形结构
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-24
 */

import React, { useState, useMemo } from "react";
import { List, Tree, Input } from "antd";
import {
  FolderOutlined,
  FileOutlined,
  SearchOutlined,
} from "@ant-design/icons";

const { DirectoryTree } = Tree;

interface TreeNode {
  key: string;
  title: string;
  type: "directory" | "file";
  children?: TreeNode[];
  path: string;
  size: number | null;
}

interface Entry {
  name: string;
  path: string;
  type: "directory" | "file";
  size: number | null;
}

interface ListDirectoryViewProps {
  data: {
    entries: Entry[];
    total?: number;
    has_more?: boolean;
    directory?: string;
  };
  toolParams?: {
    recursive?: boolean;
    path?: string;
  };
  isExpanded?: boolean;
  onToggle?: () => void;  // 【小强添加 2026-03-24】折叠切换回调
}

/**
 * 将扁平的 entries 数组转换为树形结构（供 Tree 组件使用）
 */
function convertEntriesToTree(entries: Entry[], rootPath: string): TreeNode[] {
  if (!entries || entries.length === 0) {
    return [];
  }

  // 标准化 rootPath，移除末尾斜杠，统一使用正斜杠
  const normalizedRoot = rootPath.replace(/\\/g, "/").replace(/\/$/, "");

  // 【小沈修复 2026-03-30】完全重写树构建逻辑
  // 问题：路径标准化不一致导致重复节点
  // 解决：统一使用标准化路径，确保所有节点key唯一

  // 第一步：标准化所有条目路径，并过滤相对路径
  const normalizedEntries: Entry[] = [];
  const relativeEntries: Entry[] = [];
  
  for (const entry of entries) {
    // 标准化路径：统一使用正斜杠
    const normalizedPath = entry.path.replace(/\\/g, "/");
    
    // 检查是否为绝对路径（以rootPath开头）
    if (normalizedPath.startsWith(normalizedRoot + "/")) {
      // 绝对路径条目：使用标准化路径
      normalizedEntries.push({
        ...entry,
        path: normalizedPath
      });
    } else if (normalizedPath === normalizedRoot) {
      // rootPath本身
      normalizedEntries.push({
        ...entry,
        path: normalizedPath
      });
    } else {
      // 相对路径条目
      relativeEntries.push({
        ...entry,
        path: normalizedPath
      });
    }
  }
  
  // 第二步：为没有对应绝对路径的相对路径条目创建虚拟条目
  const missingFromAbsolute = relativeEntries.filter(rel => {
    const relName = rel.name;
    return !normalizedEntries.some(abs => {
      // 检查是否有同名的第一级目录
      const pathAfterRoot = abs.path.substring(normalizedRoot.length + 1);
      if (!pathAfterRoot) return false;
      const firstPart = pathAfterRoot.split("/")[0];
      return firstPart === relName;
    });
  });
  
  // 创建虚拟条目
  const virtualEntries = missingFromAbsolute.map(rel => ({
    name: rel.name,
    path: normalizedRoot + "/" + rel.name,
    type: rel.type,
    size: rel.size
  }));
  
  // 合并所有条目
  const allEntries = [...normalizedEntries, ...virtualEntries];
  
  // 第三步：去重 - 按标准化路径去重
  const uniqueEntries: Entry[] = [];
  const seenPaths = new Set<string>();
  
  for (const entry of allEntries) {
    const normalizedPath = entry.path.replace(/\\/g, "/");
    if (!seenPaths.has(normalizedPath)) {
      seenPaths.add(normalizedPath);
      uniqueEntries.push({
        ...entry,
        path: normalizedPath
      });
    }
  }
  
  // 第四步：按路径排序，确保父目录在前
  uniqueEntries.sort((a, b) => {
    // 先按类型排序：目录在前
    if (a.type === "directory" && b.type === "file") return -1;
    if (a.type === "file" && b.type === "directory") return 1;
    // 然后按路径深度排序
    const aDepth = a.path.split("/").length;
    const bDepth = b.path.split("/").length;
    if (aDepth !== bDepth) return aDepth - bDepth;
    // 最后按名称排序
    return a.name.localeCompare(b.name);
  });
  
  // 第五步：构建树结构
  const pathToNode = new Map<string, TreeNode>();
  const rootNodes: TreeNode[] = [];
  
  // 创建所有节点
  for (const entry of uniqueEntries) {
    const node: TreeNode = {
      key: entry.path,
      title: entry.name,
      type: entry.type,
      path: entry.path,
      size: entry.size,
      children: entry.type === "directory" ? [] : undefined,
    };
    pathToNode.set(entry.path, node);
  }
  
  // 构建父子关系
  for (const entry of uniqueEntries) {
    const node = pathToNode.get(entry.path);
    if (!node) continue;
    
    // 计算相对路径
    const normalizedPath = entry.path;
    let relativePath: string;
    
    if (normalizedPath === normalizedRoot) {
      // rootPath本身，添加到根节点
      rootNodes.push(node);
      continue;
    } else if (normalizedPath.startsWith(normalizedRoot + "/")) {
      relativePath = normalizedPath.substring(normalizedRoot.length + 1);
    } else {
      // 虚拟条目，相对路径
      relativePath = normalizedPath;
    }
    
    const parts = relativePath.split("/").filter(Boolean);
    
    if (parts.length === 0) {
      // 这种情况不应该发生
      continue;
    }
    
    // 找到或创建父节点
    let parentPath = normalizedRoot;
    let parent = pathToNode.get(parentPath);
    
    // 如果没有父节点，创建虚拟父节点
    if (!parent) {
      // 创建根节点虚拟目录
      parent = {
        key: normalizedRoot,
        title: normalizedRoot.split("/").pop() || normalizedRoot,
        type: "directory",
        path: normalizedRoot,
        size: null,
        children: [],
      };
      pathToNode.set(normalizedRoot, parent);
      rootNodes.push(parent);
    }
    
    // 处理路径中的每一部分
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      const childPath = parentPath + "/" + part;
      
      // 检查子节点是否存在
      if (!pathToNode.has(childPath)) {
        // 创建虚拟目录节点
        const virtualNode: TreeNode = {
          key: childPath,
          title: part,
          type: "directory",
          path: childPath,
          size: null,
          children: [],
        };
        pathToNode.set(childPath, virtualNode);
        
        // 添加到父节点
        if (parent?.children) {
          parent.children.push(virtualNode);
        }
      }
      
      parentPath = childPath;
      parent = pathToNode.get(childPath);
    }
    
    // 添加当前节点到其父节点
    if (parent?.children) {
      parent.children.push(node);
    } else {
      // 没有父节点，添加到根节点
      rootNodes.push(node);
    }
  }
  
  // 第六步：清理和排序
  const cleanAndSort = (nodes: TreeNode[]): TreeNode[] => {
    return nodes
      .map((node) => {
        if (node.type === "directory" && node.children) {
          node.children = cleanAndSort(node.children);
        }
        return node;
      })
      .sort((a, b) => {
        if (a.type === "directory" && b.type === "file") return -1;
        if (a.type === "file" && b.type === "directory") return 1;
        return a.title.localeCompare(b.title);
      });
  };
  
  // 第七步：去重根节点
  const seenRootKeys = new Set<string>();
  const dedupedRootNodes: TreeNode[] = [];
  
  for (const node of rootNodes) {
    if (!seenRootKeys.has(node.key)) {
      seenRootKeys.add(node.key);
      dedupedRootNodes.push(node);
    }
  }
  
  return cleanAndSort(dedupedRootNodes);
}

/**
 * 非递归模式虚拟列表组件
 * 注意：搜索功能已移到父组件 ListDirectoryView 中
 */
interface VirtualFileListProps {
  filteredEntries: Entry[];
}

const VirtualFileList: React.FC<VirtualFileListProps> = ({ filteredEntries }) => {
  const fileListBackground = {
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.8,
    whiteSpace: "pre-wrap",
    boxShadow: "inset 0 1px 2px rgba(0,0,0,0.05)",
  };

  return (
    <div>
      <div style={fileListBackground}>
        <List
          dataSource={filteredEntries}
          size="small"
          style={{ maxHeight: 300, overflow: 'auto' }}
          renderItem={(entry: Entry, index: number) => (
            <List.Item
              key={`${entry.path}-${index}`}
              style={{
                padding: "4px 8px",
                borderBottom:
                  index < filteredEntries.length - 1
                    ? "1px solid #e8e8e8"
                    : "none",
              }}
            >
              <span>
                {entry.type === "directory" ? (
                  <FolderOutlined style={{ color: "#faad14", marginRight: 6 }} />
                ) : (
                  <FileOutlined style={{ color: "#1890ff", marginRight: 6 }} />
                )}
                {entry.name}
                {entry.size !== null && (
                  <span style={{ color: "#888", marginLeft: 8, fontSize: 12 }}>
                    ({formatFileSize(entry.size)})
                  </span>
                )}
              </span>
            </List.Item>
          )}
        />
      </div>
    </div>
  );
};

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024)
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
}

/**
 * ListDirectoryView 主组件
 * 【小沈修改 2026-03-24】添加 isExpanded 参数，控制列表内容折叠，目录信息始终可见
 * 【小强修改 2026-03-24】添加 onToggle 回调，在目录信息行显示折叠按钮
 * 【小强修复 2026-03-25】递归模式搜索：匹配到子节点时父节点链也要显示
 */
const ListDirectoryView: React.FC<ListDirectoryViewProps> = ({ data, toolParams, isExpanded = true, onToggle }) => {
  const { entries = [], total = 0, directory = "" } = data;

  // 【小强修复 2026-03-24】使用 toolParams 判断递归模式（从 step 传入，非从 data）
  const isRecursive = toolParams?.recursive === true;

  // 【小强修复 2026-03-25】Hooks 必须在顶层无条件调用
  const [searchText, setSearchText] = useState("");
  
  // 【小强修复】用户点击展开/折叠时的keys状态管理
  const [userExpandedKeys, setUserExpandedKeys] = useState<string[]>([]);

  // 计算树形数据
  const treeData = useMemo(
    () => convertEntriesToTree(entries, directory),
    [entries, directory]
  );

  // 【小强新增 2026-03-25】计算需要展开的父节点路径（递归模式搜索用）
  const searchExpandedKeys = useMemo(() => {
    if (!searchText.trim()) return [];
    const lowerSearch = searchText.toLowerCase();
    const keysToExpand = new Set<string>();

    // 遍历树，找到所有匹配的节点，收集它们的父节点路径
    const traverse = (nodes: TreeNode[], parentPath: string[]) => {
      for (const node of nodes) {
        const currentPath = [...parentPath, node.key];
        const title = node.title?.toString().toLowerCase() || "";
        const path = node.key?.toString().toLowerCase() || "";

        if (title.includes(lowerSearch) || path.includes(lowerSearch)) {
          // 匹配到了，收集所有父节点
          parentPath.forEach(p => keysToExpand.add(p));
        }

        // 继续遍历子节点
        if (node.children) {
          traverse(node.children, currentPath);
        }
      }
    };

    traverse(treeData, []);
    return Array.from(keysToExpand);
  }, [treeData, searchText]);

  // 【小强修复】合并展开的keys：搜索时只用searchExpandedKeys，无搜索时用userExpandedKeys
  const allExpandedKeys = useMemo(() => {
    if (!searchText.trim()) {
      return userExpandedKeys;
    }
    return searchExpandedKeys;
  }, [searchExpandedKeys, userExpandedKeys, searchText]);

  // 【小强修改 2026-03-25】递归模式：过滤后的树结构，匹配到子节点时保留父节点链
  const filteredTreeData = useMemo(() => {
    if (!searchText.trim()) return treeData;

    const lowerSearch = searchText.toLowerCase();
    const matchedKeys = new Set<string>();

    // 第一遍：收集所有匹配的节点 key
    const collectMatches = (nodes: TreeNode[]) => {
      for (const node of nodes) {
        const title = node.title?.toString().toLowerCase() || "";
        const path = node.key?.toString().toLowerCase() || "";

        if (title.includes(lowerSearch) || path.includes(lowerSearch)) {
          matchedKeys.add(node.key);
        }

        if (node.children) {
          collectMatches(node.children);
        }
      }
    };

    collectMatches(treeData);

    // 第二遍：过滤树，只保留匹配的节点及其父节点链
    const filterTree = (nodes: TreeNode[]): TreeNode[] => {
      const result: TreeNode[] = [];
      
      for (const node of nodes) {
        // 检查当前节点是否匹配
        const title = node.title?.toString().toLowerCase() || "";
        const path = node.key?.toString().toLowerCase() || "";
        const isMatch = title.includes(lowerSearch) || path.includes(lowerSearch);

        // 递归过滤子节点
        const filteredChildren = node.children ? filterTree(node.children) : undefined;

        // 如果当前节点匹配，或者有子节点匹配（children 被保留），则保留当前节点
        if (isMatch || (filteredChildren && filteredChildren.length > 0)) {
          result.push({
            ...node,
            children: filteredChildren,
          });
        }
      }

      return result;
    };

    return filterTree(treeData);
  }, [treeData, searchText]);

  // 文件列表背景样式
  const fileListBackground = {
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.8,
    whiteSpace: "pre-wrap",
    maxHeight: 300,
    overflow: "auto",
    boxShadow: "inset 0 1px 2px rgba(0,0,0,0.05)",
  };

  // 过滤后的文件列表（用于非递归模式）
  const filteredEntries = useMemo(() => {
    if (!searchText.trim()) {
      return entries;
    }
    const lowerSearch = searchText.toLowerCase();
    return entries.filter(
      (entry) =>
        entry.name.toLowerCase().includes(lowerSearch) ||
        entry.path.toLowerCase().includes(lowerSearch)
    );
  }, [entries, searchText]);

  if (entries.length === 0) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        📂 目录为空
      </div>
    );
  }

  // 【小强修改 2026-03-24】目录信息行：始终显示，包含文件数量和折叠按钮
  const directoryInfo = directory && (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 8,
        fontSize: 12,
        color: "#666",
        background: "#f5f5f5",
        padding: "4px 8px",
        borderRadius: 4,
        cursor: "pointer",
      }}
      onClick={onToggle}
    >
      <div>
        <span style={{ marginRight: 8 }}>📂 {directory}</span>
        {isRecursive ? "🌲 目录树" : "📁 文件列表"}
        ({total}个)
        {/* 【小强新增 2026-03-25】显示搜索匹配数量 */}
        {searchText && filteredEntries.length !== total && (
          <span style={{ color: "#faad14", marginLeft: 8 }}>
            (匹配 {isRecursive ? filteredTreeData.length : filteredEntries.length} 个)
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* 搜索框 - 折叠按钮右侧显示，仅在展开时显示 */}
        {entries.length > 10 && isExpanded && (
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索文件/文件夹..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200, fontSize: 12 }}
            allowClear
            onClick={(e) => e.stopPropagation()}
          />
        )}
        <span style={{ color: "#1890ff", fontWeight: 500 }}>
          {isExpanded ? "▼ 收起" : "▶ 展开"}
        </span>
      </div>
    </div>
  );

  return (
    <div>
      {/* 目录信息行 - 始终显示，包含文件数量和折叠按钮 */}
      {directoryInfo}

      {/* 【小沈修改 2026-03-24】列表内容根据 isExpanded 控制，目录信息始终可见 */}
      {isExpanded && (
        <>
          {/* 根据 recursive 参数选择显示方案 */}
          {isRecursive ? (
            /* 递归模式：树形结构 - 支持搜索展开+用户手动展开 */
            <div style={fileListBackground}>
              <DirectoryTree
                showLine={{ showLeafIcon: true }}
                treeData={filteredTreeData}
                // 【小强修复】使用allExpandedKeys：搜索时只用searchExpandedKeys，无搜索时用userExpandedKeys
                expandedKeys={allExpandedKeys}
                defaultExpandAll={false}
                // 【小强修复】允许用户点击展开/折叠
                selectable={false}
                onExpand={(keys) => {
                  setUserExpandedKeys(keys as string[]);
                }}
                style={{
                  background: "transparent",
                  fontSize: 13,
                }}
                icon={({ data }: any) =>
                  data.type === "directory" ? (
                    <FolderOutlined style={{ color: "#faad14" }} />
                  ) : (
                    <FileOutlined style={{ color: "#1890ff" }} />
                  )
                }
              />
            </div>
          ) : (
            /* 非递归模式：虚拟列表 - List自身管理滚动，外层div不限制 */
            <VirtualFileList filteredEntries={filteredEntries} />
          )}

          {/* 总数信息 - 也根据 isExpanded 控制 */}
          {total > 0 && (
            <div
              style={{
                marginTop: 8,
                fontSize: 12,
                color: "#666",
              }}
            >
              <span
                style={{
                  background: "#e6f7ff",
                  padding: "2px 8px",
                  borderRadius: 4,
                  color: "#1890ff",
                  fontWeight: 500,
                }}
              >
                📊 共 {total} 个项目
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ListDirectoryView;
