// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离会话初始化与loading生命周期至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-10 小欧 - thought重复根治(三堂会审定案): 病根=effect依赖searchParams对象引用(每次渲染新引用)反复重跑
//   initializeSession覆盖流式消息; 根治=effect只依赖稳定session_id字符串, 不再传渲染无关的URL参数对象。
//   曾用useMemo稳定searchParams(堵截)与isReceiving守卫(边界退化)两案, 复查后均撤销。 — 小欧-2026-09-10
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.17 恢复优先: 同一 effect 内把 initializeSession 包成
//   chatStreamStore.resume().then 链——非 idle(流活着)且有 URL 会话时只 loadSession 补历史
//   (F7 不重新 POST、不重建任务); idle 走原三场景分支(参数未改) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-10-01 小欧 [1] 根治"采用已存在会话后 SSE 从不恢复"(刷新/菜单回跳/URL丢参 三入口同源):
//   新增第二个 effect，以"URL 无 session_id"为触发条件补 resume()。详见该 effect 注释。 — 小欧-2026-10-01
import { useEffect } from 'react';
import { useLoadingMessage } from '../../../hooks/useLoadingMessage';
import { getMessage } from '../../../lib/antd/bridge';
import { showWarning } from '../../../utils/chatMessages';
import { ERROR_TYPE_LABELS } from '../components/ErrorDetail';
import type { UseChatFacadeReturn } from './useChatFacade';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import type { ResumeResult } from '@/features/chat/streams/backupTypes';

// 编辑历史: 2026-09-30 08:34:56 小欧 - 恢复态差异化提示。
//   病根：resume() 返回 12 值 ResumeResult，此前全仓唯一消费点就是下方 `r !== 'idle'` 一个布尔判断
//   （12 值塌缩成 2 分支），导致 S5/S11 里"任务被中断 / 事件不完整 / 持久化降级"原地兜底成
//   "正常历史"——用户只见 DB 里的结果，无从判断该不该重试。
//   落点选在此处：这是 ResumeResult 唯一的 UI 边界，一次分派即拦住"恢复不完整却被静默吞掉"。
//   文案复用 ErrorDetail.ERROR_TYPE_LABELS（4 个 error_type 中文标签已存在，不另写一份以免漂移）；
//   ResumeResult↔error_type 的对应关系见 chatStreamTransport.RECOVERY_ERROR_BRANCH。
// 编辑历史: 2026-09-30 14:30 小欧 - URL 回填加幂等守卫；删 No-op 入参 onMessageListLoadingStart
const RESUME_NOTICE: Partial<Record<ResumeResult, string>> = {
  task_interrupted: ERROR_TYPE_LABELS.task_interrupted,
  task_state_incomplete: ERROR_TYPE_LABELS.task_state_incomplete,
  gap: ERROR_TYPE_LABELS.persistence_gap,
  degraded: ERROR_TYPE_LABELS.persistence_degraded,
};
// 有意不提示的 8 值及依据：
//   idle / recovering / terminal  正常态，提示即噪声；
    //   pending_draft                 草稿本就在客户端（adoptLiveTaskOrDraft 语义），非异常；
//   aborted                       用户主动停，非故障；
//   polling                       轮询观察中，reconnectStatus 已在 UI 呈现；
//   failed                        已走 error 通道 → TaskInfoBar 位4（"error 实时显示唯一位置"定案），再提示即双显示；
//   not_found                     resumeStreamRequest 无终态短路，任务行被归档的**常见良性场景**同样命中，
//                                 发提示会对每次切回旧会话误报。

/**
 * 会话初始化 hook：initializeSession 效果 + loading 挂载/卸载清理
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatInit(opts: {
  chatFacade: UseChatFacadeReturn;
  urlSessionId: string | null;
}): void {
  const { chatState, chatSession, chatPersistence } = opts.chatFacade;
  const { show, hide } = useLoadingMessage({ duration: 0 });
  // 2026-10-01 小欧 [1] - 权威会话 id 的局部稳定别名：下方新 effect 的依赖项必须是标量字符串，
  //   取 chatState（每次渲染新对象）入依赖会自激重跑。取值语义与 useChatFacade.ts:99 真源判据同源。
  const adoptedSessionId = chatState.sessionId;

  // 会话状态持久化 - 仅 URL session_id 真正变化重新初始化（依赖稳定字符串, 非渲染无关的对象引用）
  useEffect(() => {
    // 2026-09-30 小欧 - 初始化幂等守卫：URL 指向的会话若已是当前会话，说明刚被
    //   handleNewSessionInternal 初始化过，跳过（否则会 resume+loadSession，用后端历史
    //   覆盖刚设的"新会话已创建"提示）。404 清理/列表切回时两者不等，不受影响。
    if (opts.urlSessionId && chatState.sessionId === opts.urlSessionId) return;
    const onLoadingStart = () => {
      chatState.setSessionJumpLoading(true);
      show('正在加载会话...', 'session-load');
    };
    const onLoadingEnd = () => {
      hide('session-load');
      chatState.setSessionJumpLoading(false);
    };
    const onRenderStart = () => {
      chatState.setIsRenderingMessages(true);
    };
    const onRenderEnd = () => {
      chatState.setIsRenderingMessages(false);
    };
    // 2026-09-30 小欧 - 删 onMessageListLoadingStart：其函数体本就是 No-op 空壳，
    //   useChatSession 解构后零调用（靠 eslint-disable 压着），整条链是纯接口污染
    const onMessageListLoadingEnd = () => {
      chatState.setIsMessageListLoading(false);
    };

    // 2026-09-10 小欧: initializeSession内部仅读searchParams.get('session_id')(据useChatSession.ts:227),
    //   故此处只构造session_id一个键的URLSearchParams, 避免渲染无关URL参数引入引用不稳定 — 小欧-2026-09-10
    const searchParams = new URLSearchParams(
      opts.urlSessionId ? { session_id: opts.urlSessionId } : {}
    );

    // [63] 5.17 v1.29 恢复优先：非 idle（流活着/已恢复/轮询/中断/降级等 12 态）→ 只补历史
    //   loadSession（F7：不重新 POST、不重建任务）；idle → 原 initializeSession 三场景原样执行
    void chatStreamStore.resume(opts.urlSessionId ?? undefined).then((r) => {
      if (r !== 'idle' && opts.urlSessionId) {
        // 2026-09-30 08:34:56 小欧 - 恢复不完整必须让用户看见（先提示再补历史，不等 loadSession）。
        const notice = RESUME_NOTICE[r];
        if (notice) showWarning(notice);
        // 2026-10-01 小欧 [1] B7: 本分支现也会被「书签/新标签页访问正在跑的会话」命中
        //   （resume 查到活任务 → 返回非 idle）。该分支原先只在"备份有效"时可达, 而那时
        //   sessionStorage 尚在、页面刚 mount, 短暂无指示器无感; 现在跨标签页/书签进来也走这里,
        //   慢网络下会长时间空白。故补上与 initializeSession 同款的 loading 指示器 ——
        //   否则 B7 就是"恢复流变强、历史加载指示变弱"的净退化。
        onLoadingStart();
        void chatSession
          .loadSession(opts.urlSessionId)
          .finally(onLoadingEnd);
        return;
      }
      chatSession.initializeSession({
        searchParams,
        retryCount: chatState.retryCount,
        setRetryCount: chatState.setRetryCount,
        isLoadingHistoryRef: chatState.isLoadingHistoryRef,
        setIsInitialized: chatState.setIsInitialized,
        restoreState: chatPersistence.restoreState,
        onLoadingStart,
        onLoadingEnd,
        onRenderStart,
        onRenderEnd,
        onMessageListLoadingEnd,
      });
    });
    // 仅保留urlSessionId，避免重复执行initializeSession
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.urlSessionId]);

  // [63] 5.17 恢复优先：非 idle（流活着/已恢复/轮询/中断/降级等 12 态）→ 只补历史
  //   loadSession（F7：不重新 POST、不重建任务）；idle → 原 initializeSession 三场景原样执行
  // 2026-10-01 小欧 [1] 根治"采用已存在会话后 SSE 从不恢复"——病根链（每环均有行号实证）：
  //   ① 本 effect 上方只 resume(opts.urlSessionId)，即 resume 只认 URL 里的 session_id；
  //      URL 无参 → chatStreamStore.ts:679 `if (!sessionId) return 'idle'` 早退。
  //   ② 真实 sessionId 是 initializeSession 三分支**异步解析**出来的：
  //      useChatSession.ts:277 场景1(URL) 能被 ① 覆盖；:387 场景2(缓存) 与 :409 场景3(最近会话)
  //      只在 useChatSession 内部 setSessionId(:393/:429)，**从不触发 resume**。
  //   ③ 采用已存在会话**从不写 URL**——写 URL 的只有 useChatSession.ts:538(新建会话) 与
  //      useChatSend.ts:154(发消息)。于是"采用"永远停留在 URL 无参态，① 永远早退。
  //   ④ useChatSession.ts:271-274 刷新时 removeItem(STORAGE_KEY='chat_session_state')，
  //      场景2 缓存必失效 → 刷新必然落到场景3 → 必然无 resume → 右栏实时步骤永久停止。
  //   实测：E2E fre2e_14 连续两轮以裸 URL 刷新，120s 内零 `GET /chat/stream/...?after_seq=`；
  //        同一用例 URL 带 session_id 时立即续传（后端 reader 退出 is_reconnect=True, 起点seq=538）。
  //
  //   修法：以「URL 无 session_id」为唯一触发条件，在会话被解析出来之后补一次 resume()。
  //   为什么这个触发条件是精确且无竞态的（关键，三堂会审定案）：
  //   「URL 无参」⟺「本会话是从后端采用来的既有会话」。因为 handleNewSession 成功分支
  //   useChatSession.ts:538 **必定** onUrlSessionChange(newSessionId) 写 URL，
  //   故凡本标签页新建的会话，urlSessionId 必然非空 → 本 effect 一律早退 → 永不介入，
  //   "新建会话后立即发送"的 POST/GET 竞态窗口从根上不存在（不必再动 sendMessage 的
  //   isProcessing 守卫，也不必给 store 加探测口）。而 URL 无参时必然是场景2/场景3 采用既有会话，
  //   此时用户尚未发起发送（无内容可发），只读续传安全。
  //   为什么幂等、可扩展、可靠：
  //   幂等——chatStreamStore.ts:691 活流守卫(泵/发送/续传三瞬态 + reconnectTimeout≠null) 与
  //        transport.ts:239/246 的 resumeInFlight/pumpActive 双守卫，使与上方 URL 预调用共存；
  //        URL 带参时两处二调均回读当前状态（resumeResultOf），不重复建流、不重复 loadSession。
  //   只读——transport.ts:267-274 续传只发 GET after_seq，永不 POST；
  //        chatStreamStore.ts:422-434 findLiveTask 仅 listTasks 读，不改后端状态。
  //   无环——resume 只写 store（chatStreamStore.ts:693/972），从不回写 chatState.sessionId
  //        （后者唯一写口是 useChatSession 的 setSessionId），故不构成 effect 自激。
  //   可扩展——新增任何"采用会话"分支（未来场景、或不经 URL 的跳转），只要经 setSessionId
  //        落地就自动获得恢复能力，无需在每个分支各补一次 resume（避免 call-site 逐个打补丁）。
  //   为什么不调 loadSession：场景2/场景3 已载入历史消息，再调会用后端历史覆盖正在续传的
  //        messages（与 [63] 5.17 恢复优先同源矛盾）；恢复态提示沿用既有 RESUME_NOTICE
  //        唯一分派口径，不另写文案，避免双份文案漂移。
  useEffect(() => {
    // URL 已带会话 → 交给上方预调用（[63] 5.17 契约：非 idle 时只补历史），此处不重复介入
    if (opts.urlSessionId) return;
    if (!adoptedSessionId) return;
    void chatStreamStore.resume(adoptedSessionId).then((r) => {
      const notice = RESUME_NOTICE[r];
      if (notice) showWarning(notice);
    });
  }, [opts.urlSessionId, adoptedSessionId]);

  // 组件卸载时清理 loading + message
  useEffect(() => {
    return () => {
      getMessage().destroy('session-load');
      hide('session-load');
    };
  }, [hide]);
}
