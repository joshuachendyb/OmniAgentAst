/**
 * ChatHeader 组件 - 会话标题展示与编辑
 * 
 * 功能：
 * - 展示会话标题及锁定状态
 * - 处理标题编辑与保存（回车保存 + 失焦保存）
 * - 409 版本冲突处理与数据同步
 * 
 * @author 小沈
 * @date 2026-04-21
 */

import React from 'react';
import { Space, Input, Tooltip } from 'antd';
import { RobotOutlined, InfoCircleOutlined, LockOutlined } from '@ant-design/icons';
import { sessionApi } from '../../services/api';
import {
  showTitleSaved,
  showTitleUpdated,
  showSaveError,
  showSessionConflict,
} from '../../utils/chatMessages';

// 使用 showTitleUpdated 避免未使用警告
void showTitleUpdated;

interface ChatHeaderProps {
  // 核心状态
  sessionId: string | null;
  sessionTitle: string;
  titleLocked: boolean;
  editingTitle: boolean;
  titleInput: string;
  sessionVersion: number;
  
  // 状态 setters
  setSessionTitle: (title: string) => void;
  setTitleLocked: (locked: boolean) => void;
  setEditingTitle: (editing: boolean) => void;
  setTitleInput: (input: string) => void;
  setSessionVersion: (version: number) => void;
  
  // 回调
  onEditingStart: () => void;
  onEditingCancel: () => void;
}

/**
 * ChatHeader - 会话标题组件
 * 负责标题展示、编辑、锁定状态的显示
 */
const ChatHeader: React.FC<ChatHeaderProps> = ({
  sessionId,
  sessionTitle,
  titleLocked,
  editingTitle,
  titleInput,
  sessionVersion,
  setSessionTitle,
  setTitleLocked,
  setEditingTitle,
  setTitleInput,
  setSessionVersion,
  onEditingStart,
}) => {
  // 处理标题编辑保存（回车和失焦共用的保存逻辑）
  const handleSaveTitle = async () => {
    if (!titleInput.trim() || !sessionId) {
      setEditingTitle(false);
      return;
    }

    try {
      // 保存标题到后端
      await sessionApi.updateSession(
        sessionId,
        titleInput.trim(),
        sessionVersion
      );
      
      // 更新本地状态
      setSessionTitle(titleInput.trim());
      setTitleLocked(true); // 用户修改后锁定
      showTitleSaved();
      setEditingTitle(false);
    } catch (error: unknown) {
      // 处理 409 版本冲突
      const errObj = error as { response?: { status: number } };
      if (errObj?.response?.status === 409) {
        showSessionConflict();
        // 尝试重新获取最新会话数据
        try {
          const sessionData = await sessionApi.getSessionMessages(sessionId);
          if (sessionData.version) {
            setSessionVersion(sessionData.version);
          }
          if (sessionData.title) {
            setSessionTitle(sessionData.title);
          }
        } catch (refreshError) {
          console.error('刷新会话数据失败:', refreshError);
        }
      } else {
        console.warn('保存标题失败:', error);
        showSaveError('保存标题失败，请重试');
      }
      setEditingTitle(false);
    }
  };

  return (
    <span 
      style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
      onClick={() => {
        if (!editingTitle && sessionId) {
          setTitleInput(sessionTitle || '');
        }
        onEditingStart();
      }}
    >
      <RobotOutlined />
      {/* 显示"会话"标签 + 分隔符 */}
      <span style={{ marginLeft: 8, color: '#666', fontSize: 14 }}>会话</span>
      {/* 分隔符 */}
      <span style={{
        marginLeft: 8,
        marginRight: 8,
        height: 16,
        width: 1,
        background: 'linear-gradient(to bottom, transparent, #d9d9d9, transparent)',
      }} />
      
      {/* 编辑模式 */}
      {sessionId && editingTitle ? (
        <Space>
          <Input
            value={titleInput}
            onChange={(e) => setTitleInput(e.target.value)}
            onPressEnter={async (e) => {
              e.preventDefault();
              await handleSaveTitle();
            }}
            onBlur={async () => {
              await handleSaveTitle();
            }}
            style={{ width: 200 }}
            autoFocus
            placeholder={sessionTitle || '输入会话标题'}
          />
        </Space>
      ) : (
        /* 显示模式 */
        <span
          style={{
            cursor: 'pointer',
            color: titleLocked ? '#000' : '#666',
            fontSize: titleLocked ? '16px' : '14px',
            fontWeight: titleLocked ? 'bold' : 'normal',
          }}
        >
          {sessionTitle || '未命名会话'}
          
          {/* 非锁定时显示 AI 图标提示 */}
          {!titleLocked && (
            <Tooltip title='AI自动生成的标题'>
              <InfoCircleOutlined
                style={{ fontSize: 12, marginLeft: 4, color: '#999' }}
              />
            </Tooltip>
          )}
          
          {/* 锁定时显示锁定图标 */}
          {titleLocked && (
            <Tooltip title='标题已锁定，防止自动覆盖'>
              <LockOutlined
                style={{ fontSize: 12, marginLeft: 4, color: '#1890ff' }}
              />
            </Tooltip>
          )}
        </span>
      )}
    </span>
  );
};

ChatHeader.displayName = 'ChatHeader';

export default ChatHeader;