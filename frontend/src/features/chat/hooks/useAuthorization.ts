// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离授权弹窗逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: AU-02二次授权覆盖旧confirmId先confirm(false)防泄漏+裸as守卫 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 计时统一: 移除setTimeout后备, 倒计时由AuthorizationModal countdown统一管理(§5.7.4-⑥) — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 Bug修复(24项): ⑭pendingRef镜像+监听器一次注册[]消闭包窗口 ⑮确认失败不清空pending保留重试(改前 finally清空致后端挂起) ⑱/⑲旧请求覆盖前 await confirm(false) 回声防fire-and-forget ㉒parseTimeout合法0保留(Number||60吞0) ㉗auto_confirm严格判断防"false"误判bypass — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 D2-10: normalizeAutoConfirm四态归一，P2-1: 同confirmId重放去重不二次resolve，P0-1: catch中404清pending防僵死 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧/老杨 17.3: 404判定改读axios response.status+message（String(error)对axios得[object Object]无效） - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 P1修复: handleAuthorizationConfirm加15s超时兜底, HTTP挂起时强制clearTimeout+setAuthorizationPending(null)防弹窗永久滞留 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧/北京老陈: 弹窗立即消失+API后台fire-and-forget — 改前await API后才关窗致死等，改后立即关窗API后台发，后端必有返回解耦 - 小欧/北京老陈-2026-09-03
// 编辑历史: 2026-09-03 小欧/北京老陈: 前端错误提示 — 200+success False与网络/500均走公用handleError弹窗(WARNING)，改前仅console.error用户无感知 - 小欧/北京老陈-2026-09-03
// 编辑历史: 2026-09-03 小欧/北京老陈 BUG FIX: 同步写入pendingRef — React useEffect子先父后致auto-confirm读旧confirmId发旧ID到后端, 弹窗0秒不消失; 改前pendingRef在useEffect同步(父effect后执行), 改后handleAuthorizationRequired中同步写入 - 小欧/北京老陈-2026-09-03
import React, { useCallback, useEffect, useState } from 'react';
import { taskControlApi } from '../../../services/api/task.api';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';
import { handleError, ErrorType } from '@/services/error/handler';

// 2026-09-03 小欧 Bug-22: 计时解析 —— 合法 0(禁倒计时)保留, 仅 NaN/负数兜底 60(改前 Number||60 把 0 兜成 60)
const parseTimeout = (value: unknown): number => {
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : 60;
};

/**
 * 授权弹窗 hook：监听 authorization_required 事件、确认回调（含 HITL 信任事件派发）
 * 倒计时由 AuthorizationModal 组件内部 countdown 统一管理，本 hook 不再设 setTimeout
 */
export function useAuthorization(sessionId: string | null) {
  const [authorizationPending, setAuthorizationPending] =
    useState<AuthorizationRequest | null>(null);
  // 2026-09-03 小欧 Bug-14/18/19: pendingRef 镜像最新 pending, 监听器一次性注册([]), 闭包不再读旧快照;
  //   覆盖旧请求前 await 旧 confirm(false) 回声, 防 fire-and-forget / 中间请求泄漏
  const pendingRef = React.useRef<AuthorizationRequest | null>(null);
  React.useEffect(() => {
    pendingRef.current = authorizationPending;
  }, [authorizationPending]);

  // 【v3.4新增 2026-06-09 小沈】授权请求回调（从useChatCallbacks传递）
  useEffect(() => {
    const handleAuthorizationRequired = (
      event: CustomEvent<Record<string, unknown>>
    ) => {
      const rawData = event.detail;
      if (!rawData?.confirm_id || !rawData?.tool_name) return;
      const cur = pendingRef.current;
      // 2026-09-03 小欧 P2-1: 同confirmId重放去重，不二次resolve
      if (cur) {
        if (cur.confirmId === rawData.confirm_id) return;
        taskControlApi
          .confirm(cur.confirmId, false, false)
          .catch(() => undefined);
      }
      const newRequest: AuthorizationRequest = {
        confirmId: rawData.confirm_id as string,
        toolName: rawData.tool_name as string,
        params: (rawData.params ?? {}) as Record<string, unknown>,
        safetyLevel: (rawData.safety_level as string) ?? 'unknown',
        // 2026-09-03 小欧 D2-10: normalizeAutoConfirm四态归一(true/'true'/1/'1')
        autoConfirm:
          rawData.auto_confirm === true ||
          rawData.auto_confirm === 'true' ||
          rawData.auto_confirm === 1 ||
          rawData.auto_confirm === '1',
        // 2026-09-03 小欧 Bug-22: 合法 0(禁倒计时)不被 || 兜成 60; 仅 NaN/负数 兜 60
        trustPath:
          typeof rawData.trust_path === 'string'
            ? (rawData.trust_path as string)
            : null,
        confirmTimeout: parseTimeout(rawData.confirm_timeout),
        backendTimeout: parseTimeout(rawData.backend_timeout),
      };
      // 2026-09-03 小欧 北京老陈 BUG FIX: 同步写入pendingRef, 堵React useEffect子先父后致子auto-confirm读到旧confirmId
      //   根因: React effects执行顺序=子先父后, setAuthorizationPending→子effect先跑→读pendingRef→旧值→发旧ID
      pendingRef.current = newRequest;
      setAuthorizationPending(newRequest);
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
    // 2026-09-03 小欧 Bug-14: 依赖改 [] 一次性注册, 不再随 authorizationPending 重建监听器(消闭包窗口)
  }, []);

  // 【v3.4新增 2026-06-09 小沈】授权确认处理
  // 2026-09-03 小欧/北京老陈 Bug修复: 弹窗立即消失+API后台fire-and-forget
  //   改前: await API → setPending(null), API失败/卡住→弹窗永久滞留
  //   改后: setPending(null)立即关弹窗 → API后台发, 失败弹message提示
  const handleAuthorizationConfirm = useCallback(
    (confirmed: boolean, trustSession: boolean) => {
      const cur = pendingRef.current;
      if (!cur) {
        return;
      }
      // 立即关弹窗, 不等API
      setAuthorizationPending(null);
      // API后台fire-and-forget — 成功/200+success False/网络500均走公用错误弹窗
      taskControlApi
        .confirm(cur.confirmId, confirmed, trustSession)
        .then((res: unknown) => {
          const ok = (res as { success?: boolean })?.success !== false;
          if (!ok) {
            const err = (res as { error?: string })?.error ?? '确认失败';
            console.warn('[Authorization] 确认返回错误:', res);
            handleError({ message: `授权确认失败: ${err}`, error_type: ErrorType.WARNING });
            return;
          }
          if (trustSession && sessionId) {
            window.dispatchEvent(
              new CustomEvent('omni-trust-changed', { detail: { sessionId } })
            );
          }
        })
        .catch((error: unknown) => {
          console.error('[Authorization] 确认失败(fire-and-forget):', error);
          const msg = (error as { response?: { data?: { error?: string } }; message?: string })?.response?.data?.error ?? (error as { message?: string })?.message ?? String(error);
          handleError({ message: `授权确认异常: ${msg}`, error_type: ErrorType.WARNING });
        });
    },
    [sessionId]
  );

  return { authorizationPending, handleAuthorizationConfirm };
}
