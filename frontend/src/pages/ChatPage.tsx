// 编辑历史: 2026-08-28 小欧 - NewChatContainer瘦身: 抽9 hook(useAuthorization/useChatScroll/useSessionMeta/useTaskSelection/useChainTokens/useChatInit/useChatLifecycle/useChatTitle/useChatPanels), 本文件<100行(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - v1.100实施: 点击任务联动右栏展开, 新增handleSelectTaskOpenRight包装(useChatPanels入参handleSelectTask→handleSelectTaskOpenRight, 4.5.1联动锚定) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复输入框悬空: 根div高度由写死calc(100vh-120px)改为height:100%填满Content(Content为flex:auto有确定高度, 原公式比实际可用高度矮61px导致底部空白) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.10 v1.103: G2修复(serverTaskId变化即refreshTasks, 4.8.4.2 SSE start帧任务产生即入列) + latestTaskId透传useTaskSelection/useChainTokens(diff⑤⑥签名同步) - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被隐藏修复。创建latestTaskRef常驻ref并透传useChatPanels→TaskListPanel(左列滚动定位到最新任务) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): useChainTokens入参加metaFrames(SSE实时token帧源), 解构新增sessionTokens并透传useChatPanels - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: CP-01 serverTaskId监听补sessionId防切会话残留旧列表 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 同类DB滞后修复: 直播失败即刷新左列(消executing残留) - 小欧-2026-09-02
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  const [liveErrorText, setLiveErrorText] = useState<string | null>(null);
  const [rightOpen, setRightOpen] = useState(true);
  // 2026-09-01 小欧 方案C: 左列最新任务锚点ref(常驻, 传入useChatPanels→TaskListPanel滚动定位)
  const latestTaskRef = useRef<HTMLDivElement | null>(null);
  const chatFacade = useChatFacade({
    baseURL: API_BASE_URL,
    sessionId: searchParams.get('session_id'),
    onError: (message: string) => setLiveErrorText(message),
  });
  const {
    chatState,
    chatStreaming,
    chatSession,
    chatPersistence,
    chatSend,
    chatTaskControl,
  } = chatFacade;
  const { sessionId } = chatState;
  const {
    tasks,
    total,
    loading: tasksLoading,
    refresh: refreshTasks,
    latestTaskId,
  } = useSessionTasks(sessionId);
  const { effective } = useModelLayer({
    sessionId,
    sessionTitle: chatState.sessionTitle,
    sessionVersion: chatState.sessionVersion,
    setSessionVersion: chatState.setSessionVersion,
    sessionModelOverride: chatState.sessionModelOverride,
  });

  const { authorizationPending, handleAuthorizationConfirm } =
    useAuthorization(sessionId);
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

  // 2026-09-02 小欧 - 同类DB滞后修复2: 收流结束(成功/失败/取消)即刷新, 补final后DB仍executing窗口(与G2 start刷新成对) - 小欧-2026-09-02
  const prevReceivingRef = useRef(false);
  useEffect(() => {
    if (
      prevReceivingRef.current &&
      !chatStreaming.isReceiving &&
      chatStreaming.serverTaskId
    )
      void refreshTasks();
    prevReceivingRef.current = chatStreaming.isReceiving;
  }, [chatStreaming.isReceiving, chatStreaming.serverTaskId, refreshTasks]);

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
    (content: string, mode?: 'linked' | 'independent') => {
      setLiveErrorText(null);
      void chatSend.handleSend(content, mode);
    },
    [chatSend, setLiveErrorText]
  );

  // 2026-08-27 小欧 修复#42: 切换会话时重置跨会话泄漏状态(liveErrorText)
  useEffect(() => {
    setLiveErrorText(null);
  }, [sessionId]);

  // 2026-09-02 小欧 - 同类DB滞后修复: 直播失败文案到达即刷新左列, 消DB executing残留(与useTaskInfo徽标兜底同窗) - 小欧-2026-09-02
  useEffect(() => {
    if (liveErrorText) void refreshTasks();
  }, [liveErrorText, refreshTasks]);

  // 会话初始化 / 生命周期 / 标题编辑（抽离至各 hook）
  useChatInit({ chatFacade, searchParams });
  const { handleNewSession } = useChatLifecycle({ chatFacade });
  const { handleEditingStart, handleEditingCancel } = useChatTitle(chatState);

  const panels = useChatPanels({
    chatState,
    chatStreaming,
    chatTaskControl,
    chatSend,
    liveErrorText,
    authorizationPending,
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
        visible={!!authorizationPending}
        request={authorizationPending}
        onConfirm={handleAuthorizationConfirm}
      />
    </div>
  );
};

export default ChatPage;
