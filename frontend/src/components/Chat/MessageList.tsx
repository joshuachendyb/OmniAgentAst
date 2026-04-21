/**
 * MessageList组件 - 消息列表展示
 * 
 * 功能：
 * - 渲染对话历史消息
 * - 结合 useMessageListRender Hook 实现高性能渲染
 * - 自动滚动控制
 * 
 * @author 小强
 * @date 2026-04-21
 */

import React, { memo, useRef, useEffect } from 'react';
import type { Message } from '../../types/chat';
import { useMessageListRender } from '../../hooks/useMessageListRender';

interface MessageListProps {
  messages: Message[];
  showExecution: boolean;
  sessionId: string | null;
  sessionTitle: string;
  isReceiving?: boolean;
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  showExecution,
  sessionId,
  sessionTitle,
  isReceiving
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 使用高性能渲染 Hook
  const messageElements = useMessageListRender({
    messages,
    showExecution,
    sessionId,
    sessionTitle,
  });

  // 收到新消息或正在接收时自动滚动到底部
  useEffect(() => {
    if (messages.length > 0 || isReceiving) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, isReceiving]);

  return (
    <div className="message-list-content" style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
      {messageElements}
      <div ref={messagesEndRef} style={{ float: 'left', clear: 'both' }} />
    </div>
  );
};

// 使用 memo 避免父组件（NewChatContainer）输入框重渲染导致的无效更新
export default memo(MessageList);
