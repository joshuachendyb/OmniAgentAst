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
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import ExecutionPanel from "./ExecutionPanel"; // 前端小新代修改：引入执行过程面板

const { Panel } = Collapse;

interface MessageItemProps {
  message: ChatMessage & {
    id: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;
    isStreaming?: boolean;
    isError?: boolean;
    displayName?: string; // 前端小新代修改：显示名称
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
  showExecution = false,
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
    // 调试日志：检查消息对象
     if (message.role === "assistant") {
       console.log("🔍 MessageItem.getRoleName - 消息对象:", {
         id: message.id,
         role: message.role,
         isStreaming: message.isStreaming,
         displayName: message.displayName,
         model: message.model,
         content: message.content?.substring?.(0, 50),
         // 检查所有属性
         allProps: Object.keys(message)
       });
     }
    
    switch (message.role) {
      case "user":
        return "我";
      case "assistant": {
        // ✅ 老杨 UX 建议：占位消息显示 loading 状态
        // 前端小新代修改：只要 isStreaming 为 true，就显示加载状态，并且显示 displayName
        if (message.isStreaming) {
          // 前端小新代修改：加载状态也显示 displayName（如果存在）
          // 如果 displayName 为空，尝试使用 model 构建
          let displayNameToShow = message.displayName;
          if (!displayNameToShow && message.model) {
            displayNameToShow = message.model;
            console.log("🔍 MessageItem.getRoleName - 从model构建displayName:", displayNameToShow);
          }
          
          const result = displayNameToShow
            ? `🤔 AI 助手【${displayNameToShow}】【加载中...】`
            : `🤔 AI 助手【加载中...】`;
          console.log("🔍 MessageItem.getRoleName - 流式状态，返回:", result);
          return result;
        }

        // 前端小新代修改 VIS-E02: 错误消息显示错误标识
        if (message.isError) {
          // ✅ 老杨 UX 建议：添加错误图标（⚠️）
          return message.displayName
            ? `⚠️ AI 助手【${message.displayName}】【错误】`
            : `⚠️ AI 助手【错误】`;
        }
        // 直接使用后端返回的 displayName，用【】包住显示
        const result = message.displayName
          ? `AI 助手【${message.displayName}】`
          : "AI 助手";
        console.log("🔍 MessageItem.getRoleName - 非流式状态，返回:", result);
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

        {/* 消息气泡 - 直接渲染，减少一层 div */}
        <div style={{ ...getMessageStyle(), position: "relative" }}>
            {/* 复制按钮（悬停显示）- 透明背景，小巧精致 */}
            <Tooltip title={copied ? "已复制" : "复制"}>
              <Button
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
                className="copy-button"
              />
            </Tooltip>

          {/* 消息内容 */}
          <div
            style={{
              wordBreak: "break-word",
              overflowWrap: "break-word",
              paddingRight: 32,
            }}
            className={
              message.content === "🤔 AI 正在思考..." && message.isStreaming
                ? "thinking-message"
                : message.isError
                ? "error-message"
                : ""
            }
          >
            {/* 执行过程展示（仅 AI 消息）- 优化：思考+执行在消息内容之前 */}
            {showExecution && message.role === "assistant" && message.executionSteps && message.executionSteps.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                {/* 思考步骤始终直接显示（不折叠）- 最先显示 */}
                {message.executionSteps
                  ?.filter((step) => step.type === "thought")
                  .map((step, index) => (
                    <ExecutionPanel
                      key={`thought-${index}`}
                      steps={[step]}
                      isActive={false}
                    />
                  ))}
                
                {/* 判断是否有执行步骤（action/observation） */}
                {(() => {
                  const hasExecution = message.executionSteps?.some(
                    (step) => step.type === "action" || step.type === "observation"
                  );
                  
                  return hasExecution ? (
                    // 有执行步骤：显示折叠区域
                    <Collapse
                      defaultActiveKey={
                        message.isStreaming ?? false ? ["execution"] : []
                      }
                      size="small"
                      style={{ marginBottom: 8 }}
                    >
                      <Panel
                        header={
                          <Space>
                            <ThunderboltOutlined />
                            <span>执行详情</span>
                            {(message.isStreaming ?? false) && <LoadingOutlined />}
                          </Space>
                        }
                        key="execution"
                      >
                        {/* 只渲染执行步骤（action + observation） */}
                        {message.executionSteps
                          ?.filter((step) => step.type === "action" || step.type === "observation")
                          .map((step, index) => (
                            <ExecutionPanel
                              key={index}
                              steps={[step]}
                              isActive={message.isStreaming || false}
                            />
                          ))}
                      </Panel>
                    </Collapse>
                  ) : null;
                })()}
              </div>
            )}

            {/* 消息内容 - 最后显示 */}
            {message.content && typeof message.content === 'string' 
              ? message.content 
              : String(message.content || '')}
            {(message.isStreaming ?? false) && (
              <span style={{ opacity: 0.5, marginLeft: 2 }}>▌</span>
            )}
          </div>

          {/* CSS 动画 */}
          {(message.content === "🤔 AI 正在思考..." && message.isStreaming) ||
          message.isError ? (
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
