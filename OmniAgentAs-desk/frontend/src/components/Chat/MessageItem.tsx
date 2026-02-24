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
import { Avatar, Tooltip, Button, message as antMessage, Collapse, Space } from 'antd';
import { 
  UserOutlined, 
  RobotOutlined, 
  InfoCircleOutlined,
  CopyOutlined,
  CheckOutlined,
  ThunderboltOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import type { ChatMessage } from '../../services/api';
import type { ExecutionStep } from '../../utils/sse';
import ExecutionPanel from './ExecutionPanel';  // 前端小新代修改：引入执行过程面板

const { Panel } = Collapse;

interface MessageItemProps {
  message: ChatMessage & { 
    id: string; 
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;  // 模型名称
    isStreaming?: boolean;  // 前端小新代修改：是否正在流式生成
  };
  showExecution?: boolean;
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
  showExecution = false,
}) => {
  const [copied, setCopied] = useState(false);

  /**
   * 复制消息内容
   */
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      antMessage.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      antMessage.error('复制失败');
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
        return message.model ? `AI助手【${message.model}】` : 'AI助手';
      case 'system':
        return '系统';
      default:
        return '';
    }
  };

  /**
   * 获取消息样式 - 前端小新代修改 VIS-C01: 圆角优化, VIS-C02: padding优化, VIS-C03: 阴影优化
   */
  const getMessageStyle = () => {
    const baseStyle: React.CSSProperties = {
      maxWidth: '100%',
      minWidth: '60px',
      width: 'auto',
      padding: '16px 20px',
      borderRadius: '16px',
      position: 'relative',
      transition: 'all 0.3s ease',
      whiteSpace: 'pre-wrap',
      wordBreak: 'normal',
      overflowWrap: 'break-word',
    };

    switch (message.role) {
      case 'user':
        return {
          ...baseStyle,
          background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)',
          color: '#fff',
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        };
      case 'assistant':
        return {
          ...baseStyle,
          background: '#fff',
          border: '1px solid #b7eb8f',
          color: '#262626',
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
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
  const formatTime = (date: Date | string) => {
    try {
      // 确保转换为Date对象
      const dateObj = date instanceof Date ? date : new Date(date);
      
      // 检查是否有效日期
      if (isNaN(dateObj.getTime())) {
        return '刚刚';
      }
      
      return dateObj.toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch (error) {
      return '刚刚';
    }
  };

  /**
   * 格式化相对时间
   */
  const getRelativeTime = (date: Date | string) => {
    try {
      // 确保转换为Date对象
      const dateObj = date instanceof Date ? date : new Date(date);
      
      // 检查是否有效日期
      if (isNaN(dateObj.getTime())) {
        return '刚刚';
      }
      
      const now = new Date();
      const diff = now.getTime() - dateObj.getTime();
      const minutes = Math.floor(diff / 60000);
      
      if (minutes < 1) return '刚刚';
      if (minutes < 60) return `${minutes}分钟前`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}小时前`;
      return dateObj.toLocaleDateString('zh-CN');
    } catch (error) {
      return '刚刚';
    }
  };

  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isSystem ? 'center' : isUser ? 'flex-end' : 'flex-start',
        marginBottom: 24,
        padding: '0 8px',
        width: '100%',
        boxSizing: 'border-box' as const,
      }}
    >
      {/* 左侧头像（AI消息） */}
      {!isUser && !isSystem && (
        <div style={{ marginRight: 12, marginTop: 4, flexShrink: 0 }}>
          {getAvatar()}
        </div>
      )}

      {/* 消息内容区 - 自适应宽度，从头像旁开始 */}
      <div style={{ 
        flexGrow: 1,
        flexShrink: 1,
        minWidth: 0,
        maxWidth: 'calc(100% - 60px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
      }}>
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
            <div style={{ wordBreak: 'break-word', overflowWrap: 'break-word', paddingRight: 32 }}>
              {/* 前端小新代修改：在流式生成时添加光标提示，使用默认值false */}
              {message.content}
              {(message.isStreaming ?? false) && (
                <span style={{ opacity: 0.5, marginLeft: 2 }}>▌</span>
              )}
            </div>

             {/* 执行过程展示（仅AI消息）- 前端小新代修改 */}
             {showExecution && (
               <div style={{ marginTop: 12 }}>
                 <Collapse 
                   defaultActiveKey={(message.isStreaming ?? false) ? ['execution'] : []}  // 流式时默认展开
                   size="small"
                 >
                   <Panel 
                     header={
                       <Space>
                         <ThunderboltOutlined />
                         <span>AI思考过程</span>
                         {(message.isStreaming ?? false) && <LoadingOutlined />}
                       </Space>
                     } 
                     key="execution"
                   >
                     <ExecutionPanel 
                       steps={message.executionSteps || []} 
                       isActive={message.isStreaming || false} 
                     />
                   </Panel>
                 </Collapse>
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
