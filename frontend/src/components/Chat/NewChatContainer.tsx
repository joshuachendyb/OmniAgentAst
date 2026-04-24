/**
 * NewChatContainer组件 - 升级版对话容器
 *
 * 功能：
 * - 完整会话管理（新建会话、编辑标题、历史记录加载）
 * - SSE流式输出 + 执行步骤可视化
 * - 安全检测v2.0（基于score的4级响应）
 * - 任务中断控制
 * - 标题管理优化（版本控制、锁定状态、来源标记）
 *
 * 错误处理说明：
 * - 所有错误统一使用 errorHandler.handleError()/handleApiError() 处理
 * - 禁止直接调用 message.error/warning/success/info
 * - 危险操作拦截、安全降级、错误去重由 errorHandler 统一管理
 *
 * @author 小新
 * @version 3.2.0
 * @since 2026-02-23
 * @update 2026-03-13 代码拆分：类型和工具函数提取到独立文件
 */

import React, { useEffect, useCallback, useState } from "react";
import { message, Card } from "antd";
import { useSearchParams } from "react-router-dom";
import { sessionApi, API_BASE_URL } from "../../services/api";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { Message } from "../../types/chat";
import {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  STORAGE_KEY,
} from "../../utils/chatHistory";

// 【小强修复 2026-03-31】独立输入框组件，隔离inputValue状态避免父组件重渲染
import ChatInput from "./ChatInput";

// 【小沈 2026-04-21】MessageArea组件拆分
import MessageArea from './MessageArea';

// 【小沈 2026-04-21】ChatHeader组件拆分
import ChatHeader from './ChatHeader';
// 【小沈 2026-04-21】ChatToolbar组件拆分
import ChatToolbar from './ChatToolbar';

// 【小强 2026-04-24】集成useChatFacade替代7个独立Hook
import { useChatFacade } from '../../hooks/chat/useChatFacade';

// 【小沈 2026-04-24】P0-3优化：使用独立的loading管理Hook
import { useLoadingMessage } from '../../hooks/useLoadingMessage';

// 【小沈 2026-04-24】P2优化：使用统一的beforeunload管理Hook
import { useBeforeUnload } from '../../hooks/useBeforeUnload';

// 【小强 2026-04-12】Phase 2 P1级优化 - 消息列表useMemo优化（使用独立hook）
// import { useMessageListRender } from '../../hooks/useMessageListRender'; // 已移至MessageList组件内部

// 【小新 2026-03-13 代码拆分】类型和工具函数已提取到独立文件
// - 类型定义: src/types/chat.ts
// - 工具函数: src/utils/chatHistory.ts

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

  // 解构chatState（和原来一致）
  const {
    // 独立状态
    showExecution, setShowExecution,
    useStream, setUseStream,
    isInitialized, setIsInitialized,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    setSaveStatus,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    sessionJumpLoading, setSessionJumpLoading,
    isMessageListLoading, setIsMessageListLoading,
    retryCount, setRetryCount,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isSavingTitle, setIsSavingTitle,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    lastSaveTime, setLastSaveTime,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isRenderingMessages, setIsRenderingMessages,
    // 核心状态
    messages,
    loading,
    waitTime,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isRetrying, setIsRetrying,
    isPaused, setIsPaused,
    sessionId,
    sessionTitle, setSessionTitle,
    sessionVersion, setSessionVersion,
    titleLocked, setTitleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    lastSavedTitle, setLastSavedTitle,
    // Refs
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    waitTimerRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    messagesEndRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    messagesCountRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    messagesRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    replyUserMessageIdRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    displayBufferRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isPausedRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    executionStepsRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    streamingContentRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    streamingStepsRef,
    userScrolledUpRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    lastScrollTimeRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isLoadingHistoryRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    logFlagsRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    hasReceivedInterruptEventRef,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    interruptInProgressRef,
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

  // 解构chatPersistence - 暂无需要解构的内容

  // 【小沈 2026-04-24】P0-3优化：使用useLoadingMessage Hook管理loading
  const { show: showLoading, hide: hideLoading } = useLoadingMessage({ duration: 0 });

  // ===== 【小资优化 2026-04-13】流式性能优化 =====
  // 2. 滚动控制ref
  const SCROLL_THRESHOLD = 150;  // ChatGPT实践：超过150px认为用户主动滚动
  const SCROLL_INTERVAL = 100;   // 滚动节流间隔
  // ===== 【小资优化 2026-04-13】结束 =====

  // 【小沈 2026-04-24】P1修复：使用useCallback包装scrollToBottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesEndRef]);

  // ===== 【小资优化 2026-04-13】优化滚动函数 =====
  const scrollToBottomIfNeeded = useCallback(() => {
    const now = Date.now();
    
    // ⭐ 节流：100ms内只滚动一次
    if (now - lastScrollTimeRef.current < SCROLL_INTERVAL) {
      return;
    }
    
    // ⭐ 检查：用户主动滚动时不自动滚动
    if (userScrolledUpRef.current) {
      return;
    }
    
    lastScrollTimeRef.current = now;
    scrollToBottom();
  }, [SCROLL_INTERVAL, scrollToBottom, lastScrollTimeRef, userScrolledUpRef]);
  // ===== 【小资优化 2026-04-13】结束 =====

  // 滚动到底部的增强版本，确保页面渲染完成后再滚动
  const scrollToBottomDelayed = () => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100); // 延迟100ms确保DOM更新完成
  };

  // ⭐ 同步 isPaused 状态到 ref，供回调中使用
  useEffect(() => {
    isPausedRef.current = isPaused;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPaused]);

  // ===== 【小资优化 2026-04-13】使用节流滚动
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    scrollToBottomIfNeeded();
  }, [messages, currentResponse, executionSteps, scrollToBottomIfNeeded]);

  // 【小查修复】同步executionSteps到ref，确保onComplete能获取最新值
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    executionStepsRef.current = executionSteps;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionSteps]);

  // ===== 【小资优化 2026-04-13】滚动位置监听 =====
  useEffect(() => {
    const container = messagesEndRef.current?.parentElement;
    if (!container) return;
    
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // 距离底部超过150px认为是用户主动滚动
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      userScrolledUpRef.current = distanceFromBottom > SCROLL_THRESHOLD;
    };
    
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // ===== 【小资优化 2026-04-13】结束 =====

  // 当页面从隐藏状态变为显示时也自动滚动到底部
  // 【小沈修复 2026-04-23】同时检查SSE连接状态，确保按钮状态正确
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // 延迟滚动以确保内容已渲染
        scrollToBottomDelayed();
        
        // 【Bug修复】页面恢复显示时，检查SSE连接状态
        // 问题：浏览器可能降频导致状态丢失，按钮消失
        // 解决：如果正在流式接收但状态异常，记录日志供调试
        console.log(`[visibilitychange] 当前状态: isReceiving=${isReceiving}, hasExecutionSteps=${executionSteps.length > 0}`);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, currentResponse, executionSteps, isReceiving]);

  // 【小沈 2026-04-24】P2优化：提取beforeunload保存逻辑为独立函数
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

  // 【小沈 2026-04-24】P2优化：使用useBeforeUnload Hook统一管理
  useBeforeUnload({
    shouldSave: !!isReceiving && !!sessionId,
    saveData: handleSaveBeforeUnload,
    showDialog: true,
    dialogMessage: '正在接收消息，确定要离开吗？',
  });

  // 组件卸载前保存状态（用于路由切换/F5刷新/Ctrl+F5强制刷新场景）
  // 【问题2修复 2026-03-18】增加beforeunload事件监听，刷新时也能保存数据
  useEffect(() => {
    // 清理可能残留的loading消息
    return () => {
      message.destroy("session-load");
      console.log("🔄 组件卸载（页面即将跳转或关闭）");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================
  // 会话状态持久化
  // ============================================
  
  // 【小强修复 2026-03-17】保存状态前确保 SSE 数据已处理完成
  // 问题：页面隐藏时 saveState() 可能还在接收 final 步骤，导致缓存中缺少 final
  // 修复：在 onComplete 回调中 SSE 完成时立即保存，确保 final 步骤已包含
  // 【小沈 2026-04-22】Phase 6: 使用chatPersistence版本
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { saveStateWithSSECheck, saveState } = chatPersistence;

  // 【小沈 2026-04-24】P2优化：智能状态验证轮询（带前瞻性策略）
  const [lastValidationTime, setLastValidationTime] = useState(0);
  const VALIDATION_INTERVAL = 5 * 60 * 1000; // 5分钟验证间隔
  const FAILED_RETRY_DELAY = 30 * 1000; // 失败后30秒再试

useEffect(() => {
    if (!sessionId || !isInitialized) return;

    const validateAndSyncState = async () => {
      const now = Date.now();
      try {
        // 【前瞻性策略1】页面隐藏时不验证，节省资源
        if (document.hidden) {
          console.log('[状态验证] 页面隐藏，跳过验证');
          return;
        }

        // 【前瞻性策略2】距离上次验证时间太短不验证
        if (now - lastValidationTime < VALIDATION_INTERVAL) {
          console.log('[状态验证] 距上次验证时间太短，跳过');
          return;
        }

        console.log('[状态验证] 开始验证...');
        const sessionData = await sessionApi.getSessionMessages(sessionId);

        // 获取后端返回的正确标题
        const backendTitle = sessionData.title || "会话";

        // 如果前端标题与后端不一致，强制同步
        if (backendTitle !== sessionTitle && backendTitle !== "会话") {
          console.warn("🔄 标题不一致，强制同步:", {
            frontend: sessionTitle,
            backend: backendTitle,
          });
          setSessionTitle(backendTitle);
        }

        // 验证消息数量
        if (sessionData.messages && sessionData.messages.length > 0) {
          const frontendMsgCount = messages.filter(
            (m) => m.role !== "system"
          ).length;
          const backendMsgCount = sessionData.messages.length;

          if (Math.abs(frontendMsgCount - backendMsgCount) > 2) {
            console.warn("🔄 消息数量差异较大，建议刷新页面");
          }
        }

        setLastValidationTime(now);
        console.log('[状态验证] 验证完成');
      } catch (error) {
        console.warn("[状态验证] 失败:", error);
        // 【前瞻性策略3】失败后延长下次验证时间
        setLastValidationTime(now - VALIDATION_INTERVAL + FAILED_RETRY_DELAY);
      }
    };

    // 【前瞻性策略4】页面可见性变化时立即验证
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        validateAndSyncState();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // 初始验证
    validateAndSyncState();

    // 定时验证（延长到5分钟）
    const intervalId = setInterval(validateAndSyncState, VALIDATION_INTERVAL);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, sessionTitle, messages, isInitialized, lastValidationTime]);

  // 全局快捷键 - 前端小新代修改 UX-G02: 全局快捷键
  // 【小强修复 2026-03-31】Ctrl+Enter快捷键已移至ChatInput组件内部处理
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================
  // 加载历史会话
  // 【小强 2026-04-22】Phase 7.6: 使用chatSession.initializeSession替代原useEffect
  // ============================================
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
}, [searchParams, showLoading, hideLoading]);

  // 【小沈 2026-04-24】P0-3优化：组件卸载时清理loading
  useEffect(() => {
    return () => {
      hideLoading("session-load");
    };
  }, [hideLoading]);

  // ============================================================

  /**
   * 新建会话 - 使用chatSession版本
   * 迁移到 useChatSession Hook
   */
  const handleNewSession = () => {
    console.log("🔍 [handleNewSession] 按钮被点击");
    chatSession.handleNewSession(0);
  };

  /**
   * 清空对话 - 使用chatSession版本
   * 迁移到 useChatSession Hook
   */
  const handleClear = () => {
    console.log("🔍 [handleClear] 清空对话按钮被点击");
    // 重置暂停状态，避免清空后新数据丢失
    setIsPaused(false);
    // 重置日志标记
    logFlagsRef.current = {
      chunkFirstDone: false,
      showStepsFalseDone: false,
      showStepsTrueDone: false,
    };
    chatSession.handleClear();
  };

  // ChatHeader回调 - 提取为useCallback优化性能
  const handleEditingStart = useCallback(() => {
    if (!editingTitle && sessionId) {
      setTitleInput(sessionTitle || "");
    }
    setEditingTitle(true);
  }, [editingTitle, sessionId, sessionTitle, setTitleInput, setEditingTitle]);

  const handleEditingCancel = useCallback(() => {
    setEditingTitle(false);
  }, [setEditingTitle]);

  // ChatToolbar回调 - 提取为useCallback优化性能
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
      styles={{ body: { padding: "0 4px 4px 4px" } }}
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
      {/* AI思考过程面板已移至MessageItem内部 - 前端小新代修改 */}

      {/* 【小沈 2026-04-21】使用MessageArea组件 */}
      <MessageArea
        messages={messages}
        showExecution={showExecution}
        sessionId={sessionId}
        sessionTitle={sessionTitle}
        useStream={useStream}
        isMessageListLoading={isMessageListLoading}
        messagesEndRef={messagesEndRef}
      />

      {/* 输入区域 - 【小强修复 2026-03-31】使用独立ChatInput组件隔离inputValue状态 */}
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
