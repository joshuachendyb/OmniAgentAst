/**
 * MessageList组件 - 消息列表展示
 * 
 * 功能：
 * - 渲染对话历史消息（Dumb组件，纯展示）
 * - 结合 useMessageListRender Hook 实现高性能渲染
 * - 通过 props 接收滚动控制 refs，不自行管理
 * 
 * @author 小沈
 * @date 2026-04-21
 */

/* eslint-disable react/prop-types */
import React, { memo } from 'react';
import type { Message } from '../../types/chat';
import { useMessageListRender } from '../../hooks/useMessageListRender';

interface MessageListProps {
  // 核心数据
  messages: Message[];
  showExecution: boolean;
  sessionId: string | null;
  sessionTitle: string;
  
  // 滚动控制 refs（由NewChatContainer管理）
  messagesEndRef?: React.RefObject<HTMLDivElement>;
  userScrolledUpRef?: React.MutableRefObject<boolean>;
  
  // 滚动控制函数
  scrollToBottomIfNeeded?: () => void;
  scrollToBottomDelayed?: () => void;
  
  // 状态
  isReceiving?: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const MessageList: React.FC<MessageListProps> = memo(({
  messages,
  showExecution,
  sessionId,
  sessionTitle,
  messagesEndRef,
  // 预留扩展props（为后续优化准备）
  userScrolledUpRef: _userScrolledUpRef,
  scrollToBottomIfNeeded: _scrollToBottomIfNeeded,
  scrollToBottomDelayed: _scrollToBottomDelayed,
  isReceiving: _isReceiving,
}) => {
  // 使用高性能渲染 Hook
  const messageElements = useMessageListRender({
    messages,
    showExecution,
    sessionId,
    sessionTitle,
  });

  return (
    <div className="message-list-content" style={{ flex: 1, overflowY: 'auto', padding: '20px 0' }}>
      {messageElements}
      <div 
        ref={messagesEndRef as React.Ref<HTMLDivElement>} 
        style={{ float: 'left', clear: 'both' }} 
      />
    </div>
  );
});

MessageList.displayName = 'MessageList';

export default MessageList;