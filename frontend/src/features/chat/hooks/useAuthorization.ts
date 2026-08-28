// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离授权弹窗逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useCallback, useEffect, useRef, useState } from 'react';
import { taskControlApi } from '../../../services/api/task.api';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';

/**
 * 授权弹窗 hook：监听 authorization_required 事件、60秒超时自动拒绝、确认回调（含 HITL 信任事件派发）
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useAuthorization(sessionId: string | null) {
  const [authorizationPending, setAuthorizationPending] =
    useState<AuthorizationRequest | null>(null);
  const authorizationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  // 【v3.4新增 2026-06-09 小沈】授权请求回调（从useChatCallbacks传递）
  useEffect(() => {
    const handleAuthorizationRequired = (
      event: CustomEvent<Record<string, unknown>>
    ) => {
      // 后端发送snake_case字段，前端AuthorizationModal使用camelCase
      const rawData = event.detail;
      setAuthorizationPending({
        confirmId: rawData.confirm_id as string,
        toolName: rawData.tool_name as string,
        params: (rawData.params ?? {}) as Record<string, unknown>,
        safetyLevel: rawData.safety_level as string,
      });
    };

    window.addEventListener(
      'authorization_required',
      handleAuthorizationRequired as EventListener
    );
    return () => {
      window.removeEventListener(
        'authorization_required',
        handleAuthorizationRequired as EventListener
      );
    };
  }, []);

  // 【v3.4新增 2026-06-09 小沈】授权超时自动关闭（60秒与后端一致）
  useEffect(() => {
    if (authorizationPending) {
      authorizationTimeoutRef.current = setTimeout(() => {
        // 2026-08-27 小欧 三堂会审: 授权超时自动拒绝改用 taskControlApi.confirm(false,false)
        taskControlApi
          .confirm(authorizationPending.confirmId, false, false)
          .catch(() => undefined);
        setAuthorizationPending(null);
      }, 60000);
    }
    return () => {
      if (authorizationTimeoutRef.current) {
        clearTimeout(authorizationTimeoutRef.current);
        authorizationTimeoutRef.current = null;
      }
    };
  }, [authorizationPending]);

  // 【v3.4新增 2026-06-09 小沈】授权确认处理
  const handleAuthorizationConfirm = useCallback(
    async (confirmed: boolean, trustSession: boolean) => {
      if (!authorizationPending) {
        return;
      }

      try {
        await taskControlApi.confirm(
          authorizationPending.confirmId,
          confirmed,
          trustSession
        );
        // 2026-08-27 小欧 三堂会审: HITL confirm(trust_session=True)写入成功后派发事件, 通知信任面板刷新
        if (trustSession && sessionId) {
          window.dispatchEvent(
            new CustomEvent('omni-trust-changed', { detail: { sessionId } })
          );
        }
      } catch (error) {
        console.error('[Authorization] 确认失败:', error);
      } finally {
        setAuthorizationPending(null);
      }
    },
    [authorizationPending, sessionId]
  );

  return { authorizationPending, handleAuthorizationConfirm };
}
