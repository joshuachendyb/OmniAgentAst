/**
 * MessageItem组件 - 单条消息展示
 *
 * 功能：展示用户/AI/系统消息，支持头像、时间戳、复制功能
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState } from "react";
import {
  Avatar,
  Tooltip,
  Button,
  message as antMessage,
  Tree,
  Input,
} from "antd";
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
  FolderOutlined,
  FileOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import { taskControlApi } from "../../services/api";
import { formatTimestamp } from "../../utils/timestamp";
import { } from "../../utils/markdown";
import ErrorDetail from "./ErrorDetail";

// 【小强实现 2026-03-24】阶段3：导入7个工具视图组件
import ListDirectoryView from "./views/ListDirectoryView";
import ReadFileView from "./views/ReadFileView";
import WriteFileView from "./views/WriteFileView";
import DeleteFileView from "./views/DeleteFileView";
import MoveFileView from "./views/MoveFileView";
import SearchFilesView from "./views/SearchFilesView";
import GenerateReportView from "./views/GenerateReportView";

/**
 * 树形节点类型 - 用于 convertEntriesToTree 函数
 */
interface TreeNode {
  key: string;
  title: string;
  type: 'directory' | 'file';
  children?: TreeNode[];
  path: string;
  size: number | null;
}

/**
 * 条目类型 - list_directory 工具返回的文件条目
 */
interface Entry {
  name: string;
  path: string;
  type: 'directory' | 'file';
  size: number | null;
}

/**
 * 将扁平的 entries 数组转换为树形结构（供 Tree 组件使用）
 * 【小强实现 2026-03-23】阶段4任务2：convertToTree数据转换函数
 */
function convertEntriesToTree(entries: Entry[], rootPath: string): TreeNode[] {
  if (!entries || entries.length === 0) {
    return [];
  }

  const pathToNode = new Map<string, TreeNode>();
  const rootNodes: TreeNode[] = [];

  // 标准化 rootPath，移除末尾斜杠
  const normalizedRoot = rootPath.replace(/\\/g, '/').replace(/\/$/, '');

  // 按 type 排序：目录在前，文件在后
  const sortedEntries = [...entries].sort((a, b) => {
    if (a.type === 'directory' && b.type === 'file') return -1;
    if (a.type === 'file' && b.type === 'directory') return 1;
    return a.name.localeCompare(b.name);
  });

  // 第一遍：创建所有节点
  for (const entry of sortedEntries) {
    const node: TreeNode = {
      key: entry.path,
      title: entry.name,
      type: entry.type,
      path: entry.path,
      size: entry.size,
      children: entry.type === 'directory' ? [] : undefined,
    };
    pathToNode.set(entry.path, node);
  }

  // 第二遍：构建父子关系
  for (const entry of sortedEntries) {
    const node = pathToNode.get(entry.path);
    if (!node) continue;

    // 标准化当前路径
    const normalizedPath = entry.path.replace(/\\/g, '/');

    // 计算相对路径：从 rootPath 之后的部分
    let relativePath: string;
    if (normalizedPath.startsWith(normalizedRoot + '/')) {
      relativePath = normalizedPath.substring(normalizedRoot.length + 1);
    } else if (normalizedPath.startsWith(normalizedRoot)) {
      relativePath = normalizedPath.substring(normalizedRoot.length);
    } else {
      // 相对路径情况
      relativePath = normalizedPath;
    }

    const parts = relativePath.split('/').filter(Boolean);

    if (parts.length === 0) {
      // 根路径本身就是节点
      rootNodes.push(node);
      continue;
    }

    if (parts.length === 1) {
      // 直接子项，父级是 rootPath
      const parentNode = pathToNode.get(normalizedRoot);
      if (parentNode?.children) {
        parentNode.children.push(node);
      } else {
        rootNodes.push(node);
      }
      continue;
    }

    // 多层嵌套：构建虚拟目录链
    // parts = ['src', 'components', 'App.tsx']
    // 需要创建: src -> components -> App.tsx

    let currentParentPath = normalizedRoot;

    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      const fullPath = currentParentPath + '/' + part;

      if (!pathToNode.has(fullPath)) {
        // 创建虚拟目录
        const virtualNode: TreeNode = {
          key: fullPath,
          title: part,
          type: 'directory',
          path: fullPath,
          size: null,
          children: [],
        };
        pathToNode.set(fullPath, virtualNode);

        // 链接到父级
        const parentNode = pathToNode.get(currentParentPath);
        if (parentNode?.children) {
          parentNode.children.push(virtualNode);
        } else if (currentParentPath === normalizedRoot) {
          // 第一层虚拟目录
          rootNodes.push(virtualNode);
        }
      }

      currentParentPath = fullPath;
    }

    // 最后一项添加到其父级
    const finalParentNode = pathToNode.get(currentParentPath);
    if (finalParentNode?.children) {
      finalParentNode.children.push(node);
    } else {
      rootNodes.push(node);
    }
  }

  // 清理空目录的 children
  const cleanEmptyChildren = (nodes: TreeNode[]): TreeNode[] => {
    return nodes.map(node => {
      if (node.type === 'directory' && node.children) {
        node.children = cleanEmptyChildren(node.children);
      }
      return node;
    }).sort((a, b) => {
      if (a.type === 'directory' && b.type === 'file') return -1;
      if (a.type === 'file' && b.type === 'directory') return 1;
      return a.title.localeCompare(b.title);
    });
  };

  return cleanEmptyChildren(rootNodes);
}

/**
 * 非递归模式虚拟列表组件
 * 【小强实现 2026-03-23】阶段4任务3：非递归模式虚拟列表
 */
interface VirtualFileListProps {
  entries: any[];
}

const VirtualFileList: React.FC<VirtualFileListProps> = ({ entries }) => {
  const [searchText, setSearchText] = useState('');
  
  const filteredEntries = searchText
    ? entries.filter((entry: Entry) => 
        entry.name.toLowerCase().includes(searchText.toLowerCase())
      )
    : entries;
  
  const fileListStyle: React.CSSProperties = {
    background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
    border: "1px solid #b7eb8f",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.8,
    whiteSpace: "pre-wrap",
  };
  
  return (
    <div style={fileListStyle}>
      <Input
        prefix={<SearchOutlined style={{ color: '#bbb' }} />}
        placeholder="搜索文件..."
        allowClear
        style={{ marginBottom: 8, fontSize: 12 }}
        size="small"
        value={searchText}
        onChange={(e) => setSearchText(e.target.value)}
      />
      <div style={{ maxHeight: 300, overflow: 'auto' }}>
        {filteredEntries.map((entry: Entry, idx: number) => (
          <div 
            key={`file-${idx}`}
            style={{ 
              padding: '4px 0',
              borderBottom: idx < filteredEntries.length - 1 ? '1px solid #e8e8e8' : 'none',
            }}
          >
            <span>
              {entry.type === "directory" ? "📁" : "📄"} {entry.name}
              {entry.type === "file" && entry.size !== null && (
                <span style={{ color: '#888', marginLeft: 8, fontSize: 11 }}>
                  ({(entry.size / 1024).toFixed(1)} KB)
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * 步骤行组件 - 单行步骤显示（优化后新增）
 * 思考和执行分开渲染，用颜色区分类型
 * 【小强优化 2026-03-18】UX 视觉升级：渐变徽章、柔和背景、精致阴影
 * 【小新重构 2026-03-09】添加分页支持
 */
// 【小资修复 2026-03-23】StepRow props：接收全局Map状态
interface StepRowProps {
  step: ExecutionStep;
  taskId?: string;
  stepIndex?: number;
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
}

const StepRow: React.FC<StepRowProps> = ({ step, taskId, stepIndex = 0, expandedSteps, toggleExpand }) => {
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // 【小资修复 2026-03-23】从全局Map读取展开状态（未设置的key默认展开）
  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  
  // 【小强优化 2026-03-18】渐变色方案
  const gradientMap: Record<string, string> = {
    start: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
    thought: "linear-gradient(135deg, #faad14 0%, #d48806 100%)",
    action_tool: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
    observation: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
    final: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
    error: "linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%)",
    paused: "linear-gradient(135deg, #fa8c16 0%, #d46b08 100%)",
    resumed: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
    interrupted: "linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%)",
    retrying: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
  };

  const labelMap: Record<string, string> = {
    start: "开始",
    thought: "分析",
    action_tool: "执行",
    observation: "检查",
    final: "总结",
    error: "错误",
    paused: "暂停",
    resumed: "恢复",
    interrupted: "中断",
    retrying: "重试",
  };

  const iconMap: Record<string, string> = {
    start: "🚀",
    thought: "💭",
    action_tool: "⚙️",
    observation: "🔍",
    final: "✅",
    error: "❌",
    paused: "⏸️",
    resumed: "▶️",
    interrupted: "⚠️",
    retrying: "🔄",
  };

  const gradient = gradientMap[step.type] || "#666";
  const label = labelMap[step.type] || "步骤";
  const icon = iconMap[step.type] || "";

  // 【小强优化 2026-03-18】步骤编号颜色随类型变化
  const getStepBadgeStyle = () => {
    const baseStyle: React.CSSProperties = {
      background: gradient,
      color: "white",
      padding: "2px 8px",
      borderRadius: 6,
      fontSize: 11,
      marginRight: 8,
      fontWeight: 600,
      display: "inline-block",
      minWidth: 50,
      textAlign: "center",
      boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
    };
    return baseStyle;
  };

  // 【小强优化 2026-03-18】标签样式
  const getLabelStyle = () => {
    return {
      color: gradient,
      fontWeight: 600,
      marginRight: 8,
      fontSize: 13,
    };
  };

  // 【小强优化 2026-03-18】内容区域样式
  const getContentStyle = () => {
    const baseStyle: React.CSSProperties = {
      color: "#333",
      wordBreak: "break-word",
      fontSize: 13,
      lineHeight: 1.8,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
    };
    return baseStyle;
  };

  // 【小强优化 2026-03-18】思考内容背景
  const getThoughtBackground = () => {
    return {
      background: "linear-gradient(135deg, #fff7e6 0%, #fffbe6 100%)",
      border: "1px solid #ffd591",
      borderRadius: 8,
      padding: "10px 14px",
      marginTop: 6,
      lineHeight: 1.8,
      fontSize: 13,
    };
  };

  // 【小强优化 2026-03-18】文件列表背景
  const getFileListBackground = () => {
    return {
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
  };

  // 【小新重构 2026-03-09】处理加载更多
  const handleLoadMore = async () => {
    if (!step.raw_data?.has_more || !step.raw_data?.next_page_token || !taskId) {
      return;
    }
    
    setIsLoadingMore(true);
    try {
      const result = await taskControlApi.nextPage(
        taskId,
        step.tool_name || "",
        step.raw_data.next_page_token
      );
      
      if (result.success && result.data) {
        console.log("✅ 加载更多成功:", result.data);
        // TODO: 追加新数据到列表（需要状态管理）
      }
    } catch (error) {
      console.error("❌ 加载更多失败:", error);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // 检查是否有分页数据
  const hasMore = step.raw_data?.has_more === true && !!step.raw_data?.next_page_token;

  return (
    <div style={{ 
      marginBottom: 8, 
      marginRight: 30,
      padding: "8px 12px",
      borderRadius: 8,
      background: "rgba(0,0,0,0.02)",
      transition: "all 0.2s ease",
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.background = "rgba(0,0,0,0.04)";
      e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.background = "rgba(0,0,0,0.02)";
      e.currentTarget.style.boxShadow = "none";
    }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap" as const }}>
        {/* 【小强优化 2026-03-18】步骤编号徽章 */}
        {step.step && (
          <span style={getStepBadgeStyle()}>
            步骤{step.step}
          </span>
        )}
        {/* 【小强优化 2026-03-18】标签带图标 */}
        <span style={getLabelStyle()}>
          {icon} {label}：
        </span>
      </div>
      <div style={{ ...getContentStyle(), marginTop: 4, marginLeft: 66 }}>
        {step.type === "action_tool" && (
          <>
            {step.action_description || step.tool_name || "执行中..."}
            {step.tool_params && (
              <div style={{ 
                marginTop: 6, 
                fontSize: 12, 
                color: "#666",
                background: "#f5f5f5",
                padding: "8px 12px",
                borderRadius: 6,
                fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                lineHeight: 1.6,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                参数：{JSON.stringify(step.tool_params)}
              </div>
            )}
            {/* 【小强实现 2026-03-23】阶段4任务1：isRecursive判断逻辑 */}
            {(() => {
              const isRecursive = step.tool_params?.recursive === true;
              const entries = step.raw_data?.entries || [];
              const rootPath = step.raw_data?.directory || '';
              
              // 只有在递归模式下才计算 treeData
              const treeData = isRecursive ? convertEntriesToTree(entries as Entry[], rootPath) : [];
              
              return (
                <div style={{ marginTop: 8 }}>
                  {/* 折叠按钮和文件计数 */}
                  <div style={{ marginBottom: 6 }}>
                    <span 
                      onClick={() => toggleExpand(stepIndex)}
                      style={{ 
                        cursor: "pointer", 
                        color: isRecursive ? "#52c41a" : "#1890ff",
                        fontSize: 12,
                        fontWeight: 500,
                      }}
                    >
                      {isExpanded 
                        ? "▼ 收起" 
                        : "▶ 展开"} 
                      {isRecursive ? "目录树" : "文件列表"} 
                      ({entries.length}个)
                      {isRecursive && <span style={{ marginLeft: 8, color: '#888' }}>🌲 递归模式</span>}
                    </span>
                  </div>
                  
                  {/* 文件列表内容 - 根据 isRecursive 选择显示方案 */}
                  {isExpanded && entries.length > 0 && (
                    isRecursive ? (
                      /* 【小强实现 2026-03-23】阶段4任务4：递归模式树形结构 */
                      <div style={getFileListBackground()}>
                        <Tree
                          showLine={{ showLeafIcon: true }}
                          treeData={treeData}
                          defaultExpandAll={false}
                          style={{
                            background: 'transparent',
                            fontSize: 13,
                          }}
                          icon={({ data }: any) => 
                            data.type === 'directory' 
                              ? <FolderOutlined style={{ color: '#faad14' }} /> 
                              : <FileOutlined style={{ color: '#1890ff' }} />
                          }
                        />
                      </div>
                    ) : (
                      /* 【小强实现 2026-03-23】阶段4任务3：非递归模式虚拟列表 */
                      <VirtualFileList 
                        entries={entries} 
                      />
                    )
                  )}

                  {/* 【小强实现 2026-03-24】阶段3：使用 renderToolResult 渲染工具结果视图 */}
                  {isExpanded && renderToolResult(step)}
                </div>
              );
            })()}
            {/* 【小新重构 2026-03-09】显示分页信息 */}
            {step.raw_data && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
                {step.raw_data.total && (
                  <span style={{ 
                    marginRight: 12,
                    background: "#e6f7ff",
                    padding: "2px 8px",
                    borderRadius: 4,
                    color: "#1890ff",
                    fontWeight: 500,
                  }}>
                    📊 共 {step.raw_data.total} 个项目
                  </span>
                )}
                {hasMore && (
                  <span 
                    onClick={handleLoadMore}
                    style={{ 
                      cursor: isLoadingMore ? "not-allowed" : "pointer", 
                      color: isLoadingMore ? "#999" : "#1890ff",
                      textDecoration: isLoadingMore ? "none" : "underline",
                      fontWeight: 500,
                      transition: "all 0.2s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!isLoadingMore) {
                        e.currentTarget.style.color = "#096dd9";
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = isLoadingMore ? "#999" : "#1890ff";
                    }}
                  >
                    {isLoadingMore ? "⏳ 加载中..." : "📄 加载更多"}
                  </span>
                )}
              </div>
            )}
          </>
        )}
        {step.type === "observation" && (
          <>
            {/* 【小沈修正 2026-03-23】显示 Agent 的思考过程 - 使用 step.obs_reasoning（和SSE后端字段名一致） */}
            {step.obs_reasoning && (
              <div style={{ 
                ...getThoughtBackground(),
                color: "#888",
                fontStyle: "italic",
                marginBottom: 8,
                fontSize: "0.95em",
              }}>
                💭 {step.obs_reasoning}
              </div>
            )}
            {/* 【小沈修复2026-03-23】显示 observation 的 content 字段 */}
            {step.content && typeof step.content === "string" && (
              <div style={{ 
                background: "linear-gradient(135deg, #f6ffed 0%, #f5f5f5 100%)",
                border: "1px solid #b7eb8f",
                borderRadius: 8,
                padding: "10px 14px",
                marginTop: 6,
                fontSize: 13,
                lineHeight: 1.8,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}>
                📋 {step.content}
              </div>
            )}
              {/* 显示执行结果 - 只有当没有 content 时才显示 */}
            {!step.content && (
              <div>
                {/* 【小沈修正 2026-03-23】文件列表框框 - 使用 step.obs_raw_data（和SSE后端字段名一致） */}
                {(() => {
                  const obsRawData = step.obs_raw_data;
                  const hasEntries = obsRawData?.entries && Array.isArray(obsRawData.entries);
                  const entryCount = hasEntries ? obsRawData.entries.length : 0;
                  
                  return (
                    <div>
                      {hasEntries && (
                        <div>
                          {/* 折叠按钮和文件计数 */}
                          <div style={{ marginBottom: 6 }}>
                            <span 
                              onClick={() => toggleExpand(stepIndex)}
                              style={{ 
                                cursor: "pointer", 
                                color: "#52c41a",
                                fontSize: 12,
                                fontWeight: 500,
                              }}
                            >
                              {isExpanded ? "▼ 收起" : "▶ 展开"} 文件列表 
                              ({entryCount}个)
                            </span>
                          </div>
                          {/* 文件列表内容 */}
                          {isExpanded && obsRawData?.entries && (
                            <div style={getFileListBackground()}>
                              {obsRawData.entries.map((entry: any, idx: number) => (
                                <React.Fragment key={`obs-entry-${idx}`}>
                                  <div style={{ 
                                    padding: "4px 0",
                                    borderBottom: idx < obsRawData.entries.length - 1 ? "1px solid #e8e8e8" : "none",
                                  }}>
                                    {entry.type === "directory" ? "📁" : "📄"} {entry.name}
                                  </div>
                                </React.Fragment>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      {/* 【小强修正 2026-03-23】summary 字符串 - 使用 step.obs_summary（和SSE后端字段名一致） */}
                      {typeof step.obs_summary === "string" && (
                        <div style={{ marginTop: 6 }}>{step.obs_summary}</div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
          </>
        )}
        {step.type === "start" && (
          <span style={{ 
            color: "#1890ff",
            fontWeight: 600,
            fontSize: 14,
          }}>
            🚀 {step.task_id || "任务开始"}
          </span>
        )}
        {step.type === "thought" && (
          <div style={{ 
            ...getThoughtBackground(),
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}>
            {/* 【小沈修复 2026-03-23】使用 step.reasoning 而非 step.thinking_prompt */}
            💭 {step.reasoning || step.content || ""}
          </div>
        )}
        {step.type === "final" && (
          <span style={{ 
            color: "#52c41a",
            fontWeight: 600,
            fontSize: 14,
          }}>
            ✅ {step.content || ""}
          </span>
        )}
        {step.type === "error" && (
          <span style={{ 
            color: "#ff4d4f",
            fontWeight: 600,
            fontSize: 13,
          }}>
            ❌ 错误：{step.error_message || ""}
          </span>
        )}
      </div>
    </div>
  );
};

/**
 * 【小强实现 2026-03-24】阶段3：renderToolResult 分支函数
 * 根据 tool_name 渲染不同的工具结果视图组件
 */
const renderToolResult = (step: ExecutionStep) => {
  // 从 raw_data 中获取 data
  const data = (step as any).raw_data?.data || (step as any).raw_data;
  if (!data) return null;

  // 根据 tool_name 分支处理
  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryView data={data} />;
    case "read_file":
      return <ReadFileView data={data} />;
    case "write_file":
      return <WriteFileView data={data} />;
    case "delete_file":
      return <DeleteFileView data={data} />;
    case "move_file":
      return <MoveFileView data={data} />;
    case "search_files":
      return <SearchFilesView data={data} />;
    case "generate_report":
      return <GenerateReportView data={data} />;
    default:
      // 未知工具，显示原始JSON
      return (
        <pre style={{
          background: "#f5f5f5",
          padding: "10px",
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 300,
          overflow: "auto",
        }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
};

interface MessageItemProps {
  message: ChatMessage & {
    id: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;
    provider?: string; // 提供商
    isStreaming?: boolean;
    isError?: boolean;
    display_name?: string; // 前端小新代修改：显示名称
    is_reasoning?: boolean; // 【小查修复】是否为思考过程（统一使用 snake_case）
    task_id?: string; // 【小新重构2026-03-09】任务ID，用于分页请求
    // 【小查修复2026-03-13】error相关字段（与API文档11个字段对齐）
    errorType?: string;      // error_type
    errorCode?: string;     // code
    errorMessage?: string;  // message - 错误消息内容
    errorDetails?: string;   // details
    errorStack?: string;    // stack
    errorRetryable?: boolean; // retryable
    errorRetryAfter?: number; // retry_after
    errorTimestamp?: string;  // timestamp
  };
  showExecution?: boolean;
  sessionId?: string | null;  // 【小强添加 2026-03-23】会话ID，用于导出
  sessionTitle?: string | null;  // 【小强添加 2026-03-23】会话标题，用于导出
}

/**
 * 消息项组件
 *
 * 设计要点：
 * - 用户消息：蓝色渐变，右侧对齐
 * - AI消息：白色卡片，左侧对齐，绿色边框
 * - 系统消息：浅黄色背景，居中
 * - 悬停显示复制按钮
 *
 * @param message - 消息对象
 * @param showExecution - 是否显示执行过程
 */
const MessageItem: React.FC<MessageItemProps> = ({
  message,
  showExecution: _showExecution = false,
  sessionId,
  sessionTitle,
}) => {
  const [copied, setCopied] = useState(false);
  // 【小强修复 2026-03-23】使用Map存储每个步骤的展开状态，支持多步骤独立折叠
  const [expandedSteps, setExpandedSteps] = useState<Map<number, boolean>>(new Map([[0, true]]));

  // 【小强修复 2026-03-23】切换展开状态
  const toggleExpand = (index: number) => {
    setExpandedSteps(prev => {
      const newMap = new Map(prev);
      newMap.set(index, !newMap.get(index));
      return newMap;
    });
  };

  /**
   * 复制消息内容
   */
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      antMessage.success("已复制到剪贴板");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      antMessage.error("复制失败");
    }
  };

  /**
   * 导出消息内容
   * - 有执行步骤：导出JSON格式
   * - 有执行步骤：导出JSON格式（包含所有8种type的完整字段）
   * - 是错误消息：导出JSON格式（包含完整error信息）
   * - 是incident消息：导出JSON格式（包含完整incident信息）
   * 
   * 【重要】8种type说明：
   * - 内容步骤：start（开始）、chunk（AI回复内容片段）、final（最终回答）
   *   【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
   * - 执行步骤：thought（思考）、action_tool（工具调用）、observation（工具结果）
   * - 异常步骤：error（错误）、incident（中断）
   */
  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log("🔍 [handleExport] 开始导出, message.id=", message.id);
    try {
      const hasSteps = message.executionSteps && message.executionSteps.length > 0;
      const isError = message.isError;
      console.log("🔍 [handleExport] hasSteps=", hasSteps, "isError=", isError, "executionSteps数量=", message.executionSteps?.length);
      
      let blob: Blob;
      let filename: string;
       
      // 统一的导出数据结构
      const exportData: Record<string, any> = {
        sessionId: sessionId || undefined,  // 【小强添加 2026-03-23】会话ID
        sessionTitle: sessionTitle || undefined,  // 【小强添加 2026-03-23】会话标题
        timestamp: formatTimestamp(message.timestamp instanceof Date ? message.timestamp.getTime() : message.timestamp),
        messageId: message.id,
        role: message.role,
        content: message.content,
      };
      
      // 检查是否包含incident类型的步骤（incident对应的是interrupted/paused/resumed/retrying）
      const hasIncident = hasSteps && message.executionSteps?.some(
        (step) => step.type === 'interrupted' || step.type === 'paused' || 
                  step.type === 'resumed' || step.type === 'retrying'
      );
      
      if (hasIncident) {
        // 【小查修复2026-03-13】包含incident类型：导出JSON格式（包含完整的incident字段）
        exportData.incidentSteps = message.executionSteps?.filter(
          (step) => step.type === 'interrupted' || step.type === 'paused' || 
                    step.type === 'resumed' || step.type === 'retrying'
        ).map(step => ({
          type: step.type,
          incident_value: (step as any).incident_value || step.content,
          message: step.content,
          timestamp: formatTimestamp((step as any).timestamp),
          wait_time: (step as any).wait_time,
        }));
      }
       
      if (isError) {
        // 错误消息：导出JSON格式（使用API文档字段名）
        exportData.error = {
          type: "error",
          error_type: message.errorType,
          code: message.errorCode,
          message: message.errorMessage,
          details: message.errorDetails,
          stack: message.errorStack,
          retryable: message.errorRetryable,
          retry_after: message.errorRetryAfter,
          timestamp: formatTimestamp(message.errorTimestamp),
          model: message.model,
          provider: message.provider,
        };
        // 【小强修复 2026-03-17】executionSteps 也要转换 timestamp
        exportData.executionSteps = message.executionSteps?.map(step => ({
          ...step,
          timestamp: formatTimestamp(step.timestamp),
        }));
        filename = `error_${message.id}_${new Date().toISOString().replace(/[/:]/g, "-")}.json`;
      } else if (hasSteps) {
        // 有执行步骤：导出JSON格式（包含所有8种type的完整字段）
        // 8种type: start, thought, action_tool, observation, chunk, final, error, incident
        exportData.executionSteps = message.executionSteps?.map(step => {
          const baseExport: Record<string, any> = {
            type: step.type,
            content: step.content,
            timestamp: formatTimestamp(step.timestamp),  // 转换为可读格式
          };
          
          // 根据不同type添加对应字段
          switch (step.type) {
            case 'thought':
              return { ...baseExport, step: step.step, reasoning: step.reasoning, action_tool: step.action_tool, params: step.params };
            case 'action_tool':
              return { ...baseExport, step: step.step, tool_name: step.tool_name, tool_params: step.tool_params, execution_status: step.execution_status, summary: step.summary, raw_data: step.raw_data, action_retry_count: step.action_retry_count };
            case 'observation':
              // 【小沈修正 2026-03-23】导出字段名必须和SSE后端定义一模一样（带obs_前缀）
              return { ...baseExport, step: step.step, obs_execution_status: step.obs_execution_status, obs_summary: step.obs_summary, obs_raw_data: step.obs_raw_data, content: step.content, obs_reasoning: step.obs_reasoning, obs_action_tool: step.obs_action_tool, obs_params: step.obs_params, is_finished: step.is_finished };
            case 'chunk':
              return { ...baseExport, step: step.step, is_reasoning: step.is_reasoning };
            case 'final':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step };
            case 'error':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step, code: (step as any).code, error_type: (step as any).error_type, details: (step as any).details, stack: (step as any).stack, retryable: (step as any).retryable, retry_after: (step as any).retry_after, model: (step as any).model, provider: (step as any).provider };
            case 'interrupted':
            case 'paused':
            case 'resumed':
            case 'retrying':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step, incident_value: (step as any).incident_value || step.type, wait_time: (step as any).wait_time };
            case 'start':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, task_id: step.task_id, step: step.step };
            default:
              return baseExport;
          }
        });
        filename = `execution_steps_${new Date().toISOString().replace(/[/:]/g, "-")}.json`;
      } else {
        // 无执行步骤：导出TXT格式
        const content = message.content || "";
        blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        filename = `message_${message.id}_${new Date().toLocaleString("zh-CN").replace(/[/:]/g, "-")}.txt`;
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        antMessage.success("导出成功");
        return;
      }
      
      // JSON格式导出
      const jsonStr = JSON.stringify(exportData, null, 2);
      blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      antMessage.success("导出成功");
    } catch (err) {
      console.error("🔍 [handleExport] 导出失败, error=", err);
      antMessage.error("导出失败");
    }
  };

  /**
   * 获取角色图标
   */
  const getAvatar = () => {
    switch (message.role) {
      case "user":
        return (
          <Avatar
            size={40}
            icon={<UserOutlined />}
            style={{
              background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
            }}
          />
        );
      case "assistant":
        return (
          <Avatar
            size={40}
            icon={<RobotOutlined />}
            style={{
              background: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
            }}
          />
        );
      case "system":
        return (
          <Avatar
            size={40}
            icon={<InfoCircleOutlined />}
            style={{ background: "#faad14" }}
          />
        );
      default:
        return null;
    }
  };

  /**
   * 获取角色名称
    */
  const getRoleName = () => {
    switch (message.role) {
      case "user":
        return "我";
      case "assistant": {
        // ✅ 老杨 UX 建议：占位消息显示 loading 状态
        // 前端小新代修改：只要 isStreaming 为 true，就显示加载状态，并且显示 display_name
        if (message.isStreaming) {
          // 前端小新代修改：加载状态也显示 display_name（如果存在）
          // 如果 display_name 为空，尝试使用 model 构建
          let display_nameToShow = message.display_name;
          if (!display_nameToShow && message.model) {
            display_nameToShow = message.model;
          }
          
          const result = display_nameToShow
            ? `🤔 AI 助手【${display_nameToShow}】【加载中...】`
            : `🤔 AI 助手【加载中...】`;
          return result;
        }


        // 前端小新代修改 VIS-E02: 错误消息显示错误标识
        if (message.isError) {
          // ✅ 老杨 UX 建议：添加错误图标（⚠️）
          return message.display_name
            ? `⚠️ AI 助手【${message.display_name}】【错误】`
            : `⚠️ AI 助手【错误】`;
        }
        // 直接使用后端返回的 display_name，用【】包住显示
        return message.display_name
          ? `AI 助手【${message.display_name}】`
          : "AI 助手";
      }
      case "system":
        return "系统";
      default:
        return "";
    }
  };

  /**
   * 获取消息样式 - 前端小新代修改 VIS-C01: 圆角优化，VIS-C02: padding 优化，VIS-C03: 阴影优化，VIS-E01: 错误消息样式，UX-C04: 留白优化（用户建议 50%）
   */
  const getMessageStyle = () => {
    const baseStyle: React.CSSProperties = {
      maxWidth: "100%",
      minWidth: "60px",
      width: "auto",
      // 【小查修复2026-03-13】拆分为单独属性，避免与paddingRight冲突
      paddingTop: 8,
      paddingBottom: 8,
      paddingLeft: 10,
      paddingRight: 10,
      borderRadius: "16px",
      position: "relative",
      transition: "all 0.3s ease",
      whiteSpace: "pre-wrap",
      wordBreak: "normal",
      overflowWrap: "break-word",
    };

    // 前端小新代修改 VIS-E01: 错误消息样式
    if (message.role === "assistant" && message.isError) {
      return {
        ...baseStyle,
        background: "#fff1f0",
        border: "1px solid #ffa39e",
        color: "#cf1322",
        boxShadow: "0 4px 12px rgba(255, 77, 79, 0.15)",
      };
    }

    switch (message.role) {
      case "user":
        return {
          ...baseStyle,
          background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
          color: "#fff",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          paddingRight: 30, // 为右侧按钮留出空间
        };
      case "assistant":
        return {
          ...baseStyle,
          background: "#fff",
          border: "1px solid #b7eb8f",
          color: "#262626",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          paddingRight: 30, // 为右侧按钮留出空间
        };
      case "system":
        return {
          ...baseStyle,
          background: "#fffbe6",
          border: "1px solid #ffe58f",
          color: "#ad6800",
          maxWidth: "90%",
          textAlign: "center" as const,
          whiteSpace: "nowrap" as const, // ✅ 小新修复 2026-03-01 14:38:19：系统消息不折行，覆盖 baseStyle 的 pre-wrap
        };
      default:
        return baseStyle;
    }
  };

  /**
   * 格式化时间戳
   */
  const formatTime = (date: Date | string) => {
    try {
      // 确保转换为Date对象
      const dateObj = date instanceof Date ? date : new Date(date);

      // 检查是否有效日期
      if (isNaN(dateObj.getTime())) {
        return "刚刚";
      }

      return dateObj.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (error) {
      return "刚刚";
    }
  };

  /**
   * 格式化相对时间
   */
  const getRelativeTime = (date: Date | string) => {
    try {
      // 确保转换为Date对象
      const dateObj = date instanceof Date ? date : new Date(date);

      // 检查是否有效日期
      if (isNaN(dateObj.getTime())) {
        return "刚刚";
      }

      const now = new Date();
      const diff = now.getTime() - dateObj.getTime();
      const minutes = Math.floor(diff / 60000);

      if (minutes < 1) return "刚刚";
      if (minutes < 60) return `${minutes}分钟前`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}小时前`;
      return dateObj.toLocaleDateString("zh-CN");
    } catch (error) {
      return "刚刚";
    }
  };

const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: isSystem
          ? "center"
          : isUser
          ? "flex-end"
          : "flex-start",
        marginBottom: 12,
        gap: 12,
        width: "100%",
      }}
    >
      {/* 左侧头像（AI 消息） */}
      {!isUser && !isSystem && (
        <div style={{ flexShrink: 0, marginTop: 8 }}>
          {getAvatar()}
        </div>
      )}

      {/* 消息内容区 - 简化结构 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
          maxWidth: "calc(100% - 60px)",
        }}
      >
        {/* 角色名称和时间戳区域 */}
        {!isSystem && (
          <div
            style={{
              marginBottom: 4,
              fontSize: 12,
              color: isUser ? "#1890ff" : "#52c41a",
              fontWeight: 500,
              opacity: 0.85,
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              gap: isUser ? "0" : "8px",
              flexDirection: isUser ? "row-reverse" : "row",
            }}
          >
            <span style={{ whiteSpace: "nowrap" }}>
              {getRoleName()}
            </span>
            {/* 时间戳移到角色名称同一行 */}
              <span
              style={{
                fontSize: 11,
                color: "#999999",
                whiteSpace: "nowrap",
              }}
            >
              <Tooltip title={formatTime(message.timestamp)}>
                <span>{getRelativeTime(message.timestamp)}</span>
              </Tooltip>
            </span>
          </div>
        )}

        {/* 消息内容 - 优化后的结构 */}
        <div style={{ ...getMessageStyle(), position: "relative" }}>
          {/* 复制按钮（悬停显示）- 透明背景，小巧精致 */}
          <Tooltip title={copied ? "已复制" : "复制"}>
            <Button
              className="copy-button"
              type="text"
              size="small"
              icon={
                copied ? (
                  <CheckOutlined style={{ color: "#52c41a" }} />
                ) : (
                  <CopyOutlined style={{ color: isUser ? "rgba(255,255,255,0.9)" : "#595959" }} />
                )
              }
              onClick={handleCopy}
              style={{
                position: "absolute",
                top: 4,
                right: 6,
                opacity: 0,
                transition: "opacity 0.2s ease",
                background: "transparent",
                border: "none",
                boxShadow: "none",
                padding: "0 4px",
                minHeight: "auto",
                height: "20px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            />
          </Tooltip>

          {/* 导出按钮 */}
          <Tooltip title="导出">
            <Button
              className="copy-button"
              type="text"
              size="small"
              icon={<DownloadOutlined style={{ color: isUser ? "rgba(255,255,255,0.9)" : "#595959" }} />}
              onClick={handleExport}
              style={{
                position: "absolute",
                top: 4,
                right: 30,
                opacity: 0,
                transition: "opacity 0.2s ease",
                background: "transparent",
                border: "none",
                boxShadow: "none",
                padding: "0 4px",
                minHeight: "auto",
                height: "20px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            />
          </Tooltip>

          <>
          {/* 【小强简化2026-03-18】按step顺序显示 - 用StepRow渲染 */}
          {/* 【重要】过滤逻辑：
           * - chunk：永远不在步骤列表显示（是AI回复内容，在AI回复区域显示）
           * - final：普通对话模式（有chunk）时不显示，ReAct模式时显示
           */}
          {(() => {
              const allSteps = message.executionSteps || [];
              // 判断是否是普通对话模式（有 chunk）
              const hasChunk = allSteps.some(step => step.type === 'chunk');
              // 过滤：普通对话模式下过滤 chunk 和 final
              const filteredSteps = allSteps.filter(step => {
                if (step.type === 'chunk') return false;
                if (step.type === 'final' && hasChunk) return false;
                return true;
              });
              const sortedSteps = [...filteredSteps].sort((a, b) => {
                if (a.step && b.step) return a.step - b.step;
                return 0;
              });
              return sortedSteps.map((step, index) => (
                <StepRow key={`step-${index}`} step={step} taskId={message.task_id} stepIndex={index} expandedSteps={expandedSteps} toggleExpand={toggleExpand} />
              ));
            })()}
              
              {/* 【小新修复】在推理过程中显示"💭 思考中:"标签 */}
            {message.is_reasoning && (
              <span style={{ color: '#888', fontSize: '0.85em', marginRight: 4, fontWeight: 500 }}>
                💭 思考中:
              </span>
            )}

            {/* 【小查修复】4. AI回复chunk - 逐个渲染 */}
            {/* 【小新修复 2026-03-14】is_reasoning切换时自动添加换行 */}
            {/* 
             * 【重要】chunk 显示逻辑分两种情况：
             * 1. SSE实时模式（isStreaming=true）：逐个渲染chunk，message.content作为备用
             * 2. 历史模式（isStreaming=false）：逐个渲染chunk，数据不完整时用message.content补充
             * 【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
             */ }
            {(() => {
              const chunks = message.executionSteps?.filter(step => step.type === "chunk") || [];
              
              // 逐个渲染chunk
              return chunks.map((chunk, index) => {
                const is_reasoning = !!chunk.is_reasoning;
                // 过滤掉 AI 模型返回的特殊标签
                let content = (chunk.content || '').replace(/<\/?longcat_think>/g, '');
                
                // 【小新修复 2026-03-14】判断是否需要在前面加换行
                // 当 is_reasoning 从 true->false 或 false->true 切换时
                if (index > 0) {
                  const prevChunk = chunks[index - 1];
                  const prevIsReasoning = !!prevChunk.is_reasoning;
                  const prevContent = prevChunk.content || '';
                  
                  // 只有在切换时才处理
                  if (is_reasoning !== prevIsReasoning) {
                    // 检查前一个chunk是否以\n结尾
                    if (!prevContent.endsWith('\n')) {
                      // 在当前chunk前面加换行
                      content = '\n' + content;
                    }
                  }
                }
                
                return (
                  <span
                    key={`chunk-${index}`}
                    style={{
                      color: is_reasoning ? '#888' : '#000',
                      fontStyle: is_reasoning ? 'italic' : 'normal',
                      fontSize: is_reasoning ? '0.95em' : '1em',
                    }}
                  >
                    {content}
                  </span>
                );
              });
            })()}

            {/* 【小新修改 2026-03-18】在执行 content 回退前，先判断是否有 action_tool */}
            {/* 设计思路：
              * 1. 遍历 executionSteps，检查是否有 action_tool 类型的步骤
              * 2. 如果有 action_tool（hasAction=1），则不执行 content 回退
              * 3. 如果没有 action_tool（hasAction=0），则执行原来的 content 回退逻辑
              * 目的：区分 ReAct 模式（有 action_tool）和普通对话模式（无 action_tool）
              */}
            {(() => {
              // ==================== 步骤 1：计算 hasAction 变量 ====================
              // hasAction = 0：默认值，表示没有 action_tool
              // hasAction = 1：表示有 action_tool（ReAct 模式）
              let hasAction = 0;
              
              // 遍历 message.executionSteps 数组，检查每个 step 的 type
              for (const step of (message.executionSteps || [])) {
                // 如果当前 step 的类型是 action_tool（工具调用）
                if (step.type === 'action_tool') {
                  hasAction = 1;  // 标记为 ReAct 模式
                  break;  // 找到 action_tool 后立即停止遍历（不需要继续检查）
                }
                // 如果当前 step 的类型是 chunk（AI 回复内容片段）
                if (step.type === 'chunk') {
                  hasAction = 0;  // 标记为普通对话模式
                  // 不 break，继续遍历（后面可能还有 action_tool）
                }
              }
              
              // ==================== 步骤 2：根据 hasAction 判断是否执行 content 回退 ====================
              // 只有当 hasAction !== 1（即没有 action_tool）时，才执行 content 回退逻辑
              if (hasAction !== 1) {
                // ==================== 步骤 3：执行原来的 content 回退判断逻辑（原 974-986 行） ====================
                // 过滤出所有 type 为 chunk 的步骤
                const chunks = message.executionSteps?.filter(s => s.type === "chunk") || [];
                // 检查是否存在 is_reasoning=false 的 chunk（表示有非思考过程的内容）
                const hasFalseReasoning = chunks.some(c => c.is_reasoning === false);
                
                // 情况 A：SSE 实时模式（isStreaming=true）
                // 触发条件：只有当没有 chunk 时才显示 content（作为备用）
                if (message.isStreaming) {
                  return chunks.length === 0;
                }
                
                // 情况 B：历史消息模式（isStreaming=false）
                // 触发条件：当没有 is_reasoning=false 的 chunk 时，显示 content（补充不完整的 chunk 数据）
                return !hasFalseReasoning;
              }
              
              // 如果 hasAction === 1（有 action_tool），返回 false，不执行 content 回退
              return false;
            })() && (
              // ==================== 步骤 4：渲染 content 的 div（原 987-1017 行） ====================
              // 只有当上面的 IIFE 返回 true 时，才会渲染这个 div
              <div
                style={{
                  wordBreak: "break-word",
                  overflowWrap: "break-word",
                  paddingRight: 32,
                  // 【小沈修复】思考过程使用灰色斜体样式，与正式回答区分
                  ...(message.is_reasoning ? {
                    color: '#888',
                    fontStyle: 'italic',
                    fontSize: '0.95em',
                  } : {}),
                }}
                className={
                  message.content === "🤔 AI 正在思考..." && message.isStreaming
                    ? "thinking-message"
                    : message.isError
                    ? "error-message"
                    : message.is_reasoning
                    ? "reasoning-message"
                    : ""
                }
              >
                {/* 【小查修复】已移除回退显示"思考中"标签，统一用 chunk 渲染 */}
                {/* 显示 content 内容：将双换行符\n\n替换为单换行符\n */}
                {message.content && typeof message.content === 'string' 
                  ? message.content.replace(/\n\n/g, '\n')
                  : String(message.content || '').replace(/\n\n/g, '\n')}
                {(message.isStreaming ?? false) && (
                  <span className="thinking-cursor" style={{ marginLeft: 2 }}>▌</span>
                )}
              </div>
            )}
            
            {/* 【小新重构2026-03-13】使用独立ErrorDetail组件 */}
            {message.isError && (
              <ErrorDetail
                errorType={message.errorType}
                errorCode={message.errorCode}
                errorMessage={message.errorMessage}
                errorTimestamp={message.errorTimestamp}
                errorDetails={message.errorDetails}
                errorStack={message.errorStack}
                errorRetryable={message.errorRetryable}
                errorRetryAfter={message.errorRetryAfter}
                model={message.model}
                provider={message.provider}
              />
            )}
          </>

          {/* CSS 动画 */}
          {(message.content === "🤔 AI 正在思考..." && message.isStreaming) ||
          message.isError ||
          message.is_reasoning ? (
            <style>{`
              ${
                message.content === "🤔 AI 正在思考..." && message.isStreaming
                  ? `
                @keyframes thinking-pulse {
                  0%, 100% { opacity: 1; }
                  50% { opacity: 0.6; }
                }
                @keyframes cursor-spin {
                  0% { transform: rotate(0deg); }
                  100% { transform: rotate(360deg); }
                }
                .thinking-message {
                  animation: thinking-pulse 1.5s ease-in-out infinite;
                }
                .thinking-cursor {
                  display: inline-block;
                  animation: cursor-spin 1s linear infinite;
                  opacity: 0.7;
                }
                `
                  : ""
              }
              ${
                message.isError
                  ? `
                @keyframes error-fade-in {
                  from {
                    opacity: 0;
                    transform: translateY(-10px);
                  }
                  to {
                    opacity: 1;
                    transform: translateY(0);
                  }
                }
                .error-message {
                  animation: error-fade-in 0.3s ease-out;
              }
              `
                  : ""
              }
              ${
                message.is_reasoning
                  ? `
                .reasoning-message {
                  color: #888;
                  font-style: italic;
                }
              `
                  : ""
              }
            `}</style>
          ) : null}
        </div>
      </div>

      {/* 右侧头像（用户消息） */}
      {isUser && (
        <div style={{ flexShrink: 0, marginTop: 8 }}>{getAvatar()}</div>
      )}

      {/* CSS 样式 - 悬停显示复制按钮 */}
      <style>{`
        .copy-button {
          opacity: 0 !important;
        }
        div:hover .copy-button {
          opacity: 1 !important;
        }
      `}</style>
    </div>
  );
};

export default MessageItem;
