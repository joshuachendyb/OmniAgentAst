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
import StepHeader from "../StepRow/StepHeader";
import StepContent from "../StepRow/StepContent";
import StepFooter from "../StepRow/StepFooter";
import MessageContent from "../MessageContent";
import RoleNameDisplay from "./RoleNameDisplay";
import { DynamicStatusDisplay } from "../../../utils/dynamicStatus";
import { formatTime, formatRelativeTime } from "../../../utils/timeFormatters";
import { exportMessage } from "../../../utils/messageExporter";
import { getStepStyle, getStepBadgeStyle, getStepLabelStyle, isValidStepType } from "../../../utils/stepStyles";
import type { StepType } from "../../../utils/stepStyles";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "../constants/stepConstants";
import type { ExecutionStep } from "../../../utils/sse";
import type { MessageItemProps } from "../../../hooks/useMessageItemProps";

interface AIMessageBubbleProps {
  message: MessageItemProps["message"];
  expandedSteps: Map<number, boolean>;
  toggleExpand: (index: number) => void;
  sessionId?: string | null;
  sessionTitle?: string | null;
}

/**
 * AI消息气泡样式 - 留白优化版
 */
const getAIBubbleStyle = (isError?: boolean): React.CSSProperties => {
  const baseStyle: React.CSSProperties = {
    maxWidth: "100%",
    minWidth: "60px",
    width: "auto",
    padding: 0,  // 【修改】由内层getStepStyle控制留白
    borderRadius: "8px",  // 统一为内层Step圆角程度
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
                right: 34,
                zIndex: 10,
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
                right: 6,
                zIndex: 10,
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

          {/* 执行步骤 - 框层合并后直接使用子组件 */}
          {stepData.sortedSteps.map((step, index) => {
            // 处理incident类型
            const castStep = step as ExecutionStep;
            const stepType = castStep.incident_value || step.type;
            const effectiveType = step.type === 'incident' ? stepType : step.type;
            const label = STEP_LABEL_MAP[effectiveType] || STEP_LABEL_MAP[step.type] || "步骤";
            const icon = STEP_ICON_MAP[effectiveType] || STEP_ICON_MAP[step.type] || "";
            const badgeStyle = getStepBadgeStyle(effectiveType as StepType);
            const labelStyle = getStepLabelStyle(effectiveType as StepType);
            
            return (
              <div key={`step-${index}`} style={getStepStyle(effectiveType as StepType, true)}>
                <StepHeader 
                  step={step} 
                  badgeStyle={badgeStyle} 
                  labelStyle={labelStyle} 
                  label={label}
                  icon={icon}
                />
                <StepContent 
                  step={step} 
                  stepIndex={index} 
                  expandedSteps={expandedSteps} 
                  toggleExpand={toggleExpand}
                  contentStyle={{}}
                />
                <StepFooter step={step} />
              </div>
            );
          })}

          {/* 思考中标签 - 第四步添加呼吸渐变动画（增强版） */}
          {message.is_reasoning && (
            <>
              <style>{`
                @keyframes thinking-glow {
                  0%, 100% {
                    background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 50%, #fff7e6 100%);
                    box-shadow: 0 0 8px rgba(255, 215, 0, 0.3);
                    transform: scale(1);
                  }
                  50% {
                    background: linear-gradient(135deg, #ffe7ba 0%, #ffb347 50%, #ffe7ba 100%);
                    box-shadow: 0 0 16px rgba(255, 165, 0, 0.5);
                    transform: scale(1.05);
                  }
                }
                .thinking-badge {
                  animation: thinking-glow 1s ease-in-out infinite;
                  display: inline-flex;
                  align-items: center;
                  gap: 4px;
                  padding: 6px 12px;
                  border-radius: 8px;
                  font-size: 13px;
                  font-weight: 600;
                  color: #b45309;
                  margin-right: 8px;
                  border: 1px solid rgba(255, 165, 0, 0.3);
                }
                @keyframes thinking-dot {
                  0%, 100% { opacity: 0.3; }
                  50% { opacity: 1; }
                }
                .thinking-dot {
                  animation: thinking-dot 0.5s ease-in-out infinite;
                }
                .thinking-dot:nth-child(2) { animation-delay: 0.15s; }
                .thinking-dot:nth-child(3) { animation-delay: 0.3s; }
              `}</style>
              <span className="thinking-badge">
                💭 思考中<span className="thinking-dot">.</span><span className="thinking-dot">.</span><span className="thinking-dot">.</span>
              </span>
            </>
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