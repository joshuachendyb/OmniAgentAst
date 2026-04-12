/**
 * MessageListSkeleton 消息列表骨架屏组件
 * 
 * 功能：在消息列表加载完成前显示骨架屏
 * UI布局和视觉与现有消息列表保持完全一致
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-12
 */

import React from 'react';
import styles from './MessageListSkeleton.module.css';

/**
 * MessageListSkeletonProps
 */
interface MessageListSkeletonProps {
  /** 显示消息数量，默认4条 */
  count?: number;
}

/**
 * 生成骨架消息
 */
const generateSkeletonMessages = (count: number) => {
  const messages = [];
  for (let i = 0; i < count; i++) {
    const isUser = i % 2 === 0;
    messages.push(
      <div key={i} className={`${styles.skeletonMessageItem} ${isUser ? styles.skeletonUser : styles.skeletonAI}`}>
        <div className={styles.skeletonAvatar} />
        <div className={styles.skeletonContent}>
          {isUser ? (
            <div className={`${styles.skeletonLine} ${styles.skeletonLineShort}`} />
          ) : (
            <>
              <div className={`${styles.skeletonLine} ${styles.skeletonLineLong}`} />
              <div className={`${styles.skeletonLine} ${styles.skeletonLineMedium}`} />
            </>
          )}
        </div>
      </div>
    );
  }
  return messages;
};

/**
 * MessageListSkeleton 组件
 */
export const MessageListSkeleton: React.FC<MessageListSkeletonProps> = ({ count = 4 }) => {
  return <div className={styles.messageListSkeleton}>{generateSkeletonMessages(count)}</div>;
};

export default MessageListSkeleton;