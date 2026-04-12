/**
 * useMessageListRender Hook - 消息列表渲染优化
 *
 * 功能：使用 useMemo 优化消息列表渲染，避免不必要的重渲染
 * 配合 MessageItem React.memo 实现双重优化
 *
 * Phase 2 P1级优化 - 消息列表useMemo优化
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import { useMemo, ReactNode } from 'react';
import { List } from 'antd';
import type { Message } from '../types/chat';
import MessageItem from '../components/Chat/MessageItem';

/**
 * Hook Props 类型定义
 */
interface UseMessageListRenderProps {
  messages: Message[];
  showExecution: boolean;
  sessionId: string | null;
  sessionTitle: string;
}

/**
 * 消息列表渲染 Hook
 * 
 * 使用 useMemo 缓存渲染结果，仅当依赖项变化时重新计算
 * 依赖项：messages, showExecution, sessionId, sessionTitle
 * 
 * @param messages - 消息数组
 * @param showExecution - 是否显示执行过程
 * @param sessionId - 会话ID
 * @param sessionTitle - 会话标题
 * @returns ReactNode[] - 渲染元素数组
 */
export const useMessageListRender = ({
  messages,
  showExecution,
  sessionId,
  sessionTitle,
}: UseMessageListRenderProps): ReactNode[] => {
  return useMemo(() => {
    const elements: ReactNode[] = [];
    let lastDate: string | null = null;

    for (let i = 0; i < messages.length; i++) {
      const item = messages[i];
      const currentDate = new Date(item.timestamp).toLocaleDateString('zh-CN');

      // 不同日期之间添加日期分隔符
      if (lastDate !== currentDate) {
        elements.push(
          <div
            key={`date-${i}`}
            style={{
              textAlign: 'center',
              margin: '1px 0',
              position: 'relative',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                right: 0,
                height: 1,
                backgroundColor: '#e8e8e8',
              }}
            />
            <span
              style={{
                background: '#fafafa',
                padding: '0 16px',
                color: '#999',
                fontSize: 12,
                position: 'relative',
                zIndex: 1,
              }}
            >
              {currentDate}
            </span>
          </div>
        );
        lastDate = currentDate;
      }

      elements.push(
        <List.Item
          key={item.id}
          style={{
            justifyContent:
              item.role === 'user' ? 'flex-end' : 'flex-start',
            border: 'none',
            padding: 0,
            width: '100%',
          }}
        >
          <MessageItem
            message={item}
            showExecution={showExecution}
            sessionId={sessionId}
            sessionTitle={sessionTitle}
          />
        </List.Item>
      );
    }

    return elements;
  }, [messages, showExecution, sessionId, sessionTitle]);
};

export default useMessageListRender;