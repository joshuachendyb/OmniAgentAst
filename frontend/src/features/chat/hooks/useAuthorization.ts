// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离授权弹窗逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: AU-02二次授权覆盖旧confirmId先confirm(false)防泄漏+裸as守卫 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 计时统一: 移除setTimeout后备, 倒计时由AuthorizationModal countdown统一管理(§5.7.4-⑥) — 小欧-2026-09-03
import { useCallback, useEffect, useState } from 'react';
import { taskControlApi } from '../../../services/api/task.api';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';

/**
 * 授权弹窗 hook：监听 authorization_required 事件、确认回调（含 HITL 信任事件派发）
 * 倒计时由 AuthorizationModal 组件内部 countdown 统一管理，本 hook 不再设 setTimeout
 */
export function useAuthorization(sessionId: string | null) {
  const [authorizationPending, setAuthorizationPending] =
    useState<AuthorizationRequest | null>(null);

  // 【v3.4新增 2026-06-09 小沈】授权请求回调（从useChatCallbacks传递）
  useEffect(() => {
    const handleAuthorizationRequired = (
      event: CustomEvent<Record<string, unknown>>
    ) => {
      const rawData = event.detail;
      if (!rawData?.confirm_id || !rawData?.tool_name) return;
      if (authorizationPending) {
        taskControlApi
          .confirm(authorizationPending.confirmId, false, false)
          .catch(() => undefined);
      }
      setAuthorizationPending({
        confirmId: rawData.confirm_id as string,
        toolName: rawData.tool_name as string,
        params: (rawData.params ?? {}) as Record<string, unknown>,
        safetyLevel: (rawData.safety_level as string) ?? 'unknown',
        trustPath: (rawData.trust_path as string) ?? null,
        autoConfirm: Boolean(rawData.auto_confirm),
        confirmTimeout: Number(rawData.confirm_timeout) || 60,
        backendTimeout: Number(rawData.backend_timeout) || 60,
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
