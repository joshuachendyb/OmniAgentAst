// 编辑历史: 2026-08-27 小欧 - 修复#12: 回车保存后Input卸载触发blur双发updateSession(409), 加editingRef守卫(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审H3修复: handleSaveTitle写后回填sessionApi.updateSession返回的version, 杜绝二次编辑必409冲突(409分支兜底保留)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 409恢复分支改用更轻的getSession(仅取version/title)
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

import React, { useRef } from 'react';
import { Space, Input, Tooltip } from 'antd';
import { RobotOutlined, InfoCircleOutlined, LockOutlined } from '@ant-design/icons';
import { sessionApi } from '../../services/api';
import {
  showTitleSaved,
  showSaveError,
  showSessionConflict,
} from '../../utils/chatMessages';

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
  onEditingCancel,
}) => {
  const savingRef = useRef(false); // 2026-08-27 小欧 修复#12: 防回车与失焦重复保存(双发409)的重入守卫
  // 处理标题编辑保存（回车和失焦共用的保存逻辑）
  const handleSaveTitle = async () => {
    if (savingRef.current) return; // 2026-08-27 小欧 修复#12: 重入守卫, 防回车与失焦双发
    if (!titleInput.trim() || !sessionId) {
      setEditingTitle(false);
      return;
    }
    savingRef.current = true;
    try {
      // 保存标题到后端
      const res = await sessionApi.updateSession(
        sessionId,
        titleInput.trim(),
        sessionVersion
      );
      // 2026-08-27 小欧 三堂会审H3: 写后回填version, 杜绝二次编辑必409冲突
      if (res && res.version) {
        setSessionVersion(res.version);
      }

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
          // 2026-08-27 小欧 三堂会审: 409恢复仅取version/title, 用更轻的getSession(无需messages)
          const sessionData = await sessionApi.getSession(sessionId);
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
    } finally {
      savingRef.current = false;
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
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                onEditingCancel(); // 2026-08-27 小欧 修复#11: 实现Esc取消编辑, 落地onEditingCancel接口能力(此前未接线)
              }
            }}
            onPressEnter={async (e) => {
              e.preventDefault();
              await handleSaveTitle();
            }}
            onBlur={async () => {
              if (savingRef.current) return; // 2026-08-27 小欧 修复#12: 回车保存进行中跳过失焦重复保存
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
            fontWeight: titleLocked ? 600 : 'normal',
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