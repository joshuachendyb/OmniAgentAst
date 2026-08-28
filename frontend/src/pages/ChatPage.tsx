// 编辑历史: 2026-08-28 小欧 - NewChatContainer瘦身: 抽6 hook(useAuthorization/useChatScroll/useSessionMeta/useTaskSelection/useChainTokens/useChatPanels)+本文件<100行(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE_URL } from '../services/api/client';
import { useChatFacade } from '../features/chat/hooks/useChatFacade';
import { useSessionTasks } from '../features/chat/hooks/useSessionTasks';
import { useModelLayer } from '../features/chat/hooks/useModelLayer';
import { useLoadingMessage } from '../hooks/useLoadingMessage';
import { useBeforeUnload } from '../hooks/useBeforeUnload';
import { useAuthorization } from '../features/chat/hooks/useAuthorization';
import { useChatScroll } from '../features/chat/hooks/useChatScroll';
import { useSessionMeta } from '../features/chat/hooks/useSessionMeta';
import { useTaskSelection } from '../features/chat/hooks/useTaskSelection';
import { useChainTokens } from '../features/chat/hooks/useChainTokens';
import { useChatPanels } from '../features/chat/hooks/useChatPanels';
import { SessionLayout } from '../features/chat/components/layout/SessionLayout';
import AuthorizationModal from '../components/AuthorizationModal';
import { saveChatState } from '../utils/sessionStorage';
import { getMessage } from '../lib/antd/bridge';
import { Colors } from '@/utils/stepStyles';

const ChatPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [liveErrorText, setLiveErrorText] = useState<string | null>(null);
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

  // 解构chatState
  const {
    setIsInitialized,
    setSessionJumpLoading,
    setIsMessageListLoading,
    retryCount,
    setRetryCount,
    setIsRenderingMessages,
    isPaused,
    messages,
    loading,
    sessionId,
    sessionTitle,
    setSessionTitle,
    sessionVersion,
    setSessionVersion,
    titleLocked,
    setTitleLocked,
    editingTitle,
    setEditingTitle,
    titleInput,
    setTitleInput,
    sessionModelOverride,
    setSessionModelOverride,
    messagesEndRef,
    messagesRef,
    isPausedRef,
    executionStepsRef,
    userScrolledUpRef,
    isLoadingHistoryRef,
  } = chatState;

  // 解构chatStreaming
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    metaFrames,
    serverTaskId,
  } = chatStreaming;

  // 解构chatTaskControl
  const { handleCancel, handleTogglePause } = chatTaskControl;

  // 解构chatSend
  const { handleSend } = chatSend;

  // 新建会话
  const handleNewSession = useCallback(() => {
    chatSession.handleNewSession(0);
  }, [chatSession]);

  // 插槽化组装新增状态与数据源
  const [rightOpen, setRightOpen] = useState(true);
  const {
    tasks,
    total,
    loading: tasksLoading,
    refresh: refreshTasks,
  } = useSessionTasks(sessionId);
  const { effective } = useModelLayer({
    sessionId,
    sessionTitle,
    sessionVersion,
    setSessionVersion,
    sessionModelOverride, // 2026-08-27 小欧 修复#2: 传入L2覆盖使顶栏徽标反映会话级模型(修复L2死代码)
  });

  // 授权弹窗（抽离至 useAuthorization）
  const { authorizationPending, handleAuthorizationConfirm } =
    useAuthorization(sessionId);

  // 滚动控制（抽离至 useChatScroll）
  useChatScroll({
    messagesEndRef,
    userScrolledUpRef,
    isPaused,
    isPausedRef,
    executionSteps,
    executionStepsRef,
    messages,
    currentResponse,
    isReceiving,
  });

  // 会话元数据（抽离至 useSessionMeta）
  const { sessionTimes } = useSessionMeta(sessionId);

  // 任务选择（抽离至 useTaskSelection）
  const { activeTaskId, selectedDetail, handleSelectTask } = useTaskSelection({
    sessionId,
    serverTaskId,
    isReceiving,
    tasks,
  });

  // 链累计 token（抽离至 useChainTokens）
  const { chainTokens } = useChainTokens({
    sessionId,
    serverTaskId,
    isReceiving,
    tasks,
    refreshTasks,
  });

  // 2026-08-27 小欧 修复#42: 切换会话时重置跨会话泄漏状态(liveErrorText)
  useEffect(() => {
    setLiveErrorText(null);
  }, [sessionId]);

  const handleSendWithMode = useCallback(
    (content: string, mode?: 'linked' | 'independent') => {
      setLiveErrorText(null);
      void handleSend(content, mode);
    },
    [handleSend]
  );

  // 使用useLoadingMessage Hook管理loading
  const { show: showLoading, hide: hideLoading } = useLoadingMessage({
    duration: 0,
  });

  // 保存状态（用于beforeunload）
  const handleSaveBeforeUnload = useCallback(() => {
    if (!isReceiving || !sessionId) return;

    let messagesToSave = messagesRef.current;
    if (executionStepsRef.current.length > 0) {
      messagesToSave = messagesRef.current.map((msg, idx) => {
        if (
          msg.role === 'assistant' &&
          msg.isStreaming &&
          idx === messagesRef.current.length - 1
        ) {
          return {
            ...msg,
            executionSteps: executionStepsRef.current,
          };
        }
        return msg;
      });
    }

    const state = {
      messages: messagesToSave,
      sessionId,
      sessionTitle,
      timestamp: Date.now(),
      scrollPosition: 0,
      isPaused,
      isReceiving,
    };

    // 2026-08-27 小欧 三堂会审: 会话状态保存下沉至 saveChatState(容量阈值/降级/容错)
    saveChatState(state);
  }, [
    isReceiving,
    sessionId,
    sessionTitle,
    isPaused,
    executionStepsRef,
    messagesRef,
  ]);

  // 使用useBeforeUnload Hook统一管理
  useBeforeUnload({
    shouldSave: !!isReceiving && !!sessionId,
    saveData: handleSaveBeforeUnload,
    showDialog: true,
    dialogMessage: '正在接收消息，确定要离开吗？',
  });

  // 组件卸载前清理
  useEffect(() => {
    return () => {
      getMessage().destroy('session-load');
    };
  }, []);

  // 会话状态持久化 - 使用chatSession.initializeSession
  // 仅当searchParams变化时才重新初始化（URL的sessionId变化）
  useEffect(() => {
    const onLoadingStart = () => {
      setSessionJumpLoading(true);
      showLoading('正在加载会话...', 'session-load');
    };

    const onLoadingEnd = () => {
      hideLoading('session-load');
      setSessionJumpLoading(false);
    };

    const onRenderStart = () => {
      setIsRenderingMessages(true);
    };

    const onRenderEnd = () => {
      setIsRenderingMessages(false);
    };

    const onMessageListLoadingStart = () => {
      // No-op: rendered inside initializeSession
    };

    const onMessageListLoadingEnd = () => {
      setIsMessageListLoading(false);
    };

    chatSession.initializeSession({
      searchParams,
      retryCount,
      setRetryCount,
      isLoadingHistoryRef,
      setIsInitialized,
      restoreState: chatPersistence.restoreState,
      onLoadingStart,
      onLoadingEnd,
      onRenderStart,
      onRenderEnd,
      onMessageListLoadingStart,
      onMessageListLoadingEnd,
    });
    // 仅保留searchParams，避免重复执行initializeSession（其他函数通过useCallback保持稳定）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 组件卸载时清理loading
  useEffect(() => {
    return () => {
      hideLoading('session-load');
    };
  }, [hideLoading]);

  // 全局快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + N 新建会话
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        handleNewSession();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleNewSession]);

  // ChatHeader回调
  const handleEditingStart = useCallback(() => {
    if (!editingTitle && sessionId) {
      setTitleInput(sessionTitle || '');
    }
    setEditingTitle(true);
  }, [editingTitle, sessionId, sessionTitle, setTitleInput, setEditingTitle]);

  const handleEditingCancel = useCallback(() => {
    setEditingTitle(false);
  }, [setEditingTitle]);

  // panels 组装（抽离至 useChatPanels）
  const panels = useChatPanels({
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
    handleEditingStart,
    handleEditingCancel,
    total,
    tasksLoading,
    chainTokens,
    sessionTimes,
    effective,
    handleNewSession,
    tasks,
    activeTaskId,
    handleSelectTask,
    serverTaskId,
    isReceiving,
    executionSteps,
    liveErrorText,
    authorizationPending,
    metaFrames,
    selectedDetail,
    loading,
    isPaused,
    handleSendWithMode,
    handleCancel,
    handleTogglePause,
    refreshTasks,
    sessionModelOverride,
    setSessionModelOverride,
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
