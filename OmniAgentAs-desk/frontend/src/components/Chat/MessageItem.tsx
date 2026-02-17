/**
 * MessageItem组件 - 单条消息展示
 * 
 * 功能：展示用户/AI/系统消息，支持头像、时间戳、复制功能
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState } from 'react';
import { Avatar, Typography, Tooltip, Button, message } from 'antd';
import { 
  UserOutlined, 
  RobotOutlined, 
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined
} from '@ant-design/icons';
import type { ChatMessage } from '../../services/api';

const { Text } = Typography;

interface MessageItemProps {
  message: ChatMessage & { 
    id: string; 
    timestamp: Date;
    executionSteps?: ExecutionStep[];
  };
  showExecution?: boolean;
}

interface ExecutionStep {
  type: 'thought' | 'action' | 'observation' | 'final';
  content?: string;
  tool?: string;
  params?: Record<string, any>;
  result?: any;
  timestamp: number;
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
const MessageItem: React.FC<MessageItemProps> = ({ 
  message, 
  showExecution = false 
}) => {
  const [copied, setCopied] = useState(false);

  /**
   * 复制消息内容
   */
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      message.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      message.error('复制失败');
    }
  };

  /**
   * 获取角色图标
   */
  const getAvatar = () => {
    switch (message.role) {
      case 'user':
        return (
          <Avatar 
            size={36} 
            icon={<UserOutlined />} 
            style={{ background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)' }}
          />
        );
      case 'assistant':
        return (
          <Avatar 
            size={36} 
            icon={<RobotOutlined />} 
            style={{ background: 'linear-gradient(135deg, #52c41a 0%, #389e0d 100%)' }}
          />
        );
      case 'system':
        return (
          <Avatar 
            size={36} 
            icon={<InfoCircleOutlined />} 
            style={{ background: '#faad14' }}
          />
        );
      default:
        return null;
    }
  };

  /**
   * 获取角色名称
   */
  const getRoleName = () => {
    switch (message.role) {
      case 'user':
        return '我';
      case 'assistant':
        return 'AI助手';
      case 'system':
        return '系统';
      default:
        return '';
    }
  };

  /**
   * 获取消息样式
   */
  const getMessageStyle = () => {
    const baseStyle: React.CSSProperties = {
      maxWidth: '75%',
      padding: '12px 16px',
      borderRadius: '12px',
      position: 'relative',
      transition: 'all 0.3s ease',
    };

    switch (message.role) {
      case 'user':
        return {
          ...baseStyle,
          background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)',
          color: '#fff',
          borderRadius: '12px 12px 2px 12px',
          boxShadow: '0 2px 8px rgba(24,144,255,0.3)',
        };
      case 'assistant':
        return {
          ...baseStyle,
          background: '#fff',
          border: '1px solid #b7eb8f',
          color: '#262626',
          borderRadius: '12px 12px 12px 2px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        };
      case 'system':
        return {
          ...baseStyle,
          background: '#fffbe6',
          border: '1px solid #ffe58f',
          color: '#ad6800',
          maxWidth: '90%',
          textAlign: 'center' as const,
        };
      default:
        return baseStyle;
    }
  };

  /**
   * 格式化时间戳
   */
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  /**
   * 格式化相对时间
   */
  const getRelativeTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    return date.toLocaleDateString('zh-CN');
  };

  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isSystem ? 'center' : isUser ? 'flex-end' : 'flex-start',
        marginBottom: 16,
        padding: '0 8px',
      }}
    >
      {/* 左侧头像（AI消息） */}
      {!isUser && !isSystem && (
        <div style={{ marginRight: 12, marginTop: 4 }}>
          {getAvatar()}
        </div>
      )}

      {/* 消息内容区 */}
      <div style={{ maxWidth: '80%' }}>
        {/* 角色名称 */}
        {!isSystem && (
          <div
            style={{
              marginBottom: 4,
              fontSize: 12,
              color: isUser ? '#1890ff' : '#52c41a',
              fontWeight: 500,
              textAlign: isUser ? 'right' : 'left',
              padding: '0 4px',
            }}
          >
            {getRoleName()}
          </div>
        )}

        {/* 消息气泡 */}
        <div style={{ position: 'relative' }}>
          <div style={getMessageStyle()}>
            {/* 复制按钮（悬停显示） */}
            <Tooltip title={copied ? '已复制' : '复制'}>
              <Button
                type="text"
                size="small"
                icon={copied ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />}
                onClick={handleCopy}
                style={{
                  position: 'absolute',
                  top: 4,
                  right: 4,
                  opacity: 0,
                  transition: 'opacity 0.2s',
                }}
                className="copy-button"
              />
            </Tooltip>

            {/* 消息内容 */}
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {message.content}
            </div>

            {/* 执行过程展示（仅AI消息） */}
            {showExecution && message.executionSteps && message.executionSteps.length > 0 && (
              <div
                style={{
                  marginTop: 12,
                  padding: 12,
                  background: 'rgba(0,0,0,0.02)',
                  borderRadius: 8,
                  borderLeft: '3px solid #52c41a',
                }}
              >
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                  🤔 执行过程（{message.executionSteps.length}步）
                </Text>
                {message.executionSteps.map((step, idx) => (
                  <div key={idx} style={{ marginBottom: 8, fontSize: 13 }}>
                    {step.type === 'thought' && (
                      <div style={{ color: '#666', fontStyle: 'italic' }}>
                        🧠 {step.content}
                      </div>
                    )}
                    {step.type === 'action' && (
                      <div>
                        <span style={{ color: '#1890ff' }}>🔧 {step.tool}</span>
                        <pre style={{ margin: '4px 0', fontSize: 11, background: '#f5f5f5', padding: 4 }}>
                          {JSON.stringify(step.params, null, 2)}
                        </pre>
                        {step.result && (
                          <div style={{ color: '#52c41a', fontSize: 12 }}>
                            ↳ {step.result}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 时间戳 */}
          <div
            style={{
              marginTop: 4,
              fontSize: 11,
              color: '#bfbfbf',
              textAlign: isUser ? 'right' : 'left',
              padding: '0 4px',
            }}
          >
            <Tooltip title={formatTime(message.timestamp)}>
              <span>{getRelativeTime(message.timestamp)}</span>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* 右侧头像（用户消息） */}
      {isUser && (
        <div style={{ marginLeft: 12, marginTop: 4 }}>
          {getAvatar()}
        </div>
      )}

      {/* CSS样式 - 悬停显示复制按钮 */}
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
};

export default MessageItem;
