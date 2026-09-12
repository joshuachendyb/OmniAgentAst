// 编辑历史: 2026-08-28 小欧 - NewChatContainer瘦身: 抽9 hook(useAuthorization/useChatScroll/useSessionMeta/useTaskSelection/useChainTokens/useChatInit/useChatLifecycle/useChatTitle/useChatPanels), 本文件<100行(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - v1.100实施: 点击任务联动右栏展开, 新增handleSelectTaskOpenRight包装(useChatPanels入参handleSelectTask→handleSelectTaskOpenRight, 4.5.1联动锚定) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复输入框悬空: 根div高度由写死calc(100vh-120px)改为height:100%填满Content(Content为flex:auto有确定高度, 原公式比实际可用高度矮61px导致底部空白) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.10 v1.103: G2修复(serverTaskId变化即refreshTasks, 4.8.4.2 SSE start帧任务产生即入列) + latestTaskId透传useTaskSelection/useChainTokens(diff⑤⑥签名同步) - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被隐藏修复。创建latestTaskRef常驻ref并透传useChatPanels→TaskListPanel(左列滚动定位到最新任务) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): useChainTokens入参加metaFrames(SSE实时token帧源), 解构新增sessionTokens并透传useChatPanels - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: CP-01 serverTaskId监听补sessionId防切会话残留旧列表 - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 同类DB滞后修复: 直播失败即刷新左列(消executing残留) - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - BUG-29修复修正: handleSendWithMode改async+await, 原void吞Promise致ChatInput catch永不触发回填无效 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 简化重构: AuthorizationModal加key={confirmId}强制重建, 新请求=新组件实例, 彻底消除countdown/autoHandledRef等跨请求残留 - 小欧-2026-09-03
// 编辑历史: 2026-09-06 小欧 - B1「已放行」短时高亮: useAuthorization 解构 recentConfirmedTool 并透传 useChatPanels —— 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈定案): liveErrorText✗ string 改 liveError(LiveError|null 对象形态,
//   onError 升为 (liveError: LiveError)=>void 接收 位4/类型分层字段) + setter/一处消费(if(liveError)refreshTasks,
//   暂用对象真值判空)与 useChatPanels 透传同步 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-A类: 去chatSession/chatPersistence解构(死解构, eslint@typescript-eslint/no-unused-vars) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 透传rightOpen状态给useChatPanels, 控制TaskListPanel模型标签provider前缀条件显示 - 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - thought重复根治(三堂会审定案): 病根=useChatInit effect依赖searchParams对象引用
//   (React Router useSearchParams每次渲染返回新对象)致流式期间反复重跑initializeSession, 直接赋值
//   setMessages(result.messages)覆盖流式assistant消息; 根治=只传稳定urlSessionId字符串(非全局searchParams对象),
//   effect依赖它(session_id不变即不重跑)。曾用useMemo稳定引用(堵截)与isReceiving守卫(边界退化)两案, 复查后撤销 — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - R3+R4修复: R3加prevReceivingForR3Ref effect(isReceiving翻false时从messages取final.response即时写入task, 不读DB);
//   R4删旧prevReceivingRef effect改hasFinalStats信号(final_stats到达=DB已落库才触发refreshTasks); 解构补updateTaskResponse — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - P1-10三堂会审修复: L54 searchParams.get('session_id') 复用已有 urlSessionId(L47), 消重复取参(DRY) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - P1左卡草稿根治: R3数据源修正(lastMsg.content→executionSteps中type=final的step.response, 无兜底) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - X2终态短信号(北京老陈定案): 删除R4(hasFinalStats→refreshTasks DB兜底补左侧response), 铁命令: 左侧只用final.response, 实时短条留空、历史回放从DB读; useChainTokens 的 final_stats→refreshTasks(token刷新)保持不变 — 小欧-2026-09-12
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { LiveError } from '@/types/sse'; // 2026-09-08 小欧 6.3.4 位4数据源对象形态 — 小欧-2026-09-08
import { API_BASE_URL } from '../services/api/client';
import { useChatFacade } from '../features/chat/hooks/useChatFacade';
import { useSessionTasks } from '../features/chat/hooks/useSessionTasks';
import { useModelLayer } from '../features/chat/hooks/useModelLayer';
import { useAuthorization } from '../features/chat/hooks/useAuthorization';
import { useChatScroll } from '../features/chat/hooks/useChatScroll';
import { useSessionMeta } from '../features/chat/hooks/useSessionMeta';
import { useTaskSelection } from '../features/chat/hooks/useTaskSelection';
import { useChainTokens } from '../features/chat/hooks/useChainTokens';
import { useChatInit } from '../features/chat/hooks/useChatInit';
import { useChatLifecycle } from '../features/chat/hooks/useChatLifecycle';
import { useChatTitle } from '../features/chat/hooks/useChatTitle';
import { useChatPanels } from '../features/chat/hooks/useChatPanels';
import { SessionLayout } from '../features/chat/components/layout/SessionLayout';
import AuthorizationModal from '../components/AuthorizationModal';
import { Colors } from '@/utils/stepStyles';

const ChatPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  // 2026-09-10 小欧: thought重复根治(三堂会审定案): 传稳定urlSessionId字符串给useChatInit,
  //   effect依赖它(非全局searchParams对象引用), 流式期间session_id不变即不重跑initializeSession。 — 小欧-2026-09-10
  const urlSessionId = searchParams.get('session_id');
  const [liveError, setLiveError] = useState<LiveError | null>(null); // 2026-09-08 小欧 6.3.4: 对象形态(位4 类型+分层字段) — 小欧-2026-09-08
  const [rightOpen, setRightOpen] = useState(true);
  // 2026-09-01 小欧 方案C: 左列最新任务锚点ref(常驻, 传入useChatPanels→TaskListPanel滚动定位)
  const latestTaskRef = useRef<HTMLDivElement | null>(null);
  const chatFacade = useChatFacade({
    baseURL: API_BASE_URL,
    sessionId: urlSessionId, // 2026-09-12 小欧 P1-10: 复用 L47 已取 urlSessionId, 消重复 searchParams.get(DRY) — 小欧-2026-09-12
    onError: (liveError: LiveError) => setLiveError(liveError),
  });
  const { chatState, chatStreaming, chatSend, chatTaskControl } = chatFacade;
  const { sessionId } = chatState;
  const {
    tasks,
    total,
    loading: tasksLoading,
    refresh: refreshTasks,
    latestTaskId,
    updateTaskResponse, // 小欧 2026-09-11 R3: SSE final 帧到达时即时更新 task response — 小欧-2026-09-11
  } = useSessionTasks(sessionId);
  const { effective } = useModelLayer({
    sessionId,
    sessionTitle: chatState.sessionTitle,
    sessionVersion: chatState.sessionVersion,
    setSessionVersion: chatState.setSessionVersion,
    sessionModelOverride: chatState.sessionModelOverride,
  });

  const {
    authorizationPending,
    handleAuthorizationConfirm,
    recentConfirmedTool,
  } = useAuthorization(sessionId);
  useChatScroll(chatState, chatStreaming);
  const { sessionTimes } = useSessionMeta(sessionId);
  const { activeTaskId, selectedDetail, handleSelectTask } = useTaskSelection(
    sessionId,
    chatStreaming.serverTaskId,
    chatStreaming.isReceiving,
    latestTaskId,
    tasks
  );

  // 2026-08-30 小欧 diff⑦: G2修复(4.8.4.2) serverTaskId变化即刷新任务列表(SSE start帧任务产生即入列, 左列实时可见)
  const prevServerTaskIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (prevServerTaskIdRef.current !== chatStreaming.serverTaskId) {
      prevServerTaskIdRef.current = chatStreaming.serverTaskId;
      if (chatStreaming.serverTaskId) {
        void refreshTasks();
      }
    }
  }, [chatStreaming.serverTaskId, sessionId, refreshTasks]);

  // 小欧 2026-09-11 R3: 实时当前任务回复只读 final.response，不读 DB
  //   isReceiving 翻 false = final 到达 → 从 executionSteps 取 type=final step.response 即时写入 task —
  //   2026-09-12 修: 原读 chatState.messages 尾部 lastMsg.content(实为流式正文含草稿, 非 final.response) — 小欧-2026-09-12
  // 铁命令(北京老陈 2026-09-12): 左侧任务 response 只允许源自 SSE final 帧的 final.response,
  //   严禁用 DB 查询/消息正文/refreshTasks 全量刷新或其他任何兜底顶替——R4(hasFinalStats→refreshTasks)已据令删除。
  //   实时短条 final.response 为空则左侧留空; 历史回放的完整 response 由 DB 落库长条经 useSessionTasks.refresh() 加载。 — 小欧-2026-09-12
  const prevReceivingForR3Ref = useRef(false);
  useEffect(() => {
    if (
      prevReceivingForR3Ref.current &&
      !chatStreaming.isReceiving &&
      chatStreaming.serverTaskId
    ) {
      const finalStep = chatStreaming.executionSteps.find(
        (s) => s.type === 'final'
      );
      const finalResponse = (finalStep?.response as string) || '';
      if (finalResponse) {
        updateTaskResponse(chatStreaming.serverTaskId, finalResponse);
      }
    }
    prevReceivingForR3Ref.current = chatStreaming.isReceiving;
  }, [
    chatStreaming.isReceiving,
    chatStreaming.serverTaskId,
    chatStreaming.executionSteps,
    updateTaskResponse,
  ]);

  // 2026-08-30 小欧 v1.100: 点击任务 → 右栏展开(4.5.1 联动锚定: 点击查看即展开)
  const handleSelectTaskOpenRight = useCallback(
    (taskId: string) => {
      setRightOpen(true);
      handleSelectTask(taskId);
    },
    [handleSelectTask]
  );
  const { sessionTokens, chainTokens } = useChainTokens(
    sessionId,
    chatStreaming.serverTaskId,
    chatStreaming.isReceiving,
    latestTaskId,
    tasks,
    refreshTasks,
    chatStreaming.metaFrames // 2026-09-01 小欧: SSE实时token帧源
  );
  const handleSendWithMode = useCallback(
    async (content: string, mode?: 'linked' | 'independent') => {
      setLiveError(null);
      await chatSend.handleSend(content, mode);
    },
    [chatSend, setLiveError]
  );

  // 2026-08-27 小欧 修复#42: 切换会话时重置跨会话泄漏状态(liveError)
  useEffect(() => {
    setLiveError(null);
  }, [sessionId]);

  // 2026-09-02 小欧 - 同类DB滞后修复: 直播失败文案到达即刷新左列, 消DB executing残留(与useTaskInfo徽标兜底同窗) - 小欧-2026-09-02
  useEffect(() => {
    if (liveError) void refreshTasks();
  }, [liveError, refreshTasks]);

  // 会话初始化 / 生命周期 / 标题编辑（抽离至各 hook）
  useChatInit({ chatFacade, urlSessionId });
  const { handleNewSession } = useChatLifecycle({ chatFacade });
  const { handleEditingStart, handleEditingCancel } = useChatTitle(chatState);

  const panels = useChatPanels({
    chatState,
    chatStreaming,
    chatTaskControl,
    chatSend,
    liveError,
    authorizationPending,
    recentConfirmedTool, // 2026-09-06 小欧 B1: 「已放行」短时高亮透传 — 小欧-2026-09-06
    handleAuthorizationConfirm,
    tasks,
    total,
    tasksLoading,
    refreshTasks,
    effective,
    sessionTimes,
    activeTaskId,
    selectedDetail,
    handleSelectTask: handleSelectTaskOpenRight,
    sessionTokens,
    chainTokens,
    handleNewSession,
    handleEditingStart,
    handleEditingCancel,
    handleSendWithMode,
    latestTaskId, // 2026-09-01 小欧 方案C: 左列最新任务锚点透传
    latestTaskRef, // 2026-09-01 小欧 方案C: 滚动定位ref透传
    rightOpen, // 2026-09-09 小欧: 右侧展开状态透传TaskListPanel
  });

  return (
    <div
      style={{
        height: 'calc(100vh - 59px)', // 2026-08-30 小欧: 精确贴合Content内容区高度=Header43+padding上6下10; 原calc(100vh-120px)矮61px致底部空白, height:100%会随父级撑高掉屏外, 两者均废弃
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        padding: '0 8px 8px',
        background: Colors.BG.PRIMARY,
        minWidth: 0,
      }}
    >
      <SessionLayout
        panels={panels}
        rightOpen={rightOpen}
        onToggleRight={() => setRightOpen((v) => !v)}
      />
      <AuthorizationModal
        key={authorizationPending?.confirmId ?? 'none'}
        visible={!!authorizationPending}
        request={authorizationPending}
        onConfirm={handleAuthorizationConfirm}
      />
    </div>
  );
};

export default ChatPage;
