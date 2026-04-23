/**
 * MessageItem组件 - 单条消息展示
 *
 * 功能：展示用户/AI/系统消息，支持头像、时间戳、复制功能
 * 委托给 UserMessageBubble 和 AIMessageBubble 组件渲染
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState, memo } from "react";
import { message as antMessage } from "antd";
import type { ExecutionStep } from "../../utils/sse";
import { exportMessage } from "../../utils/messageExporter";

// 【2026-04-21 优化3.2.1】从新拆分的StepRow目录导入
import UserMessageBubble from "./MessageItem/UserMessageBubble";
import AIMessageBubble from "./MessageItem/AIMessageBubble";

// 【小强 2026-04-12】Phase 2 P1级优化 - 导入自定义比较函数
import { messageItemCompare } from '../../hooks/useMessageItemProps';

/**
 * MessageItemProps 类型已移至 useMessageItemProps.ts 中导出，供外部使用
 */
export type { MessageItemProps } from '../../hooks/useMessageItemProps';

/**
 * 消息项组件
 *
 * 设计要点：
 * - 根据role选择渲染 UserMessageBubble 或 AIMessageBubble
 * - 用户消息：蓝色渐变，右侧对齐
 * - AI消息：白色卡片，左侧对齐，绿色边框
 * - 系统消息：浅黄色背景，居中
 *
 * @param message - 消息对象
 * @param showExecution - 是否显示执行过程
 */
/* eslint-disable react/prop-types */
// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装组件，减少不必要的重渲染
const MessageItem = memo(({
  message,
  showExecution: _showExecution = false,
  sessionId,
  sessionTitle,
}: {
  message: {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    isStreaming?: boolean;
    isError?: boolean;
    sendStatus?: 'sending' | 'sent' | 'failed';
    display_name?: string;
    model?: string;
    provider?: string;
    is_reasoning?: boolean;
    task_id?: string;
    errorType?: string;
    errorMessage?: string;
    errorRetryAfter?: number;
    errorTimestamp?: string;
    errorRecoverable?: boolean;
    errorContext?: {
      step?: number;
      model?: string;
      provider?: string;
      thought_content?: string;
    };
  };
  showExecution?: boolean;
  sessionId?: string | null;
  sessionTitle?: string | null;
}) => {
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

  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  // 根据角色选择渲染组件
  if (isSystem) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          marginBottom: 12,
          width: "100%",
        }}
      >
        <div
          style={{
            background: "#fffbe6",
            border: "1px solid #ffe58f",
            color: "#ad6800",
            padding: "8px 16px",
            borderRadius: "16px",
            maxWidth: "90%",
            whiteSpace: "nowrap",
            fontSize: 14,
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "flex-end",
          marginBottom: 12,
          gap: 4,
          width: "100%",
          paddingRight: 0,
        }}
      >
        {/* 用户消息气泡 */}
        <UserMessageBubble
          message={message}
          sessionId={sessionId}
          sessionTitle={sessionTitle}
        />

        {/* 用户头像 */}
        <div style={{ flexShrink: 0, marginTop: 6, marginLeft: 0 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: 14,
            fontWeight: 500,
          }}>
            我
          </div>
        </div>
      </div>
    );
  }

  // AI消息
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "flex-start",
        marginBottom: 12,
        gap: 4,
        width: "100%",
        paddingLeft: 0,
      }}
    >
      {/* AI头像 */}
      <div style={{ flexShrink: 0, marginTop: 6, marginRight: 0 }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #52c41a 0%, #73d13d 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: 14,
          fontWeight: 500,
        }}>
          AI
        </div>
      </div>

      <AIMessageBubble
        message={message}
        expandedSteps={expandedSteps}
        toggleExpand={toggleExpand}
        sessionId={sessionId}
        sessionTitle={sessionTitle}
      />
    </div>
  );
}, messageItemCompare);

// 【小强 2026-04-12】Phase 2 P1级优化：使用React.memo包装 + 自定义比较函数
// eslint-disable-next-line react/display-name
MessageItem.displayName = 'MessageItem';

export default MessageItem;