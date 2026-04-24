/**
 * ChatFacadeTest - useChatFacade 验证测试组件
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import React, { useMemo, useCallback } from "react";
import { Spin } from "antd";
import { useChatFacade } from "../../hooks/chat/useChatFacade";
import type { Message } from "../../types/chat";

// 消息列表组件
const MessageList: React.FC<{
  messages: Message[];
  messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
}> = ({ messages, messagesEndRef }) => (
  <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
    {messages.map((msg, idx) => (
      <div
        key={idx}
        style={{
          marginBottom: "12px",
          padding: "8px 12px",
          borderRadius: "8px",
          background: msg.role === "user" ? "#e6f7ff" : "#f6ffed",
          marginLeft: msg.role === "user" ? "48px" : "0",
        }}
      >
        <div style={{ fontWeight: "bold", fontSize: "12px" }}>
          {msg.role === "user" ? "👤 用户" : "🤖 AI"}
        </div>
        <div>{msg.content}</div>
      </div>
    ))}
    <div ref={messagesEndRef} />
  </div>
);

// 输入框组件
const ChatInput: React.FC<{
  onSend: (content: string) => void;
  disabled: boolean;
}> = ({ onSend, disabled }) => {
  const [value, setValue] = React.useState("");

  const handleSend = () => {
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue("");
    }
  };

  return (
    <div style={{ padding: "12px", borderTop: "1px solid #ddd", display: "flex", gap: "8px" }}>
      <input
        style={{ flex: 1, padding: "8px 12px", borderRadius: "4px", border: "1px solid #d9d9d9" }}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSend()}
        placeholder="输入消息..."
        disabled={disabled}
      />
      <button
        style={{
          padding: "8px 16px",
          borderRadius: "4px",
          background: "#1890ff",
          color: "#fff",
          border: "none",
          cursor: disabled ? "not-allowed" : "pointer",
        }}
        onClick={handleSend}
        disabled={disabled}
      >
        发送
      </button>
    </div>
  );
};

// 流式状态显示
const StreamingStatus: React.FC<{
  isReceiving: boolean;
  isPaused: boolean;
  executionSteps: Array<{ type: string; content?: string }>;
  waitTime: number;
}> = ({ isReceiving, isPaused, executionSteps, waitTime }) => {
  if (!isReceiving && executionSteps.length === 0) return null;

  return (
    <div style={{ padding: "12px", background: "#f0f0f0", borderRadius: "4px", margin: "8px" }}>
      <div style={{ fontWeight: "bold", marginBottom: "8px" }}>📡 流式状态</div>
      <div>状态：{isReceiving ? "🔄 接收中" : isPaused ? "⏸️ 已暂停" : "✅ 完成"}</div>
      <div>等待时间：{waitTime}ms</div>
      <div>步骤数：{executionSteps.length}</div>
    </div>
  );
};

// 测试组件主体
const ChatFacadeTest: React.FC = () => {
  const chat = useChatFacade();
  const { session, message: msgState, streaming, ui, send, interrupt } = chat;

  // UI按需渲染
  const renderStreamingUI = useMemo(() => (
    <StreamingStatus
      isReceiving={streaming.isReceiving}
      isPaused={streaming.isPaused}
      executionSteps={streaming.executionSteps}
      waitTime={streaming.waitTime}
    />
  ), [streaming]);

  // 发送消息
  const handleSend = useCallback(async (content: string) => {
    try {
      await send.handleSend(content);
    } catch (err) {
      console.error("发送失败:", err);
    }
  }, [send]);

  // 中断任务
  const handleInterrupt = useCallback(async () => {
    try {
      await interrupt.handleTogglePause();
    } catch (err) {
      console.error("操作失败:", err);
    }
  }, [interrupt]);

  // 会话信息
  const sessionInfo = useMemo(() => {
    if (!session.sessionId) return null;
    return (
      <div style={{ padding: "8px 12px", background: "#f5f5f5", fontSize: "12px" }}>
        会话ID: {session.sessionId} | 标题: {session.sessionTitle || "(无标题)"}
      </div>
    );
  }, [session.sessionId, session.sessionTitle]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* 头部 */}
      <div style={{ padding: "12px", borderBottom: "1px solid #ddd", display: "flex", justifyContent: "space-between" }}>
        <div style={{ fontWeight: "bold", fontSize: "16px" }}>useChatFacade 测试</div>
        <div style={{ fontSize: "12px", color: "#666" }}>
          {streaming.isReceiving ? "🔄 接收中" : "✅ 空闲"}
        </div>
      </div>

      {/* 会话信息 */}
      {sessionInfo}

      {/* 流式状态 - 按需渲染 */}
      {renderStreamingUI}

      {/* 消息列表 */}
      <MessageList messages={msgState.messages} messagesEndRef={msgState.messagesEndRef} />

      {/* 控制按钮 - 按需渲染 */}
      {(streaming.isReceiving || streaming.isPaused) && (
        <div style={{ padding: "8px 12px", borderTop: "1px solid #ddd" }}>
          <button
            style={{
              padding: "8px 16px",
              borderRadius: "4px",
              background: "#ff4d4f",
              color: "#fff",
              border: "none",
            }}
            onClick={handleInterrupt}
          >
            {streaming.isPaused ? "▶️ 恢复" : "⏹️ 中断"}
          </button>
        </div>
      )}

      {/* 输入框 */}
      <ChatInput onSend={handleSend} disabled={msgState.loading || streaming.isReceiving} />

      {/* 加载状态 */}
      {msgState.loading && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>
          <Spin />
        </div>
      )}
    </div>
  );
};

export default ChatFacadeTest;