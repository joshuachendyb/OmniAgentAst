// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离授权弹窗逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: AU-02二次授权覆盖旧confirmId先confirm(false)防泄漏+裸as守卫 - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 计时统一: 移除setTimeout后备, 倒计时由AuthorizationModal countdown统一管理 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - Bug修复(24项): ⑭pendingRef镜像+监听器一次注册[]消闭包窗口 ⑮确认失败不清空pending保留重试(改前 finally清空致后端挂起) ⑱/⑲旧请求覆盖前 await confirm(false) 回声防fire-and-forget ㉒parseTimeout合法0保留(Number||60吞0) ㉗auto_confirm严格判断防"false"误判bypass - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - normalizeAutoConfirm四态归一；同confirmId重放去重不二次resolve；catch中404清pending防僵死 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 17.3: 404判定改读axios response.status+message（String(error)对axios得[object Object]无效） - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 修复: handleAuthorizationConfirm加15s超时兜底, HTTP挂起时强制clearTimeout+setAuthorizationPending(null)防弹窗永久滞留 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 弹窗立即消失+API后台fire-and-forget: 改前await API后才关窗致死等，改后立即关窗API后台发，后端必有返回解耦 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 前端错误提示: 200+success False与网络/500均走公用handleError弹窗(WARNING)，改前仅console.error用户无感知 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - BUG FIX: 同步写入pendingRef — React useEffect子先父后致auto-confirm读旧confirmId发旧ID到后端, 弹窗0秒不消失; 改前pendingRef在useEffect同步(父effect后执行), 改后handleAuthorizationRequired中同步写入 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 根因修复: handleAuthorizationConfirm加confirmId参数, 优先用参数(弹窗直接传入), fallback用pendingRef(兜底); 堵ref时序竞态致旧弹窗auto-confirm发旧ID - 小欧-2026-09-03
// 编辑历史: 2026-09-06 小欧 - B1「已放行」短时高亮: 确认成功(confirmed=true)暂存 recentConfirmedTool(state)+recentTimerRef(2s自动清除, 卸载清timer), 返回扩展 recentConfirmedTool —— 小欧-2026-09-06
// 编辑历史: 2026-09-18 小欧 - 设计稿实施: 组装 AuthorizationRequest 新增 content 字段(弹窗原因, 后端 ConfirmSpec.content 透传) — 小欧-2026-09-18
// 编辑历史: 2026-09-19 小欧 - confirm_id已失效静默处理: 后端超时清理/重复confirm返回"not found/already processed"时仅log不弹toast(良性竞态) — 北京老陈驱动
// 编辑历史: 2026-09-19 小欧 - P-005契约化(北京老陈批准): confirm_id失效判定改读后端稳定code字段confirm_stale(替代4关键词字符串includes匹配, 消除"后端message变更即前端失效"脆弱链) — 小欧-2026-09-19
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.15: HITL 单源化——71行 window 双监听 effect 换 Store.pendingAuthorization
//   快照订阅(useChatStreamSession); 同confirmId去重/覆盖旧请求先confirm(false)/auto_confirm四态/parseTimeout
//   全保留; Store 置空即关弹窗(S1 放行链路); 用户 confirm/cancel 补 acknowledgeAuthorization 防重弹 — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 01:05:17 小欧 - 删本文件内"二次授权覆盖旧 confirmId 先 confirm(false)"分支(原 :69-72),
//   该职责下沉到 Store 唯一 owner: chatStreamTransport.ts onAuthorizationRequired(覆写发生处)。
//   根因(BUG-14 真实退化, 非风格改动): 同一 SSE 流内连发两帧 paused 时 Store 同批 commit,
//   React 只渲染末帧 → effect 里的 pendingRef 镜像拿不到中间帧, 中间 confirm_id 从未
//   confirm(false), 静默泄漏到后端等自身超时(正是 2026-09-02 ⑭ 要防的);
//   保留在此还会与 Store 重复发起 confirm(false)(DRY/SRP: 单一 owner) — 小欧-2026-09-30 01:05:17
import React, { useCallback, useEffect, useState } from 'react';
import { taskControlApi } from '../../../services/api/task.api';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';
import { handleError, ErrorType } from '@/services/error/handler';
import { useChatStreamSession } from '@/features/chat/streams/useChatStreamSession';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';

// 2026-09-03 小欧 修复: 计时解析 —— 合法 0(禁倒计时)保留, 仅 NaN/负数兜底 60(改前 Number||60 把 0 兜成 60)
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
  // 2026-09-03 小欧 修复: pendingRef 镜像最新 pending, 监听器一次性注册([]), 闭包不再读旧快照;
  //   覆盖旧请求前 await 旧 confirm(false) 回声, 防 fire-and-forget / 中间请求泄漏
  const pendingRef = React.useRef<AuthorizationRequest | null>(null);
  React.useEffect(() => {
    pendingRef.current = authorizationPending;
  }, [authorizationPending]);

  // 2026-09-06 小欧 B1「已放行」短时高亮: 用户确认(confirmed=true)后暂存工具名, 2s 后自动清除。
  //   让 RightViewer highlightToolName 在确认瞬间仍命中(isCurrentLive 不断链), 补 F4 高亮空转缺口 — 小欧-2026-09-06
  const [recentConfirmedTool, setRecentConfirmedTool] = useState<string | null>(
    null
  );
  const recentTimerRef = React.useRef<number | null>(null);
  React.useEffect(() => {
    return () => {
      if (recentTimerRef.current !== null)
        window.clearTimeout(recentTimerRef.current);
    };
  }, []);

  // [63] 5.15 v1.29：HITL 单源化——订阅 Store.pendingAuthorization（5.1 raw 载荷，5.3 收帧写入）
  //   派发端双删：useChatCallbacks.ts onAuthorizationRequired window 派发 + sseParser.ts resumed 兜底派发
  //   S1 超时放行(resumed) → 5.3 onResumed 置空 → 本快照 effect 关弹窗；用户 confirm/cancel → acknowledgeAuthorization
  //   归一化复用原逻辑：auto_confirm 四态、parseTimeout、同 id 去重与拒旧全保留
  const { pendingAuthorization } = useChatStreamSession(sessionId);
  useEffect(() => {
    if (pendingAuthorization) {
      const cur = pendingRef.current;
      // 2026-09-03 小欧 修复: 同confirmId重放去重，不二次resolve（原 :63-64）
      if (cur?.confirmId === pendingAuthorization.confirm_id) return;
      // 2026-09-30 00:52 小欧 - [63] 5.15 归位：原此处"二次授权覆盖旧 confirmId 先 confirm(false)"
      //   已下沉到 Store（chatStreamTransport.ts onAuthorizationRequired，覆写发生处）。
      //   保留在 effect 会与 Store 重复发起 confirm(false)，且同批多帧时 effect 只能看到末帧，
      //   本就漏拒中间请求 → 单一 owner 在 Store，hook 只负责归一化与展示（DRY/SRP）。
      const newRequest: AuthorizationRequest = {
        confirmId: pendingAuthorization.confirm_id,
        toolName: pendingAuthorization.tool_name,
        params: (pendingAuthorization.params ?? {}) as Record<string, unknown>,
        content: pendingAuthorization.content ?? '', // 7.4.3: 弹窗原因(后端 ConfirmSpec.content) — 小欧-2026-09-18
        safetyLevel: pendingAuthorization.safety_level ?? 'unknown',
        // 2026-09-03 小欧 D2-10: normalizeAutoConfirm四态归一(true/'true'/1/'1')
        autoConfirm:
          pendingAuthorization.auto_confirm === true ||
          pendingAuthorization.auto_confirm === 'true' ||
          pendingAuthorization.auto_confirm === 1 ||
          pendingAuthorization.auto_confirm === '1',
        // 2026-09-03 小欧 修复: 合法 0(禁倒计时)不被 || 兜成 60; 仅 NaN/负数 兜 60
        trustPath:
          typeof pendingAuthorization.trust_path === 'string'
            ? pendingAuthorization.trust_path
            : null,
        confirmTimeout: parseTimeout(pendingAuthorization.confirm_timeout),
        backendTimeout: parseTimeout(pendingAuthorization.backend_timeout),
      };
      // 2026-09-03 小欧 北京老陈 BUG FIX: 同步写入pendingRef, 堵React useEffect子先父后致子auto-confirm读到旧confirmId
      //   根因: React effects执行顺序=子先父后, setAuthorizationPending→子effect先跑→读pendingRef→旧值→发旧ID
      pendingRef.current = newRequest;
      setAuthorizationPending(newRequest);
    } else if (pendingRef.current) {
      // [63] 5.15：Store 侧清空（onResumed S1 放行 / onRejected / acknowledge）→ 关弹窗
      pendingRef.current = null;
      setAuthorizationPending(null);
    }
    // [63] 5.15：依赖从 [] 改 pendingAuthorization——快照驱动，无监听器即无闭包窗口
  }, [pendingAuthorization]);

  // 【v3.4新增 2026-06-09 小沈】授权确认处理
  // 2026-09-03 小欧/北京老陈 Bug修复: 弹窗立即消失+API后台fire-and-forget
  //   改前: await API → setPending(null), API失败/卡住→弹窗永久滞留
  //   改后: setPending(null)立即关弹窗 → API后台发, 失败弹message提示
  const handleAuthorizationConfirm = useCallback(
    (confirmed: boolean, trustSession: boolean, confirmIdOverride?: string) => {
      // 2026-09-03 小欧/北京老陈: 优先用弹窗传入的confirmId(精确), fallback用pendingRef(兜底)
      const cur = pendingRef.current;
      const confirmId = confirmIdOverride ?? cur?.confirmId;
      if (!confirmId) {
        return;
      }
      // 2026-09-06 小欧 B1: confirmed=true 且取到工具名 → 记录「已放行」短时高亮(2s), 拒绝/超时不记录
      if (confirmed && cur?.toolName) {
        if (recentTimerRef.current !== null)
          window.clearTimeout(recentTimerRef.current);
        setRecentConfirmedTool(cur.toolName);
        recentTimerRef.current = window.setTimeout(() => {
          setRecentConfirmedTool(null);
          recentTimerRef.current = null;
        }, 2000);
      }
      // 立即关弹窗, 不等API
      setAuthorizationPending(null);
      // [63] 5.15：同步清 Store.pendingAuthorization——否则切回页面快照 effect 重跑会重弹旧请求
      //   （流侧 5.3 onResumed/onRejected 也会清，两路幂等；此处保证"用户已处理"即时生效）
      if (sessionId) {
        pendingRef.current = null;
        chatStreamStore.acknowledgeAuthorization(sessionId);
      }
      // API后台fire-and-forget — 成功/200+success False/网络500均走公用错误弹窗
      taskControlApi
        .confirm(confirmId, confirmed, trustSession)
        .then((res: unknown) => {
          const ok = (res as { success?: boolean })?.success !== false;
          if (!ok) {
            // 2026-09-19 小欧 P-005契约化(北京老陈批准): confirm_id失效判定改读后端稳定code字段,
            //   替代字符串includes匹配(改前4关键词脆弱, 后端message文案变更即前端失效) — 小欧-2026-09-19
            if ((res as { code?: string })?.code === 'confirm_stale') {
              console.warn(
                '[Authorization] confirm_id已失效(良性):',
                confirmId
              );
              return;
            }
            const err = (res as { error?: string })?.error ?? '确认失败';
            console.warn('[Authorization] 确认返回错误:', res);
            handleError({
              message: `授权确认失败: ${err}`,
              error_type: ErrorType.WARNING,
            });
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
          const msg =
            (
              error as {
                response?: { data?: { error?: string } };
                message?: string;
              }
            )?.response?.data?.error ??
            (error as { message?: string })?.message ??
            String(error);
          handleError({
            message: `授权确认异常: ${msg}`,
            error_type: ErrorType.WARNING,
          });
        });
    },
    [sessionId]
  );

  return {
    authorizationPending,
    handleAuthorizationConfirm,
    recentConfirmedTool,
  };
}
