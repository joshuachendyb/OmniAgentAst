/**
 * MessageArea 组件 - 消息展示区域
 * 
 * 功能：
 * - 消息列表容器（滚动区域）
 * - 骨架屏显示
 * - 空状态提示
 * - 整合MessageList组件
 * 
 * @author 小沈
 * @date 2026-04-21
 */

import React from 'react';
import { RobotOutlined } from '@ant-design/icons';
import { MessageListSkeleton } from '../Skeleton';
import MessageList from './MessageList';
import type { Message } from '../../types/chat';

interface MessageAreaProps {
  // 消息数据
  messages: Message[];
  showExecution: boolean;
  sessionId: string | null;
  sessionTitle: string;
  useStream: boolean;
  
  // 骨架屏状态
  isMessageListLoading: boolean;
  
  // 滚动控制 refs
  messagesEndRef: React.RefObject<HTMLDivElement>;
}

/**
 * MessageArea - 消息展示区域组件
 */
const MessageArea: React.FC<MessageAreaProps> = ({
  messages,
  showExecution,
  sessionId,
  sessionTitle,
  useStream,
  isMessageListLoading,
  messagesEndRef,
}) => {
  return (
    <div
      style={{
        height: 500,
        overflowY: 'auto',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        padding: '0 2px 2px 0',
        marginBottom: 0,
        backgroundColor: '#fafafa',
        position: 'relative',
      }}
    >
      {/* 空状态或骨架屏 */}
      {messages.length === 0 ? (
        isMessageListLoading ? (
          <MessageListSkeleton count={4} />
        ) : (
          <div style={{ textAlign: 'center', color: '#999', marginTop: 50 }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <p>开始与 AI 助手对话</p>
            <p style={{ fontSize: 12 }}>
              {useStream
                ? '流式模式已开启 - 可实时查看 AI 思考过程'
                : '普通模式 - 一次性返回完整回复'}
            </p>
          </div>
        )
      ) : (
        /* 消息列表 */
        <MessageList
          messages={messages}
          showExecution={showExecution}
          sessionId={sessionId}
          sessionTitle={sessionTitle}
          messagesEndRef={messagesEndRef}
        />
      )}
    </div>
  );
};

MessageArea.displayName = 'MessageArea';

export default MessageArea;