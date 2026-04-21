/**
 * NewChatContainer重构示例 - 使用Hook架构
 * 
 * 这是一个示例文件，展示了如何使用新的Hook架构重构NewChatContainer
 * 实际重构时，请按照以下步骤逐步替换原有代码
 * 
 * @author 小强
 * @version 4.0.0
 * @since 2026-04-21
 */

import React, { useEffect } from "react";
import { Card } from "antd";
import { useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../../services/api";

// 导入新的Hook
import { useChatState } from '../../hooks/chat/useChatState';
import { useChatCallbacks } from '../../hooks/chat/useChatCallbacks';
import { useChatStreaming } from '../../hooks/chat/useChatStreaming';
import { useChatSession } from '../../hooks/chat/useChatSession';
import { useChatPersistence } from '../../hooks/chat/useChatPersistence';

// 导入工具函数
import { handleError, handleApiError } from "../../utils/errorHandler";
import { logAIComplete, logAIError, logUserSend } from "../../utils/chatLogger";
import { getClientInfo } from "../../utils/clientInfo";
import { showSaveError, showLoadSuccess, showNetworkError } from "../../utils/chatMessages";

// 导入组件
import ChatInput from "./ChatInput";
import MessageArea from './MessageArea';
import ChatHeader from './ChatHeader';
import ChatToolbar from './ChatToolbar';

/**
 * NewChatContainer重构版本 - 使用Hook架构
 * 
 * 重构步骤：
 * 1. 导入所有新的Hook
 * 2. 按顺序初始化Hook
 * 3. 解构需要的状态和函数
 * 4. 替换原有的业务逻辑
 * 5. 保持UI组件不变
 */
const NewChatContainerRefactored: React.FC = () => {
  const [searchParams] = useSearchParams();
  
  // ==================== 1. 状态管理 ====================
  const chatState = useChatState();
  
  // ==================== 2. 回调管理 ====================
  const chatCallbacks = useChatCallbacks(chatState);
  
  // ==================== 3. SSE流式管理 ====================
  const chatStreaming = useChatStreaming(
    chatState,
    chatCallbacks,
    { baseURL: API_BASE_URL, sessionId: chatState.sessionId }
  );
  
  // ==================== 4. 会话管理 ====================
  const chatSession = useChatSession(chatState);
  
  // ==================== 5. 持久化管理 ====================
  const chatPersistence = useChatPersistence(chatState, chatStreaming);
  
  // ==================== 解构状态和函数 ====================
  
  // 从chatState解构
  const {
    messages, setMessages,
    loading, setLoading,
    waitTime, setWaitTime,
    isRetrying, setIsRetrying,
    isPaused, setIsPaused,
    sessionId, sessionTitle, sessionVersion, titleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    lastSavedTitle, setLastSavedTitle,
    showExecution, setShowExecution,
    useStream, setUseStream,
    isInitialized, setIsInitialized,
    
    // Refs
    waitTimerRef,
    messagesEndRef,
    currentSessionIdRef,
    messagesCountRef,
    messagesRef,
    replyUserMessageIdRef,
    displayBufferRef,
    isPausedRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    userScrolledUpRef,
    lastScrollTimeRef,
    isLoadingHistoryRef,
    logFlagsRef,
    hasReceivedInterruptEventRef,
    interruptInProgressRef,
  } = chatState;
  
  // 从chatCallbacks解构（如果需要直接访问）
  const {
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
  } = chatCallbacks;
  
  // 从chatStreaming解构
  const {
    isReceiving,
    setIsReceiving,
    executionSteps,
    currentResponse,
    sendMessage,
    disconnect,
    clearSteps,
    serverTaskId,
  } = chatStreaming;
  
  // 从chatSession解构
  const {
    loadSession,
    handleNewSession,
    handleClear,
    updateSessionTitle,
  } = chatSession;
  
  // 从chatPersistence解构
  const {
    saveState,
    saveStateWithSSECheck,
    clearStorage,
    restoreState,
    saveMessagesToStorage,
  } = chatPersistence;
  
  // ==================== 业务函数（可以进一步拆分） ====================
  
  /**
   * handleSendMessage - 发送消息
   * 迁移自：NewChatContainer.tsx 中的发送消息逻辑
   */
  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isReceiving) return;
    
    try {
      // 记录用户发送
      logUserSend(content);
      
      // 创建用户消息
      const userMessage: Message = {
        id: Date.now().toString(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };
      
      // 添加到消息列表
      setMessages(prev => [...prev, userMessage]);
      setLoading(true);
      
      // 重置流式状态
      streamingContentRef.current = '';
      streamingStepsRef.current = [];
      
      // 发送消息
      await sendMessage(content.trim(), sessionId || undefined);
      
      // 保存到sessionStorage
      saveMessagesToStorage.current(
        [...messages, userMessage],
        sessionId || "new-session",
        sessionTitle,
        isPaused,
        true // isReceiving
      );
      
    } catch (error) {
      console.error("发送消息失败:", error);
      handleApiError(error);
      setLoading(false);
    }
  };
  
  /**
   * handleInterrupt - 中断任务
   */
  const handleInterrupt = () => {
    if (!isReceiving) return;
    
    console.log("[中断] 用户手动中断任务");
    interruptInProgressRef.current = true;
    disconnect();
    
    // 清理状态
    setLoading(false);
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
      waitTimerRef.current = null;
    }
    setWaitTime(0);
    setIsRetrying(false);
    
    // 显示中断消息
    setMessages(prev => {
      const lastMessage = prev[prev.length - 1];
      if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...lastMessage,
          content: lastMessage.content + "\n\n[用户中断了任务]",
          isStreaming: false,
        };
        return updated;
      }
      return prev;
    });
    
    // 重置中断标记
    setTimeout(() => {
      interruptInProgressRef.current = false;
    }, 1000);
  };
  
  /**
   * handleTogglePause - 切换暂停状态
   */
  const handleTogglePause = () => {
    if (isPaused) {
      // 恢复
      setIsPaused(false);
      // 触发onResumed回调
      onResumed();
    } else {
      // 暂停
      setIsPaused(true);
      // 触发onPaused回调
      onPaused();
    }
  };
  
  /**
   * handleUpdateTitle - 更新会话标题
   */
  const handleUpdateTitle = async (newTitle: string) => {
    try {
      await updateSessionTitle(newTitle);
    } catch (error) {
      console.error("更新标题失败:", error);
    }
  };
  
  // ==================== 初始化效果 ====================
  
  useEffect(() => {
    // 组件挂载时恢复状态
    const init = async () => {
      if (isInitialized) return;
      
      try {
        // 从URL参数获取sessionId
        const urlSessionId = searchParams.get("session_id");
        if (urlSessionId) {
          const loadedMessages = await loadSession(urlSessionId);
          setMessages(loadedMessages);
        } else {
          // 从sessionStorage恢复
          const restored = await restoreState();
          if (restored) {
            setMessages(restored.messages);
            // 注意：sessionId等状态已经在restoreState中设置
          }
        }
        
        setIsInitialized(true);
      } catch (error) {
        console.error("初始化失败:", error);
        handleError(error);
      }
    };
    
    init();
  }, [searchParams, isInitialized, loadSession, restoreState, setMessages, setIsInitialized]);
  
  // ==================== 渲染UI ====================
  
  return (
    <div className="new-chat-container">
      <ChatHeader
        title={sessionTitle}
        locked={titleLocked}
        editing={editingTitle}
        titleInput={titleInput}
        onEditStart={() => setEditingTitle(true)}
        onEditCancel={() => {
          setEditingTitle(false);
          setTitleInput("");
        }}
        onEditSave={handleUpdateTitle}
        onTitleInputChange={setTitleInput}
      />
      
      <ChatToolbar
        onNew={handleNewSession}
        onClear={handleClear}
        useStream={useStream}
        onToggleStream={() => setUseStream(!useStream)}
        showExecution={showExecution}
        onToggleExecution={() => setShowExecution(!showExecution)}
      />
      
      <MessageArea
        messages={messages}
        loading={loading}
        isReceiving={isReceiving}
        showExecution={showExecution}
        executionSteps={executionSteps}
        messagesEndRef={messagesEndRef}
        onScroll={() => {
          // 处理滚动逻辑
          const container = messagesEndRef.current?.parentElement;
          if (container) {
            const { scrollTop, scrollHeight, clientHeight } = container;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
            userScrolledUpRef.current = !isNearBottom;
            lastScrollTimeRef.current = Date.now();
          }
        }}
      />
      
      <ChatInput
        onSend={handleSendMessage}
        onInterrupt={handleInterrupt}
        isReceiving={isReceiving}
        waitTime={waitTime}
        isPaused={isPaused}
        onTogglePause={handleTogglePause}
        disabled={loading}
      />
    </div>
  );
};

export default NewChatContainerRefactored;