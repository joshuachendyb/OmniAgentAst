// 编辑历史: 2026-08-27 小欧 - 修复#12: 回车保存后Input卸载触发blur双发updateSession(409), 加editingRef守卫(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审H3修复: handleSaveTitle写后回填sessionApi.updateSession返回的version, 杜绝二次编辑必409冲突(409分支兜底保留)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 409恢复分支改用更轻的getSession(仅取version/title)
// 编辑历史: 2026-08-27 小欧 - 去头像-C1: 删ChatHeader内RobotOutlined代头像(顶栏"会话"标签), 仅留文字+渐变竖线锚点, 不扩至全局Layout
// 编辑历史: 2026-08-28 小欧 - ②A/a1: 标题字号统一14+500/400, 分割线渐变→solid #f0f0f0令牌化, 令牌化去跳动
// 编辑历史: 2026-08-28 小欧 - ②D/d1: 点击域收敛至标题段+Tooltip点击编辑, Input 200→min(280px,40vw)响应式, 去Space冗余
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
import { Input, Tooltip } from 'antd';
import { InfoCircleOutlined, LockOutlined } from '@ant-design/icons';
import { sessionApi } from '../../../services/api/session.api';
import { Colors } from '@/utils/stepStyles';
import {
  showTitleSaved,
  showSaveError,
  showSessionConflict,
} from '../../../utils/chatMessages';

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
  // 编辑历史: 2026-08-28 小欧 - 修复卸载触发blur双发: 保存成功后标记本次编辑已落库, 拦截Input卸载时的blur二度保存 - 小欧-2026-08-28
  const savedThisEditRef = useRef(false);
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
      savedThisEditRef.current = true; // 标记本次编辑已保存, 拦截卸载触发的blur双发
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
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      <span
        style={{ color: Colors.TEXT.PRIMARY, fontSize: 14, fontWeight: 500 }}
      >
        会话
      </span>
      <span
        style={{
          marginLeft: 8,
          marginRight: 8,
          height: 16,
          width: 1,
          background: Colors.BORDER.LIGHT,
        }}
      />
      {sessionId && editingTitle ? (
        <Input
          value={titleInput}
          onChange={(e) => setTitleInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              onEditingCancel();
            }
          }}
          onPressEnter={async (e) => {
            e.preventDefault();
            await handleSaveTitle();
          }}
          onBlur={async () => {
            if (savingRef.current || savedThisEditRef.current) {
              savedThisEditRef.current = false;
              return;
            }
            await handleSaveTitle();
          }}
          style={{ width: 'min(280px, 40vw)' }}
          autoFocus
          placeholder={sessionTitle || '输入会话标题'}
        />
      ) : (
        <Tooltip title={editingTitle ? '' : '点击编辑标题'}>
          <span
            style={{
              cursor: 'pointer',
              color: titleLocked ? Colors.TEXT.STRONG : Colors.TEXT.PRIMARY,
              fontSize: 14,
              fontWeight: titleLocked ? 500 : 400,
            }}
            onClick={(e) => {
              e.stopPropagation();
              if (sessionId) {
                setTitleInput(sessionTitle || '');
                onEditingStart();
              }
            }}
          >
            {sessionTitle || '未命名会话'}
            {!titleLocked ? (
              <Tooltip title="AI自动生成的标题">
                <InfoCircleOutlined
                  style={{
                    fontSize: 12,
                    marginLeft: 4,
                    color: Colors.TEXT.SECONDARY,
                  }}
                />
              </Tooltip>
            ) : (
              <Tooltip title="标题已锁定，防止自动覆盖">
                <LockOutlined
                  style={{ fontSize: 12, marginLeft: 4, color: Colors.PRIMARY }}
                />
              </Tooltip>
            )}
          </span>
        </Tooltip>
      )}
    </span>
  );
};

ChatHeader.displayName = 'ChatHeader';

export default ChatHeader;
