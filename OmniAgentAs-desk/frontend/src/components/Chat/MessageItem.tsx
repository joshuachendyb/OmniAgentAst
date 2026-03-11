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
    <div style={{ marginBottom: 4 }}>
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
        {step.type === "thought" && (step.thinking_prompt || step.content || "")}
        {/* 【小查修复2026-03-10】添加status类型渲染 */}
        {["paused", "resumed", "interrupted", "retrying"].includes(step.type) && (
          <span style={{ 
            color: colorMap[step.type] || "#666", 
            fontWeight: 500,
            padding: "4px 8px",
            borderRadius: 4,
            background: `${colorMap[step.type] || "#666"}15`,
          }}>
            {labelMap[step.type] || "状态"}: {step.content || step.message || ""}
          </span>
        )}
        {step.type === "final" && (step.answer_content || "")}
        {step.type === "error" && (step.error_message || "")}
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
    isStreaming?: boolean;
    isError?: boolean;
    display_name?: string; // 前端小新代修改：显示名称
    is_reasoning?: boolean; // 【小沈修复】是否为思考过程
    task_id?: string; // 【小新重构2026-03-09】任务ID，用于分页请求
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
   * - 无执行步骤：导出TXT格式
   */
  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log("🔍 [handleExport] 开始导出, message.id=", message.id);
    try {
      const hasSteps = message.executionSteps && message.executionSteps.length > 0;
      console.log("🔍 [handleExport] hasSteps=", hasSteps, "executionSteps=", message.executionSteps);
      
      let blob: Blob;
      let filename: string;
      
      if (hasSteps) {
        // 有执行步骤：导出JSON格式
        const exportData = {
          timestamp: new Date().toLocaleString("zh-CN"),
          messageId: message.id,
          role: message.role,
          content: message.content,
          executionSteps: message.executionSteps,
        };
        const jsonStr = JSON.stringify(exportData, null, 2);
        blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
        filename = `execution_steps_${new Date().toISOString().replace(/[/:]/g, "-")}.json`;
      } else {
        // 无执行步骤：导出TXT格式
        const content = message.content || "";
        blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        filename = `message_${message.id}_${new Date().toLocaleString("zh-CN").replace(/[/:]/g, "-")}.txt`;
      }
      
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
        const result = message.display_name
          ? `AI 助手【${message.display_name}】`
          : "AI 助手";
        return result;
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
      padding: "8px 10px", // ✅ 用户建议：16px 20px → 8px 10px（减少 50%），更紧凑
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
        };
      case "assistant":
        return {
          ...baseStyle,
          background: "#fff",
          border: "1px solid #b7eb8f",
          color: "#262626",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
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

            {/* 【小新重构2026-03-09】2. 执行步骤 - 按 action_tool 分组，每组一个折叠面板 */}
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
                  
                  // 调试：打印原始步骤
                  console.log("🔍 分组原始步骤:", actionObservationSteps.map(s => ({ type: s.type, action_description: s.action_description })));
                  
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
                  
                  // 调试：打印分组结果
                  console.log("🔍 分组结果:", groups.length, "组", groups.map((g, i) => ({ 
                    groupIndex: i, 
                    steps: g.map(s => s.type) 
                  })));
                  
                  // 渲染每个组（折叠面板）
                  console.log("🔍 渲染折叠面板: groups.length =", groups.length);
                  return groups.map((group, groupIndex) => {
                    console.log("🔍 渲染第" + (groupIndex + 1) + "个折叠面板, 步骤数:", group.length);
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

            {/* 【小沈修复】4. AI回复chunk - 先分组相同类型的chunk，再分别显示 */}
            {(() => {
              const chunks = message.executionSteps?.filter(step => step.type === "chunk") || [];
              console.log("🔍 [MessageItem] chunks.length =", chunks.length, "chunks:", chunks.map(c => ({ is_reasoning: c.is_reasoning, content: (c.content || c.answer_content || '').slice(0, 20) })));
              
              // 分组：将连续相同类型的chunk合并
              const groupedChunks: { isReasoning: boolean; content: string }[] = [];
              for (const chunk of chunks) {
                const isReasoning = chunk.is_reasoning === true;
                const content = chunk.answer_content || chunk.content || '';
                if (groupedChunks.length > 0 && groupedChunks[groupedChunks.length - 1].isReasoning === isReasoning) {
                  // 相同类型，合并
                  groupedChunks[groupedChunks.length - 1].content += content;
                } else {
                  // 新类型，创建新组
                  groupedChunks.push({ isReasoning, content });
                }
              }
              
              // 渲染分组后的chunk
              return groupedChunks.map((group, index) => (
                <span
                  key={`chunk-group-${index}`}
                  style={{
                    // 思考过程：灰色斜体；正式内容：正常黑色
                    ...(group.isReasoning ? {
                      color: '#888',
                      fontStyle: 'italic',
                      fontSize: '0.95em',
                    } : {
                      color: '#000',
                    }),
                  }}
                >
                  {/* 只有第一组思考过程添加标签 */}
                  {group.isReasoning && index === 0 && (
                    <span style={{ 
                      color: '#888', 
                      fontSize: '0.85em', 
                      marginRight: 4,
                      fontWeight: 500,
                    }}>
                      💭 思考中:
                    </span>
                  )}
                  {group.content}
                </span>
              ));
            })()}
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
                .thinking-message {
                  animation: thinking-pulse 1.5s ease-in-out infinite;
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
