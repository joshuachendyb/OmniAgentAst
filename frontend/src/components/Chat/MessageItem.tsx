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
  Tooltip,
  Button,
  message as antMessage,
} from "antd";
import {
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../../services/api";
import type { ExecutionStep } from "../../utils/sse";
import { formatTimestamp } from "../../utils/timestamp";
import { formatTime, formatRelativeTime } from "../../utils/timeFormatters";
import { DynamicStatusDisplay } from "../../utils/dynamicStatus";
import { exportMessage } from "../../utils/messageExporter";

// 【小强 2026-04-12】Phase 2 P1级优化 - 导入自定义比较函数
import { messageItemCompare } from '../../hooks/useMessageItemProps';

// 【2026-04-21 优化3.2.1】从新拆分的StepRow目录导入
import StepRow from "./StepRow/index";
import MessageContent from "./MessageContent";
import AvatarDisplay from "./MessageItem/AvatarDisplay";
import RoleNameDisplay from "./MessageItem/RoleNameDisplay";

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
    // 【小沈修复2026-04-23】P0-1: 添加发送状态
    sendStatus?: 'sending' | 'sent' | 'failed';
    display_name?: string; // 前端小新代修改：显示名称
    is_reasoning?: boolean; // 【小查修复】是否为思考过程（统一使用 snake_case）
    task_id?: string; // 【小新重构2026-03-09】任务ID，用于分页请求
    // 【小沈修改2026-04-16】error相关字段：删除details/stack/retryable，后端已删除
    errorType?: string;      // error_type
    // 【小沈修改2026-04-15】删除errorCode，统一使用errorMessage
    errorMessage?: string;  // error_message - 错误消息内容 【小沈修改2026-04-15】message → error_message
    errorRetryAfter?: number; // retry_after
    errorTimestamp?: string;  // timestamp
    // 【小沈添加2026-04-15】新增recoverable和context字段
    errorRecoverable?: boolean;
    errorContext?: {
      step?: number;
      model?: string;
      provider?: string;
      thought_content?: string;
    };
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
   * 调用 utils/messageExporter.ts 中的 exportMessage 函数
   */
  const handleExport = async (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log("🔍 [handleExport] 开始导出, message.id=", message.id);
    try {
      await exportMessage(message, { sessionId, sessionTitle });
    } catch (err) {
      console.error("🔍 [handleExport] 导出失败, error=", err);
      antMessage.error("导出失败");
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
          // 【小强优化2026-04-14】轻淡蓝色渐变方案B，更柔和
          background: "linear-gradient(135deg, #f0f5ff 0%, #adc6ff 100%)",
          color: "#262626",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          paddingRight: 30,
          border: "1px solid #d6e4ff",
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
        gap: 10,
        width: "100%",
      }}
    >
      {/* 左侧头像（仅AI消息） */}
      {!isUser && !isSystem && (
        <div style={{ flexShrink: 0, marginTop: 6 }}>
          <AvatarDisplay role={message.role} />
        </div>
      )}

      {/* 消息内容区 - 简化结构 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
          maxWidth: "calc(100% - 50px)",
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
              <RoleNameDisplay
                role={message.role}
                isStreaming={message.isStreaming}
                isError={message.isError}
                sendStatus={message.sendStatus}
                display_name={message.display_name}
                model={message.model}
              />
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
                <span>{formatRelativeTime(message.timestamp)}</span>
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

            {/* 【小新修复 2026-04-21】使用 MessageContent 组件渲染 chunk 和 content 回退 */}
            <MessageContent message={message} isUser={isUser} isSystem={isSystem} />

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

      {/* 右侧头像（仅用户消息） */}
      {isUser && (
        <div style={{ flexShrink: 0, marginTop: 6 }}>
          <AvatarDisplay role={message.role} />
        </div>
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
