// 编辑历史: 2026-08-28 小欧 - NewChatContainer瘦身: 抽9 hook(useAuthorization/useChatScroll/useSessionMeta/useTaskSelection/useChainTokens/useChatInit/useChatLifecycle/useChatTitle/useChatPanels), 本文件<100行(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import React, { useState, useEffect, useCallback } from 'react';
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
    tasks
  );
  const { chainTokens } = useChainTokens(
    sessionId,
    chatStreaming.serverTaskId,
    chatStreaming.isReceiving,
    tasks,
    refreshTasks
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
    handleSelectTask,
    chainTokens,
    handleNewSession,
    handleEditingStart,
    handleEditingCancel,
    handleSendWithMode,
  });

  return (
    <div
      style={{
        height: 'calc(100vh - 120px)',
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
