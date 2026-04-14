/**
 * MessageItem组件 - 单条消息展示
 *
 * 功能：展示用户/AI/系统消息，支持头像、时间戳、复制功能
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState, memo } from "react";
import {
  Avatar,
  Tooltip,
  Button,
  message as antMessage,
} from "antd";
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import { formatTimestamp } from "../../utils/timestamp";
import { DynamicStatusDisplay } from "../../utils/dynamicStatus";
import { } from "../../utils/markdown";
import ErrorDetail from "./ErrorDetail";
import { 
  getStepStyle, 
  getStepTitleStyle,
  getStepContentStyle,
  getStepLabelStyle,
  getStepBadgeStyle,
  getTimestampStyle,
  getNextStepStyle,
  getStatusBadgeStyle,
  FontSize,
  FontWeight,
  Colors,
  type StepType 
} from "../../utils/stepStyles";

// 【小强实现 2026-03-24】阶段3：导入7个工具视图组件
import ListDirectoryView from "./views/ListDirectoryView";
import ReadFileView from "./views/ReadFileView";
import WriteFileView from "./views/WriteFileView";
import DeleteFileView from "./views/DeleteFileView";
import MoveFileView from "./views/MoveFileView";
import SearchFilesView from "./views/SearchFilesView";
import SearchFileContentView from "./views/SearchFileContentView";
import GenerateReportView from "./views/GenerateReportView";
import JsonHighlight from "./views/JsonHighlight";
// 【小强实现 2026-03-31】导入搜索工具数据转换函数
import { transformSearchFilesData, transformSearchFileContentData } from "../../utils/searchTransformers";

// 【小强 2026-04-12】Phase 2 P1级优化 - 导入自定义比较函数
import { messageItemCompare } from '../../hooks/useMessageItemProps';

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

const StepRow: React.FC<StepRowProps> = ({ step, taskId: _taskId, stepIndex = 0, expandedSteps, toggleExpand }) => {
  const [_isLoadingMore, _setIsLoadingMore] = useState(false);
  const [_showAllData, setShowAllData] = useState(false);  // 【小强新增 2026-04-03】前端分页控制

  // 【小资修复 2026-03-23】从全局Map读取展开状态（未设置的key默认展开）
  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  
  const labelMap: Record<string, string> = {
    start: "开始",
    thought: "思考",
    action_tool: "执行",
    observation: "观察",
    final: "完成",
    error: "错误",
    paused: "暂停",
    resumed: "恢复",
    interrupted: "中断",
    retrying: "重试",
    incident: "事件",  // incident默认标签
  };

  const iconMap: Record<string, string> = {
    start: "🚀",
    thought: "💭",
    action_tool: "⚙️",
    observation: "📋",
    final: "✅",
    error: "❌",
    paused: "⏸️",
    resumed: "▶️",
    interrupted: "⚠️",
    retrying: "🔄",
    incident: "⚡",  // incident默认图标
  };

  // 【小沈修复 2026-03-28】处理incident类型：优先使用incident_value，否则用type
  const effectiveType = step.type === 'incident' ? (step as any).incident_value || 'incident' : step.type;
  const label = labelMap[effectiveType] || labelMap[step.type] || "步骤";
  const icon = iconMap[effectiveType] || iconMap[step.type] || "";
  
  // 【小强优化 2026-03-18】步骤编号颜色随类型变化 - 使用stepStyles的函数
  const badgeStyle = getStepBadgeStyle(effectiveType as StepType);
  const labelStyle = getStepLabelStyle(effectiveType as StepType);

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

  // 【小强修改 2026-04-03】前端分页：后端返回全部数据，前端自己控制显示
  const handleLoadMore = () => {
    setShowAllData(true);  // 前端直接显示全部数据，不调用后端API
  };

  // 获取分页数据：前端切片
  const getPageData = () => {
    const rawData = step.raw_data as any;
    const allData = rawData?.matches || rawData?.entries || rawData?.results || [];
    const FRONTEND_PAGE_SIZE = 100;  // 前端每页显示100条
    
    if (_showAllData) {
      return { displayData: allData, hasMore: false };
    }
    
    if (allData.length > FRONTEND_PAGE_SIZE) {
      return { displayData: allData.slice(0, FRONTEND_PAGE_SIZE), hasMore: true };
    }
    
    return { displayData: allData, hasMore: false };
  };

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
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap" }}>
        {/* 【小强优化 2026-03-18】步骤编号徽章 */}
        {step.step && (
          <span style={badgeStyle}>
            步骤{step.step}
          </span>
        )}
        {/* 【小强优化 2026-03-18】标签带图标 */}
        <span style={labelStyle}>
          {icon} {label}：
        </span>
        <span style={{ flex: 1 }} />  {/* 弹性空间，将timestamp推到右侧 */}
        {/* timestamp放在行右侧，与右侧边框挨着，更醒目 */}
        {step.timestamp && (
          <span style={getTimestampStyle("action_tool")}>
            ⏰ {formatTimestamp(step.timestamp)}
          </span>
        )}
      </div>
      <div style={{ ...getContentStyle(), marginTop: 4, marginLeft: 0 }}>
        {step.type === "action_tool" && (
          <>
            {/* 显示工具名称 */}
            🔧 {step.tool_name || "执行中..."}
            {step.tool_params && (
              <div>
                {/* 默认显示1行 */}
                <div 
                  onClick={() => toggleExpand(stepIndex + 1000)} // +1000避免和文件列表折叠冲突
                  style={{ 
                    marginTop: 6, 
                    fontSize: 12, 
                    color: "#666",
                    background: "#e6f7ff", // action_tool的bg1颜色，保持一致性
                    padding: "8px 12px",
                    borderRadius: 6,
                    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                    lineHeight: 1.6,
                    whiteSpace: expandedSteps.get(stepIndex + 1000) ? "pre-wrap" : "nowrap",
                    overflow: "hidden",
                    textOverflow: expandedSteps.get(stepIndex + 1000) ? "clip" : "ellipsis",
                    cursor: "pointer",
                    maxHeight: expandedSteps.get(stepIndex + 1000) ? "none" : "36px",
                  }}
                >
                  <JsonHighlight data={step.tool_params} isExpanded={!!expandedSteps.get(stepIndex + 1000)} />
                  <span style={{ 
                    marginLeft: 8, 
                    color: "#1890ff", 
                    fontSize: 11,
                    fontWeight: 500,
                  }}>
                    {expandedSteps.get(stepIndex + 1000) ? "▲ 收起" : "▼ 展开"}
                  </span>
                </div>
              </div>
            )}
            {/* 【小强实现 2026-03-23】阶段4任务1：isRecursive判断逻辑 */}
            {(() => {
                return (
                  <div style={{ marginTop: 8 }}>
                    {/* 【小强修改 2026-03-24】折叠功能已移到 ListDirectoryView 内部，这里不再显示 */}
                     {/* 【小强实现 2026-03-24】阶段3：使用 renderToolResult 渲染工具结果视图 */}
                    {/* 【小沈修改 2026-03-24】传递 isExpanded 参数，让 ListDirectoryView 内部控制列表折叠 */}
                    {/* 【小强修改 2026-03-24】传递 toggleExpand 和 stepIndex，用于 list_directory 折叠按钮 */}
                    {renderToolResult(step, isExpanded, toggleExpand, stepIndex)}
                  </div>
               );
            })()}
            {/* 【小强修改 2026-04-03】前端分页：后端返回全部数据，前端自己控制显示 */}
            {/* 【小沈修复 2026-03-24】对于list_directory，总数由ListDirectoryView内部显示，避免重复 */}
            {step.raw_data && step.tool_name !== "list_directory" && (() => {
              const { hasMore } = getPageData();
              return hasMore && (
                <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
                  <span 
                    onClick={handleLoadMore}
                    style={{ 
                      cursor: "pointer", 
                      color: "#1890ff",
                      textDecoration: "underline",
                      fontWeight: 500,
                      transition: "all 0.2s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "#096dd9";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "#1890ff";
                    }}
                  >
                    加载更多
                  </span>
                </div>
              );
            })()}
            {/* 【小沈优化 2026-03-30】显示execution_status和summary - 使用徽章样式 */}
            {(step as any).execution_status && (
              <div style={{ marginTop: 6, fontSize: 12 }}>
                <span style={getStatusBadgeStyle((step as any).execution_status === "success" ? "success" : "error")}>
                  📊 状态：{(step as any).execution_status}
                </span>
                {(step as any).summary && (
                  <span style={{ color: "#666", marginLeft: 8 }}>
                    | 摘要：{(step as any).summary}
                  </span>
                )}
              </div>
            )}
          </>
        )}
        {step.type === "observation" && (
          <>
            {/* 【小资精简 2026-04-07】后端删除第二次LLM后，observation只显示content */}
            {/* 工具执行结果已在 action_tool 阶段完整显示，本阶段仅作轻量提示 */}
            {step.content && (
              <div style={{ 
                ...getStepStyle("observation" as StepType),
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}>
                {/* 【小沈新增 2026-04-07】显示工具名称，提升可读性 */}
                {step.tool_name && (
                  <div style={{ fontSize: "12px", color: "#666", marginBottom: "4px" }}>
                    🔧 工具：{step.tool_name}
                  </div>
                )}
                <span style={getStepContentStyle("observation" as StepType, "primary")}>
                  {step.content}
                </span>
              </div>
            )}
          </>
        )}
        {step.type === "start" && (
          <div style={getStepStyle("start" as StepType)}>
            {/* 【小强修复 2026-03-31】删除内容框内重复的标题行和时间戳，标题行已在StepRow外层显示 */}
            {/* 【小强修复 2026-03-31】恢复用户消息显示功能 */}
            <div style={getStepTitleStyle("start" as StepType)}>
              🚀 用户消息：{(step as any).user_message || "(无)"}
            </div>
            {/* 详细信息行：任务ID、安全检查 */}
            <div style={{ 
              ...getStepContentStyle("start" as StepType, "secondary"),
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 8,
            }}>
              <span style={{ marginRight: 16 }}>
                <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>任务ID：</span>
                <span style={getStepBadgeStyle("start")}>
                  {step.task_id || "无"}
                </span>
              </span>
              
              {step.security_check && (
                <span style={{ marginRight: 16 }}>
                  <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>安全：</span>
                  <span style={{ 
                    color: step.security_check.is_safe ? Colors.SUCCESS : Colors.ERROR,
                    fontWeight: FontWeight.BOLD,
                    backgroundColor: step.security_check.is_safe ? "rgba(82,196,26,0.1)" : "rgba(255,77,79,0.1)",
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: FontSize.SMALL,
                  }}>
                    {step.security_check.is_safe ? "✅ 通过" : "⚠️ 拦截"}
                  </span>
                  {!step.security_check.is_safe && step.security_check.risk && (
                    <span style={{ color: Colors.ERROR, marginLeft: 6, fontSize: FontSize.TERTIARY }}>
                      ({step.security_check.risk})
                    </span>
                  )}
                </span>
              )}
              
              <span style={{ flex: 1 }} />  {/* 弹性空间，将timestamp推到右侧 */}
              {/* timestamp已移到标题行右侧，此处不再显示 */}
            </div>
            
            {/* 【小强新增 2026-04-03】模型信息行：provider + model + display_name */}
            {(step as any).provider || (step as any).model || (step as any).display_name ? (
              <div style={{ 
                marginTop: 4,
                padding: '6px 10px',
                borderRadius: 6,
                background: 'rgba(24,144,255,0.06)',
                border: '1px solid rgba(24,144,255,0.15)',
                fontSize: FontSize.SMALL,
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
              }}>
                {(step as any).provider && (
                  <span>
                    <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>provider：</span>
                    <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).provider}</span>
                  </span>
                )}
                {(step as any).model && (
                  <span>
                    <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>model：</span>
                    <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).model}</span>
                  </span>
                )}
                {(step as any).display_name && (
                  <span>
                    <span style={{ color: Colors.TEXT.SECONDARY, fontWeight: FontWeight.MEDIUM }}>display_name：</span>
                    <span style={{ color: '#1890ff', fontWeight: FontWeight.MEDIUM }}>{(step as any).display_name}</span>
                  </span>
                )}
              </div>
            ) : null}
          </div>
        )}
        {step.type === "thought" && (
          <div style={{ 
            ...getStepStyle("thought" as StepType),
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}>
            {/* 【小强修复 2026-03-31】删除内容框内重复的标题行和时间戳，标题行已在StepRow外层显示 */}
            
            {/* LLM思考过程和推理过程 - 如果有的话 */}
            {(step as any).thought || (step as any).reasoning ? (
              <div style={{
                marginBottom: 10,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}>
                {/* 思考过程 - 橙色主题 */}
                {(step as any).thought && (
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, rgba(250,173,20,0.12) 0%, rgba(255,165,0,0.08) 100%)',
                    border: '1px solid rgba(255,170,0,0.25)',
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      marginBottom: 6,
                    }}>
                      <span style={{ fontSize: 14 }}>💭</span>
                      <span style={{ 
                        fontSize: 12, 
                        fontWeight: 600,
                        color: '#d97706',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                      }}>思考</span>
                    </div>
                    <div style={{
                      fontSize: 13,
                      color: '#92400e',
                      lineHeight: 1.5,
                    }}>
                      {(step as any).thought}
                    </div>
                  </div>
                )}
                
                {/* 推理过程 - 紫色主题 */}
                {(step as any).reasoning && (
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, rgba(139,92,246,0.1) 0%, rgba(167,139,250,0.06) 100%)',
                    border: '1px solid rgba(167,139,250,0.2)',
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      marginBottom: 6,
                    }}>
                      <span style={{ fontSize: 14 }}>🧠</span>
                      <span style={{ 
                        fontSize: 12, 
                        fontWeight: 600,
                        color: '#7c3aed',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                      }}>推理</span>
                    </div>
                    <div style={{
                      fontSize: 13,
                      color: '#6d28d9',
                      lineHeight: 1.5,
                    }}>
                      {(step as any).reasoning}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
            
            {/* 思考内容 - JSON前面的纯文本 */}
            <div>
              <span style={getStepContentStyle("thought" as StepType, "primary")}>
                {step.content || ""}
              </span>
            </div>
            
            {/* 信息区域：下一步、参数 */}
            <div style={{
              marginTop: 6,
              padding: '8px 12px',
              borderRadius: 6,
              background: 'linear-gradient(135deg, rgba(250,173,20,0.08) 0%, rgba(212,136,6,0.08) 100%)',
              border: '1px solid rgba(255,213,145,0.3)',
            }}>
              {/* 显示下一步tool_name */}
              {(step as any).tool_name && (
                <div style={getNextStepStyle("thought")}>
                  <span style={{ fontWeight: FontWeight.MEDIUM }}>⬇️ 下一步：{(step as any).tool_name}</span>
                </div>
              )}
              {/* 显示tool_params - 使用JsonHighlight组件统一格式 */}
              {(step as any).tool_params && Object.keys((step as any).tool_params).length > 0 && (
                <div style={{ 
                  marginTop: 4, 
                  fontSize: 12, 
                  background: "#fff7e6", // thought的bg1颜色，保持一致性
                  padding: "6px 10px",
                  borderRadius: 4,
                }}>
                  <JsonHighlight data={(step as any).tool_params} isExpanded={true} />
                </div>
              )}
            </div>
          </div>
        )}
        {step.type === "final" && (
          <div style={getStepStyle("final" as StepType)}>
            <span style={getStepContentStyle("final" as StepType, "primary")}>
              {step.content || ""}
            </span>
          </div>
        )}
        {step.type === "error" && (
          <ErrorDetail
            errorType={(step as any).error_type}
            errorMessage={step.error_message || (step as any).message}
            errorTimestamp={typeof step.timestamp === 'number' ? new Date(step.timestamp).toISOString() : String(step.timestamp)}
            errorDetails={(step as any).details}
            errorStack={(step as any).stack}
            errorRetryable={(step as any).retryable}
            errorRetryAfter={(step as any).retry_after}
            model={(step as any).model}
            provider={(step as any).provider}
          />
        )}
        {/* 【小沈修复 2026-03-28】后端type固定为'incident'，通过incident_value区分，需要同时处理新旧两种格式 */}
        {(step.type === "interrupted" || (step.type === "incident" && (step as any).incident_value === "interrupted")) && (
          <div style={getStepStyle("interrupted" as StepType)}>
            <span style={getStepContentStyle("interrupted" as StepType, "primary")}>
              {step.content || "客户端断开连接，任务中断"}
            </span>
          </div>
        )}
        {(step.type === "paused" || (step.type === "incident" && (step as any).incident_value === "paused")) && (
          <div style={getStepStyle("paused" as StepType)}>
            <span style={getStepContentStyle("paused" as StepType, "primary")}>
              {step.content || "任务已暂停，可恢复继续"}
            </span>
          </div>
        )}
        {(step.type === "resumed" || (step.type === "incident" && (step as any).incident_value === "resumed")) && (
          <div style={getStepStyle("resumed" as StepType)}>
            <span style={getStepContentStyle("resumed" as StepType, "primary")}>
              {step.content || "任务已恢复"}
            </span>
          </div>
        )}
        {(step.type === "retrying" || (step.type === "incident" && (step as any).incident_value === "retrying")) && (
          <div style={getStepStyle("retrying" as StepType)}>
            <span style={getStepContentStyle("retrying" as StepType, "primary")}>
              {step.content || "正在重试..."}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * 【小强实现 2026-03-24】阶段3：renderToolResult 分支函数
 * 根据 tool_name 渲染不同的工具结果视图组件
 * 【小沈修改 2026-03-24】添加 isExpanded 参数，让 ListDirectoryView 内部控制列表折叠
 * 【小强修改 2026-03-24】添加 toggleExpand 和 stepIndex 参数，用于 list_directory 折叠功能
 */
const renderToolResult = (step: ExecutionStep, isExpanded: boolean = true, toggleExpand?: (index: number) => void, stepIndex?: number) => {
  // 从 raw_data 中获取 data
  const data = (step as any).raw_data?.data || (step as any).raw_data;
  if (!data) return null;

  // 【小强修复 2026-03-24】处理可能的 undefined
  const handleToggle = toggleExpand && stepIndex !== undefined ? () => toggleExpand(stepIndex) : undefined;

  // 根据 tool_name 分支处理
  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryView data={data} toolParams={step.tool_params} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file":
      return <ReadFileView data={data} />;
    case "write_file":
      return <WriteFileView data={data} />;
    case "delete_file":
      return <DeleteFileView data={data} />;
    case "move_file":
      return <MoveFileView data={data} />;
    case "search_files": {
      // 【小强实现 2026-03-31】使用转换函数处理后端数据
      const transformedSearchFilesData = transformSearchFilesData(data);
      return <SearchFilesView data={transformedSearchFilesData} />;
    }
    case "search_file_content": {
      // 【小强实现 2026-03-31】使用转换函数处理后端数据
      const transformedSearchFileContentData = transformSearchFileContentData(data);
      return <SearchFileContentView data={transformedSearchFileContentData} />;
    }
    case "generate_report":
      return <GenerateReportView data={data} isExpanded={isExpanded} onToggle={handleToggle} />;
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

// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装组件，减少不必要的重渲染
// MessageItemProps 类型已移至 useMessageItemProps.ts 中导出，供外部使用
export interface MessageItemProps {
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
/* eslint-disable react/prop-types */
// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装组件，减少不必要的重渲染
// MessageItemProps 在 useMessageItemProps.ts 中导出使用
const MessageItem = memo(({
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
      
      // 检查是否包含incident类型的步骤（后端type固定为'incident'，通过incident_value区分具体类型）
      const hasIncident = hasSteps && message.executionSteps?.some(
        (step) => step.type === 'incident'
      );
      
      if (hasIncident) {
        // 【小沈修复2026-03-28】后端type固定为'incident'，通过incident_value区分具体类型
        exportData.incidentSteps = message.executionSteps?.filter(
          (step) => step.type === 'incident'
        ).map(step => ({
          type: (step as any).incident_value || 'incident',  // 使用incident_value作为type
          incident_value: (step as any).incident_value,
          message: step.content || (step as any).message,
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
              // 【小强修复 2026-04-14】添加thought和reasoning字段导出
              return { 
                ...baseExport, 
                step: step.step, 
                thought: step.thought || "",     // LLM思考过程
                reasoning: step.reasoning || "", // LLM推理过程
                tool_name: step.tool_name, 
                tool_params: step.tool_params 
              };
            case 'action_tool':
              return { ...baseExport, step: step.step, tool_name: step.tool_name, tool_params: step.tool_params, execution_status: step.execution_status, summary: step.summary, raw_data: step.raw_data, action_retry_count: step.action_retry_count };
            case 'observation':
              // 【小资精简 2026-04-07】后端删除第二次LLM调用后，observation只保留基础字段
              // 工具执行结果已在 action_tool 阶段完整显示
              return { ...baseExport, step: step.step, content: step.content };
            case 'chunk':
              return { ...baseExport, step: step.step, is_reasoning: step.is_reasoning };
            case 'final':
              // 【小强修复 2026-03-18】添加 step 字段
              return { 
                ...baseExport, 
                step: step.step,
                display_name: step.display_name,
                model: step.model,
                provider: step.provider
              };
            case 'error':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step, code: (step as any).code, error_type: (step as any).error_type, details: (step as any).details, stack: (step as any).stack, retryable: (step as any).retryable, retry_after: (step as any).retry_after, model: (step as any).model, provider: (step as any).provider };
            case 'interrupted':
            case 'paused':
            case 'resumed':
            case 'retrying':
              // 【小强修复 2026-03-18】添加 step 字段
              return { ...baseExport, step: step.step, incident_value: (step as any).incident_value || step.type, wait_time: (step as any).wait_time };
            case 'incident':
              // 【小沈修复 2026-03-28】后端type固定为'incident'，通过incident_value区分具体类型
              return { 
                ...baseExport, 
                step: step.step, 
                type: (step as any).incident_value || 'incident',  // 导出时还原为具体类型
                incident_value: (step as any).incident_value,
                message: step.content || (step as any).message,
                wait_time: (step as any).wait_time 
              };
            case 'start':
              // 【小强修复 2026-03-18】添加 step 字段
              return { 
                ...baseExport, 
                task_id: step.task_id, 
                step: step.step,
                security_check: step.security_check,
                user_message: step.user_message,
                display_name: step.display_name,
                model: step.model,
                provider: step.provider
              };
            default:
              return baseExport;
          }
        });
        filename = `execution_steps_${new Date().toLocaleString("zh-CN").replace(/[/:]/g, "-").replace(/ /g, "T")}.json`;
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
               // 【小强修复 2026-04-03】从 start 步骤获取 task_id（SSE 流式时保存在 executionSteps 中）
               const taskId = allSteps.find(s => s.type === 'start')?.task_id;
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
                <StepRow key={`step-${index}`} step={step} taskId={taskId} stepIndex={index} expandedSteps={expandedSteps} toggleExpand={toggleExpand} />
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

             {/* 【小新修改 2026-03-18】content 回退逻辑：当没有 chunk 时显示 message.content */}
             {/* 【小强修改 2026-04-03】跳过 "🤔 AI 正在思考..." 占位文本（已由 DynamicStatusDisplay 处理） */}
             {(() => {
               let hasAction = 0;
               for (const step of (message.executionSteps || [])) {
                 if (step.type === 'action_tool') {
                   hasAction = 1;
                   break;
                 }
                 if (step.type === 'chunk') {
                   hasAction = 0;
                 }
               }
               
               if (hasAction !== 1) {
                 const chunks = message.executionSteps?.filter(s => s.type === "chunk") || [];
                 const hasFalseReasoning = chunks.some(c => c.is_reasoning === false);
                 
                 const hasErrorStep = message.executionSteps?.some(step => {
                   const content = step.content || '';
                   return step.type === 'error' || 
                          content.includes('[错误]') || 
                          content.includes('429') || 
                          content.includes('限流');
                 });
                 
                 if (hasErrorStep) {
                   return false;
                 }
                 
                 if (message.isStreaming) {
                   // 【小强修改】跳过占位文本，由 DynamicStatusDisplay 处理
                   if (message.content === "🤔 AI 正在思考...") {
                     return false;
                   }
                   return chunks.length === 0;
                 }
                 
                 return !hasFalseReasoning;
               }
               
               return false;
              })() && (
               <div
                 style={{
                   wordBreak: "break-word",
                   overflowWrap: "break-word",
                   paddingRight: 32,
                 }}
               >
                 {message.content && typeof message.content === 'string' 
                   ? message.content.replace(/\n\n/g, '\n')
                   : String(message.content || '').replace(/\n\n/g, '\n')}
               </div>
             )}

            {/* 【小强新增 2026-04-03】动态状态提示：根据 step type 显示对应状态 */}
            {/* 只在 AI 助手消息的气泡底部显示，用户消息不显示 */}
            {!isUser && !isSystem && message.isStreaming && (
              <DynamicStatusDisplay 
                executionSteps={message.executionSteps || []}
                isStreaming={message.isStreaming}
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
}, messageItemCompare);

// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装 + 自定义比较函数
// eslint-disable-next-line react/display-name
MessageItem.displayName = 'MessageItem';

export default MessageItem;
