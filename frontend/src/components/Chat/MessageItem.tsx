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
  Collapse,
  Space,
} from "antd";
import {
  UserOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined,
  ThunderboltOutlined,
  LoadingOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import { taskControlApi } from "../../services/api";
import { formatTimestamp } from "../../utils/timestamp";
import { } from "../../utils/markdown";
import ErrorDetail from "./ErrorDetail";

/**
 * 步骤行组件 - 单行步骤显示（优化后新增）
 * 思考和执行分开渲染，用颜色区分类型
 * 【小新重构2026-03-09】添加分页支持
 */
const StepRow: React.FC<{ step: ExecutionStep; taskId?: string }> = ({ step, taskId }) => {
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  
  const colorMap: Record<string, string> = {
    thought: "#faad14",
    action_tool: "#1890ff",
    observation: "#52c41a",
    final: "#52c41a",
    error: "#cf1322",
    paused: "#fa8c16",
    resumed: "#52c41a",
    interrupted: "#cf1322",
    retrying: "#1890ff",
  };

  const labelMap: Record<string, string> = {
    thought: "思考",
    action_tool: "工具",
    observation: "结果",
    final: "答案",
    error: "错误",
    paused: "暂停",
    resumed: "恢复",
    interrupted: "中断",
    retrying: "重试",
  };

  const color = colorMap[step.type] || "#666";
  const label = labelMap[step.type] || "步骤";

  // 【小新重构2026-03-09】处理加载更多
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
    <div style={{ marginBottom: 4, marginRight: 30 }}>
      <span style={{ color, fontWeight: 500, marginRight: 8 }}>
        {label}：
      </span>
      <span style={{ color: "#333", wordBreak: "break-word" }}>
        {step.type === "action_tool" && (
          <>
            {step.action_description || step.tool_name || "执行中..."}
            {step.tool_params && (
              <span style={{ color: "#999", marginLeft: 8, fontSize: 12 }}>
              参数：{JSON.stringify(step.tool_params)}
              </span>
            )}
            {/* 【小新重构2026-03-09】显示分页信息 */}
            {step.raw_data && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
                {step.raw_data.total && (
                  <span style={{ marginRight: 12 }}>
                    共 {step.raw_data.total} 个项目
                  </span>
                )}
                {hasMore && (
                  <span 
                    onClick={handleLoadMore}
                    style={{ 
                      cursor: "pointer", 
                      color: isLoadingMore ? "#999" : "#1890ff",
                      textDecoration: "underline"
                    }}
                  >
                    {isLoadingMore ? "加载中..." : "加载更多"}
                  </span>
                )}
              </div>
            )}
          </>
        )}
        {step.type === "observation" && (
          <>
            {/* 显示 Agent 的思考过程 */}
            {step.thought && (
              <div style={{ color: "#888", fontStyle: "italic", marginBottom: 4, fontSize: "0.95em" }}>
                💭 {step.thought}
              </div>
            )}
            {/* 显示执行结果 */}
            {(() => {
              const obsResult = step.observation?.result;
              const hasEntries = obsResult?.entries && Array.isArray(obsResult.entries);
              
              return (
                <div>
                  {/* 文件列表框框 */}
                  {hasEntries && (
                    <div style={{ 
                      background: "#f5f5f5", 
                      borderRadius: 6, 
                      padding: "8px 12px", 
                      marginBottom: 8,
                      fontSize: "0.9em",
                      whiteSpace: "pre-wrap",
                      maxHeight: 300,
                      overflow: "auto"
                    }}>
                      {obsResult.entries.map((entry: any) => 
                        `${entry.type === "directory" ? "📁" : "📄"} ${entry.name}`
                      ).join("\n")}
                    </div>
                  )}
                  {/* summary 字符串 */}
                  {typeof step.result === "string" && (
                    <div>{step.result}</div>
                  )}
                </div>
              );
            })()}
          </>
        )}
        {step.type === "thought" && (
          <span style={{ 
            color: colorMap.thought,
            fontWeight: 500,
            padding: "4px 8px",
            borderRadius: 4,
            background: "#faad1415",
          }}>
            💭 {step.thinking_prompt || step.content || ""}
          </span>
        )}
        {step.type === "final" && (
          <span style={{ color: colorMap.final, fontWeight: 500 }}>
            ✅ {step.content || ""}
          </span>
        )}
        {step.type === "error" && (
          <span style={{ color: colorMap.error, fontWeight: 500 }}>
            ❌ 错误: {step.error_message || ""}
          </span>
        )}
      </span>
    </div>
  );
};

const { Panel } = Collapse;

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
}) => {
  const [copied, setCopied] = useState(false);

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
   * 8种type: start, thought, action_tool, observation, chunk, final, error, incident
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
        exportData.executionSteps = message.executionSteps;
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
              return { ...baseExport, step: step.step, obs_execution_status: (step as any).obs_execution_status, obs_summary: (step as any).obs_summary, obs_raw_data: (step as any).obs_raw_data, is_finished: step.is_finished };
            case 'chunk':
              return { ...baseExport, is_reasoning: step.is_reasoning };
            case 'final':
              return baseExport;
            case 'error':
              return { ...baseExport, code: (step as any).code, error_type: (step as any).error_type, details: (step as any).details, stack: (step as any).stack, retryable: (step as any).retryable, retry_after: (step as any).retry_after, model: (step as any).model, provider: (step as any).provider };
            case 'interrupted':
            case 'paused':
            case 'resumed':
            case 'retrying':
              return { ...baseExport, incident_value: (step as any).incident_value || step.type, wait_time: (step as any).wait_time };
            case 'start':
              return { ...baseExport, task_id: step.task_id };
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

  // 判断是否有执行步骤（action_tool/observation）
  const hasExecution = message.executionSteps?.some(
    step => step.type === "action_tool" || step.type === "observation"
  ) ?? false;

  // 【小查修复2026-03-10】判断是否有status类型步骤
  const hasStatus = message.executionSteps?.some(
    step => ["paused", "resumed", "interrupted", "retrying"].includes(step.type)
  ) ?? false;

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

          {/* 优化后的消息气泡结构 - 按照文档6.6.5节：按时间顺序线性渲染 */}
          <>
            {/* 1. 思考步骤 - 直接显示在最前面，不折叠 */}
            {message.executionSteps
              ?.filter(step => step.type === "thought")
              .map((step, index) => (
                <StepRow key={`thought-${index}`} step={step} taskId={message.task_id} />
              ))}

            {/* 【小新重构2026-03-09】按 action_tool 分组，每组一个折叠面板 */}
            {/* 【小查修复2026-03-10】兼容旧类型 action */}
            {hasExecution && message.role === "assistant" && (
              <div>
                {(() => {
                  const actionObservationSteps = message.executionSteps?.filter(
                    step => step.type === "action_tool" || step.type === "observation"
                  ) || [];
                  
                  // 将 action_tool 和后续的 observation 分组
                  const groups: ExecutionStep[][] = [];
                  let currentGroup: ExecutionStep[] = [];
                  
                  for (const step of actionObservationSteps) {
                    if (step.type === "action_tool") {
                      // 如果当前组有内容，先保存
                      if (currentGroup.length > 0) {
                        groups.push(currentGroup);
                      }
                      // 开始新组
                      currentGroup = [step];
                    } else if (step.type === "observation") {
                      // observation 加入当前组
                      currentGroup.push(step);
                    }
                  }
                  // 保存最后一个组
                  if (currentGroup.length > 0) {
                    groups.push(currentGroup);
                  }
                   
                  // 渲染每个组（折叠面板）
                  return groups.map((group, groupIndex) => {
                    return (
                    <Collapse
                      key={`execution-${groupIndex}-${group.length}`}
                      defaultActiveKey={
                        message.isStreaming ?? false ? [`execution-${groupIndex}`] : []
                      }
                      size="small"
                      style={{ marginBottom: 8 }}
                    >
                      <Panel
                        header={
                          <Space>
                            <ThunderboltOutlined />
                            <span>执行详情 {groupIndex + 1}</span>
                            {(message.isStreaming ?? false) && groupIndex === groups.length - 1 && <LoadingOutlined />}
                          </Space>
                        }
                        key={`execution-${groupIndex}`}
                      >
                        {group.map((step, stepIndex) => (
                          <StepRow key={stepIndex} step={step} taskId={message.task_id} />
                        ))}
                      </Panel>
                    </Collapse>
                    );
                  });
                })()}
              </div>
            )}

            {/* 【小查修复2026-03-10】渲染status类型步骤 */}
            {hasStatus && (
              <div style={{ marginBottom: 8 }}>
                {message.executionSteps
                  ?.filter(step => ["paused", "resumed", "interrupted", "retrying"].includes(step.type))
                  .map((step, index) => (
                    <StepRow key={`status-${index}`} step={step} taskId={message.task_id} />
                  ))}
              </div>
            )}

            {/* 【小新修复】在推理过程中显示"💭 思考中:"标签，推理完成后自动隐藏 */}
            {message.is_reasoning && (
              <span style={{ color: '#888', fontSize: '0.85em', marginRight: 4, fontWeight: 500 }}>
                💭 思考中:
              </span>
            )}

            {/* 【小查修复】4. AI回复chunk - 逐个渲染 */}
            {/* 【小新修复 2026-03-14】is_reasoning切换时自动添加换行 */}
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

            {/* 5. 最终答案content - 兼容历史消息不完整的情况 */}
            {(() => {
              const chunks = message.executionSteps?.filter(s => s.type === "chunk") || [];
              // 判断是否有 is_reasoning=false 的chunk
              const hasFalseReasoning = chunks.some(c => c.is_reasoning === false);
              
              // SSE实时（isStreaming=true）：按原来逻辑，只有没有chunk时才显示content
              if (message.isStreaming) {
                return chunks.length === 0;
              }
              
              // 历史消息：没有 is_reasoning=false 的chunk时，显示content（补充不完整的chunk）
              return !hasFalseReasoning;
            })() && (
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
                {/* 【小查修复】已移除回退显示"思考中"标签，统一用chunk渲染 */}
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
