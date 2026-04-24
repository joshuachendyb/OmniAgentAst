import React, { useEffect, useCallback } from "react";
import { message, Card } from "antd";
import { useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../../services/api";
import {
  STORAGE_KEY,
} from "../../utils/chatHistory";

import ChatInput from "./ChatInput";
import MessageArea from './MessageArea';
import ChatHeader from './ChatHeader';
import ChatToolbar from './ChatToolbar';
import { useChatFacade } from '../../hooks/chat/useChatFacade';
import { useLoadingMessage } from '../../hooks/useLoadingMessage';
import { useBeforeUnload } from '../../hooks/useBeforeUnload';

const NewChatContainer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const chatFacade = useChatFacade({ baseURL: API_BASE_URL, sessionId: searchParams.get('sessionId') });
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
    // 独立状态
    showExecution, setShowExecution,
    useStream, setUseStream,
    setIsInitialized,
    setSessionJumpLoading,
    isMessageListLoading, setIsMessageListLoading,
    retryCount, setRetryCount,
    setIsRenderingMessages,
    isRetrying,
    isPaused, setIsPaused,
    messages,
    loading,
    waitTime,
    sessionId,
    sessionTitle, setSessionTitle,
    sessionVersion, setSessionVersion,
    titleLocked, setTitleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    // Refs
    messagesEndRef,
    messagesRef,
    isPausedRef,
    executionStepsRef,
    userScrolledUpRef,
    isLoadingHistoryRef,
    logFlagsRef,
  } = chatState;

  // 解构chatStreaming
  const {
    isReceiving,
    executionSteps,
    currentResponse,
  } = chatStreaming;

  // 解构chatTaskControl
  const { handleInterrupt, handleTogglePause } = chatTaskControl;

  // 解构chatSend
  const { handleSend } = chatSend;

  // chatPersistence 直接使用（restoreState）

  // 使用useLoadingMessage Hook管理loading
  const { show: showLoading, hide: hideLoading } = useLoadingMessage({ duration: 0 });

  // 新建会话
  const handleNewSession = useCallback(() => {
    console.log("🔍 [handleNewSession] 按钮被点击");
    chatSession.handleNewSession(0);
  }, [chatSession]);

  // 清空对话
  const handleClear = useCallback(() => {
    console.log("🔍 [handleClear] 清空对话按钮被点击");
    setIsPaused(false);
    logFlagsRef.current = {
      chunkFirstDone: false,
      showStepsFalseDone: false,
      showStepsTrueDone: false,
    };
    chatSession.handleClear();
  }, [chatSession, logFlagsRef, setIsPaused]);

  // 滚动控制参数
  const SCROLL_THRESHOLD = 150;

  // 延迟滚动

  // 延迟滚动
  const scrollToBottomDelayed = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, [messagesEndRef]);

  // 同步 isPaused 状态到 ref
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused, isPausedRef]);

  // 滚动位置监听
  useEffect(() => {
    const container = messagesEndRef.current?.parentElement;
    if (!container) return;
    
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      userScrolledUpRef.current = distanceFromBottom > SCROLL_THRESHOLD;
    };
    
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [messagesEndRef, userScrolledUpRef]);

  // 当页面从隐藏状态变为显示时也自动滚动到底部
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        scrollToBottomDelayed();
        console.log(`[visibilitychange] 当前状态: isReceiving=${isReceiving}, hasExecutionSteps=${executionSteps.length > 0}`);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [currentResponse, executionSteps, isReceiving, scrollToBottomDelayed]);

  // 保存状态（用于beforeunload）
  const handleSaveBeforeUnload = useCallback(() => {
    if (!isReceiving || !sessionId) return;

    console.log("💾 [beforeunload] 刷新前保存状态, steps:", executionStepsRef.current.length);
    
    let messagesToSave = messagesRef.current;
    if (executionStepsRef.current.length > 0) {
      messagesToSave = messagesRef.current.map((msg, idx) => {
        if (msg.role === 'assistant' && msg.isStreaming && idx === messagesRef.current.length - 1) {
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
    
    try {
      const stateStr = JSON.stringify(state);
      if (stateStr.length > 4 * 1024 * 1024) {
        const lightState = {
          sessionId,
          sessionTitle,
          timestamp: Date.now(),
          messageCount: messagesToSave.length,
          isPaused,
          isReceiving,
        };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lightState));
      } else {
        sessionStorage.setItem(STORAGE_KEY, stateStr);
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'QuotaExceededError') {
        console.warn("⚠️ [beforeunload] sessionStorage容量满，跳过保存");
      } else {
        console.error("保存会话状态失败:", e);
      }
    }
  }, [isReceiving, sessionId, sessionTitle, isPaused, executionStepsRef, messagesRef]);

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
      message.destroy("session-load");
      console.log("🔄 组件卸载（页面即将跳转或关闭）");
    };
  }, []);

  // 会话状态持久化 - 使用chatSession.initializeSession
  useEffect(() => {
    const onLoadingStart = () => {
      setSessionJumpLoading(true);
      showLoading("正在加载会话...", "session-load");
    };

    const onLoadingEnd = () => {
      hideLoading("session-load");
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
  }, [searchParams, showLoading, hideLoading, chatPersistence, chatSession, isLoadingHistoryRef, retryCount, setRetryCount, setIsInitialized, setSessionJumpLoading, setIsMessageListLoading, setIsRenderingMessages]);

  // 组件卸载时清理loading
  useEffect(() => {
    return () => {
      hideLoading("session-load");
    };
  }, [hideLoading]);

  // 全局快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + K 清空对话
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        handleClear();
      }
      // Ctrl/Cmd + N 新建会话
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        handleNewSession();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleClear, handleNewSession]);

  // ChatHeader回调
  const handleEditingStart = useCallback(() => {
    if (!editingTitle && sessionId) {
      setTitleInput(sessionTitle || "");
    }
    setEditingTitle(true);
  }, [editingTitle, sessionId, sessionTitle, setTitleInput, setEditingTitle]);

  const handleEditingCancel = useCallback(() => {
    setEditingTitle(false);
  }, [setEditingTitle]);

  // ChatToolbar回调
  const handleToggleStream = useCallback((checked: boolean) => {
    console.log("🔍 [流式开关] 被点击，新状态:", checked);
    setUseStream(checked);
    if (!checked) {
      setShowExecution(false);
    }
  }, [setUseStream, setShowExecution]);

  const handleToggleExecution = useCallback(() => {
    console.log("🔍 [显示过程] 按钮被点击");
    setShowExecution(!showExecution);
  }, [showExecution, setShowExecution]);

  return (
    <Card
      styles={{ body: { padding: "0 4px 4px" } }}
      title={
        <ChatHeader
          sessionId={sessionId}
          sessionTitle={sessionTitle}
          titleLocked={titleLocked}
          editingTitle={editingTitle}
          titleInput={titleInput}
          sessionVersion={sessionVersion}
          setSessionTitle={setSessionTitle}
          setTitleLocked={setTitleLocked}
          setEditingTitle={setEditingTitle}
          setTitleInput={setTitleInput}
          setSessionVersion={setSessionVersion}
          onEditingStart={handleEditingStart}
          onEditingCancel={handleEditingCancel}
        />
      }
      extra={
        <ChatToolbar
          useStream={useStream}
          showExecution={showExecution}
          onNewSession={handleNewSession}
          onClear={handleClear}
          onToggleStream={handleToggleStream}
          onToggleExecution={handleToggleExecution}
        />
      }
    >
      <MessageArea
        messages={messages}
        showExecution={showExecution}
        sessionId={sessionId}
        sessionTitle={sessionTitle}
        useStream={useStream}
        isMessageListLoading={isMessageListLoading}
        messagesEndRef={messagesEndRef}
      />

      <ChatInput
        loading={loading}
        isReceiving={isReceiving}
        isPaused={isPaused}
        isRetrying={isRetrying}
        waitTime={waitTime}
        useStream={useStream}
        onSend={handleSend}
        onInterrupt={handleInterrupt}
        onTogglePause={handleTogglePause}
      />
    </Card>
  );
};

export default NewChatContainer;
