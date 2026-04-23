/**
 * AIMessageBubble组件 - AI消息气泡
 * 
 * 功能：
 * 1. AI消息气泡样式（白色卡片+绿色边框）
 * 2. 角色名称 + 时间戳
 * 3. 执行步骤显示（StepRow）
 * 4. 消息内容渲染
 * 5. 动态状态显示
 * 6. 复制/导出功能
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-23
 */

/* eslint-disable react/prop-types */
import React, { memo, useState, useMemo } from "react";
import { Tooltip, Button, message as antMessage } from "antd";
import {
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import StepRow from "../StepRow/index";
import MessageContent from "../MessageContent";
import RoleNameDisplay from "./RoleNameDisplay";
import { DynamicStatusDisplay } from "../../../utils/dynamicStatus";
import { formatTime, formatRelativeTime } from "../../../utils/timeFormatters";
import { exportMessage } from "../../../utils/messageExporter";
import type { MessageItemProps } from "../../../hooks/useMessageItemProps";

interface AIMessageBubbleProps {
  message: MessageItemProps["message"];
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
  sessionId?: string | null;
  sessionTitle?: string | null;
}

/**
 * AI消息气泡样式
 */
const getAIBubbleStyle = (isError?: boolean): React.CSSProperties => {
  const baseStyle: React.CSSProperties = {
    maxWidth: "100%",
    minWidth: "60px",
    width: "auto",
    paddingTop: 8,
    paddingBottom: 8,
    paddingLeft: 10,
    paddingRight: 30,
    borderRadius: "16px",
    position: "relative",
    transition: "all 0.3s ease",
    whiteSpace: "pre-wrap" as const,
    wordBreak: "normal" as const,
    overflowWrap: "break-word" as const,
  };

  // AI错误消息样式
  if (isError) {
    return {
      ...baseStyle,
      background: "#fff1f0",
      border: "1px solid #ffa39e",
      color: "#cf1322",
      boxShadow: "0 4px 12px rgba(255, 77, 79, 0.15)",
    };
  }

  // 正常AI消息样式
  return {
    ...baseStyle,
    background: "#fff",
    border: "1px solid #b7eb8f",
    color: "#262626",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
  };
};

/**
 * AIMessageBubble组件
 */
const AIMessageBubble: React.FC<AIMessageBubbleProps> = memo(({
  message,
  expandedSteps,
  toggleExpand,
  sessionId,
  sessionTitle,
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
   */
  const handleExport = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await exportMessage(message, { sessionId, sessionTitle });
    } catch (err) {
      antMessage.error("导出失败");
    }
  };

  // 处理执行步骤
  const stepData = useMemo(() => {
    const allSteps = message.executionSteps || [];
    const taskId = allSteps.find(s => s.type === 'start')?.task_id;
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
    
    return { taskId, sortedSteps };
  }, [message.executionSteps]);

  const bubbleStyle = getAIBubbleStyle(message.isError);

  return (
    <>
      {/* 消息内容区 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          maxWidth: "calc(100% - 50px)",
        }}
      >
        {/* 角色名称和时间戳 */}
        <div
          style={{
            marginBottom: 4,
            fontSize: 12,
            color: "#52c41a",
            fontWeight: 500,
            opacity: 0.85,
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexDirection: "row",
          }}
        >
          <span style={{ whiteSpace: "nowrap" }}>
            <RoleNameDisplay
              role={message.role}
              isStreaming={message.isStreaming}
              isError={message.isError}
              display_name={message.display_name}
              model={message.model}
            />
          </span>
          <span
            style={{
              fontSize: 11,
              color: "#999999",
              whiteSpace: "nowrap",
            }}
          >
            <Tooltip title={formatTime(message.timestamp)}>
              <span>{formatRelativeTime(message.timestamp)}</span>
            </Tooltip>
          </span>
        </div>

        {/* 消息气泡 */}
        <div style={{ ...bubbleStyle, position: "relative" }}>
          {/* 复制按钮 */}
          <Tooltip title={copied ? "已复制" : "复制"}>
            <Button
              className="copy-button"
              type="text"
              size="small"
              icon={
                copied ? (
                  <CheckOutlined style={{ color: "#52c41a" }} />
                ) : (
                  <CopyOutlined style={{ color: "#595959" }} />
                )
              }
              onClick={handleCopy}
              style={{
                position: "absolute",
                top: 4,
                right: 6,
                opacity: 1,
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
              icon={<DownloadOutlined style={{ color: "#595959" }} />}
              onClick={handleExport}
              style={{
                position: "absolute",
                top: 4,
                right: 30,
                opacity: 1,
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

          {/* 执行步骤 */}
          {stepData.sortedSteps.map((step, index) => (
            <StepRow 
              key={`step-${index}`} 
              step={step} 
              taskId={stepData.taskId} 
              stepIndex={index} 
              expandedSteps={expandedSteps} 
              toggleExpand={toggleExpand} 
            />
          ))}

          {/* 思考中标签 */}
          {message.is_reasoning && (
            <span style={{ color: '#888', fontSize: '0.85em', marginRight: 4, fontWeight: 500 }}>
              💭 思考中:
            </span>
          )}

          {/* 消息内容 */}
          <MessageContent message={message} isUser={false} isSystem={false} />

          {/* 动态状态显示 */}
          {message.isStreaming && (
            <DynamicStatusDisplay 
              executionSteps={message.executionSteps || []}
              isStreaming={message.isStreaming}
            />
          )}

          {/* CSS动画 */}
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
    </>
  );
});

AIMessageBubble.displayName = "AIMessageBubble";

export default AIMessageBubble;