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

import React, { useRef, useEffect, useCallback } from "react";
import { message, Card } from "antd";
import { useSearchParams } from "react-router-dom";
import { sessionApi, API_BASE_URL, taskControlApi } from "../../services/api";
import { handleError, handleApiError, ErrorType } from "../../utils/errorHandler";

// 【新增 2026-03-13】从独立文件导入类型和工具函数
import type { Message } from "../../types/chat";
import {
  debounce,
  loadHistoryMessages,
  loadLatestHistoryMessages,
  SESSION_EXPIRY_TIME,
  STORAGE_KEY,
} from "../../utils/chatHistory";

// 【新增 2026-03-13】从独立文件导入日志和消息提示函数
import { logUserSend } from "../../utils/chatLogger";
import { getClientInfo } from "../../utils/clientInfo";  // 【小沈 2026-03-24】获取客户端信息
import { checkNetworkConnection } from "../../utils/network";  // 【小强 2026-04-22】网络检查工具
import {
  showSaveError,
  showLoadSuccess,
  showNetworkError,
  showConflictError,
  showInfo,
  showRetryWarning,
  showTaskControlMessage,
  showTaskResultMessage,
  showTaskControlInfo,
  showNoActiveTaskWarning,
  showLoadRetryWarning,
  showLoadErrorWithKey,
} from "../../utils/chatMessages";

// 【小强修复 2026-03-31】独立输入框组件，隔离inputValue状态避免父组件重渲染
import ChatInput from "./ChatInput";

// 【小沈 2026-04-21】MessageArea组件拆分
import MessageArea from './MessageArea';

// 【小沈 2026-04-21】ChatHeader组件拆分
import ChatHeader from './ChatHeader';
// 【小沈 2026-04-21】ChatToolbar组件拆分
import ChatToolbar from './ChatToolbar';

// 【小强 2026-04-21】Hooks已创建，按方案2.1.7/2.2.7/2.3.5验证1：暂不使用
// 使用时导入：
import { useChatSession } from '../../hooks/chat/useChatSession';
import { useChatPersistence } from '../../hooks/chat/useChatPersistence';

// 【小强 2026-04-21】Phase 2 Task 2.2: 导入useChatState
import { useChatState } from '../../hooks/chat/useChatState';

// 【小沈 2026-04-22】Phase 3 Task 3.2: 导入useChatCallbacks
import { useChatCallbacks } from '../../hooks/chat/useChatCallbacks';

// 【小沈 2026-04-22】Phase 4: 导入useChatStreaming
import { useChatStreaming } from '../../hooks/chat/useChatStreaming';

// 【小强 2026-04-22】Phase 7.2: 导入useChatTaskControl
import { useChatTaskControl } from '../../hooks/chat/useChatTaskControl';

// 【小强 2026-04-12】Phase 2 P1级优化 - 消息列表useMemo优化（使用独立hook）
// import { useMessageListRender } from '../../hooks/useMessageListRender'; // 已移至MessageList组件内部

// 【小新 2026-03-13 代码拆分】类型和工具函数已提取到独立文件
// - 类型定义: src/types/chat.ts
// - 工具函数: src/utils/chatHistory.ts

/**

/**
 * NewChatContainer - 升级版对话容器
 *
 * 整合功能：
 * - Chat/index.tsx: 会话管理、安全检测、状态持久化
 * - ChatContainer: useSSE hook、ExecutionPanel、流式开关
 *
 * @author 小新
 * @version 3.0.0
 */
const NewChatContainer: React.FC = () => {
  // Phase 2: 使用useChatState统一管理状态
  const chatState = useChatState();
  const { 
    // 独立状态
    showExecution, setShowExecution, 
    useStream, setUseStream,
    isInitialized, setIsInitialized,
    saveStatus, setSaveStatus,
    sessionJumpLoading, setSessionJumpLoading,
    isMessageListLoading, setIsMessageListLoading,
    retryCount, setRetryCount,
    isSavingTitle, setIsSavingTitle,
    lastSaveTime, setLastSaveTime,
    isRenderingMessages, setIsRenderingMessages,
    // 核心状态
    messages, setMessages,
    loading, setLoading,
    waitTime, setWaitTime,
    isRetrying, setIsRetrying,
    isPaused, setIsPaused,
    sessionId, setSessionId,
    sessionTitle, setSessionTitle,
    sessionVersion, setSessionVersion,
    titleLocked, setTitleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    lastSavedTitle, setLastSavedTitle,
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
  
  const [searchParams] = useSearchParams();

// 【小沈 2026-04-22】Phase 3 Task 3.2: 使用useChatCallbacks获取回调
  const chatCallbacks = useChatCallbacks(chatState);

  // 【小沈 2026-04-22】Phase 4: 使用useChatStreaming替代useSSE
  const chatStreaming = useChatStreaming(
    chatState,
    chatCallbacks,
    { baseURL: API_BASE_URL, sessionId: sessionId }
  );

  // 【小沈 2026-04-22】Phase 5: 使用useChatSession管理会话生命周期
  const chatSession = useChatSession(chatState, chatStreaming);

  // 【小沈 2026-04-22】Phase 6: 使用useChatPersistence管理持久化
  const chatPersistence = useChatPersistence(chatState, chatStreaming);

  // 【小强 2026-04-22】Phase 7.2: 使用useChatTaskControl管理任务控制
  const chatTaskControl = useChatTaskControl({
    // chatState
    setLoading,
    setIsPaused,
    interruptInProgressRef,
    hasReceivedInterruptEventRef,
    waitTimerRef,
    isPaused,
    isPausedRef,
    // chatStreaming
    serverTaskId: chatStreaming.serverTaskId,
    setIsReceiving: chatStreaming.setIsReceiving,
    disconnect: chatStreaming.disconnect,
    // session
    sessionId,
  });
  const { handleInterrupt, handleTogglePause } = chatTaskControl;
   
  // ===== 【小资优化 2026-04-13】流式性能优化 =====
  // 2. 滚动控制ref
  const SCROLL_THRESHOLD = 150;  // ChatGPT实践：超过150px认为用户主动滚动
  const SCROLL_INTERVAL = 100;   // 滚动节流间隔

  // 【小沈 2026-04-22】Phase 6: 使用chatPersistence版本的防抖保存
  const { saveMessagesToStorage } = chatPersistence;
  // ===== 【小资优化 2026-04-13】结束 =====

// 【小沈 2026-04-22】Phase 4: 使用chatStreaming（useChatStreaming Hook）
// 【小强 2026-04-22】Phase 7.1: 解构executeSend方法
  const {
    isReceiving,
    setIsReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    serverTaskId,
    executeSend,
  } = chatStreaming;

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

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
  }, []);
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
  }, [isPaused]);

  // ===== 【小资优化 2026-04-13】使用节流滚动
  useEffect(() => {
    scrollToBottomIfNeeded();
  }, [messages, currentResponse, executionSteps, scrollToBottomIfNeeded]);

  // 【小查修复】同步executionSteps到ref，确保onComplete能获取最新值
  useEffect(() => {
    executionStepsRef.current = executionSteps;
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
  }, []);
  // ===== 【小资优化 2026-04-13】结束 =====

  // 【小新第二修复 2026-03-02】同步跟踪消息数量，用于保存消息时获取准确的值
  // 【小查修复2026-03-14】同时同步messagesRef，避免visibilitychange useEffect频繁重新注册
  // 【问题2修复 2026-03-18】当正在接收SSE数据时，持续保存到sessionStorage（页面隐藏期间也能保存）
  useEffect(() => {
    messagesCountRef.current = messages.length;
    messagesRef.current = messages;
    
    if (sessionId) {
      // ⭐ 使用debounce函数延迟保存（500ms）
      saveMessagesToStorage.current(messages, sessionId, sessionTitle, isPaused, isReceiving);
    }
  }, [messages, sessionId, sessionTitle, isPaused, isReceiving]);

  // 当页面从隐藏状态变为显示时也自动滚动到底部
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // 延迟滚动以确保内容已渲染
        scrollToBottomDelayed();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [messages, currentResponse, executionSteps]);

  // 组件卸载前保存状态（用于路由切换/F5刷新/Ctrl+F5强制刷新场景）
  // 【问题2修复 2026-03-18】增加beforeunload事件监听，刷新时也能保存数据
  useEffect(() => {
    // beforeunload：页面刷新/关闭前触发
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      // 当正在接收SSE数据时，同步保存最新状态
      if (isReceiving && sessionId) {
        console.log("💾 [beforeunload] 刷新前保存状态, steps:", executionStepsRef.current.length);
        
        // 同步保存最新数据（从executionStepsRef获取最新steps）
        // 【修复 2026-03-18】使用messagesRef.current获取最新messages，而不是闭包中的messages
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
        // 【小强修复 2026-04-08】添加try-catch防止QuotaExceededError崩溃
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
        
        // 提示浏览器不要关闭（可选）
        e.preventDefault();
        e.returnValue = '';
      }
    };
    
    // 添加事件监听
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      // 销毁可能残留的loading消息
      message.destroy("session-load");
      
      // 移除事件监听
      window.removeEventListener('beforeunload', handleBeforeUnload);
      
      console.log("🔄 组件卸载（页面即将跳转或关闭）");
    };
  }, []);

  // ============================================
  // 会话状态持久化
  // ============================================
  
  // 【小强修复 2026-03-17】保存状态前确保 SSE 数据已处理完成
  // 问题：页面隐藏时 saveState() 可能还在接收 final 步骤，导致缓存中缺少 final
  // 修复：在 onComplete 回调中 SSE 完成时立即保存，确保 final 步骤已包含
  // 【小沈 2026-04-22】Phase 6: 使用chatPersistence版本
  const { saveStateWithSSECheck, saveState } = chatPersistence;

  const restoreState = () => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        // 🔴 修复：检查时间戳，避免恢复过时的状态（超过5分钟）
        const currentTime = Date.now();
        const savedTime = state.timestamp || 0;
        const timeDiff = currentTime - savedTime;
        // console.log("🕒 距离上次保存: " + (timeDiff/1000).toFixed(1) + "秒", "| 过期时间: 5分钟");

        // 只恢复5分钟内的状态
        if (timeDiff > SESSION_EXPIRY_TIME) {
          // console.log("🕒 会话状态已过期，跳过恢复");
          sessionStorage.removeItem(STORAGE_KEY);
          return false;
        }

        if (state.sessionId) {
          // ⭐ 小新修复 2026-03-07：检查缓存消息是否缺少 display_name，如果是则跳过恢复，从 API 重新加载
          // 【2026-04-08修复】如果缓存中没有messages（容量满时只保存了摘要），也从API重新加载
          if (!state.messages || state.messages.length === 0) {
            console.log("🕒 缓存中没有messages（可能容量满），从 API 重新加载");
            return false;
          }
          
          const hasDisplayName = state.messages?.some((m: any) => m.display_name);
          if (!hasDisplayName) {
            console.log("🕒 缓存消息缺少 display_name，跳过恢复，从 API 重新加载");
            sessionStorage.removeItem(STORAGE_KEY);
            return false;
          }
          
          setMessages(state.messages || []);
          setSessionId(state.sessionId);
          // 【小新第二修复 2026-03-02】从sessionStorage恢复时也更新ref
          currentSessionIdRef.current = state.sessionId;
          setSessionTitle(state.sessionTitle || "会话");

          // 恢复暂停/中断状态
          if (state.isPaused !== undefined) {
            setIsPaused(state.isPaused);
            isPausedRef.current = state.isPaused;
            console.log("🔄 恢复暂停状态:", state.isPaused);
          }
          // 注意：isReceiving 状态不需要恢复，因为页面切换回来后需要重新开始接收

          // 🔴 修复：根据保存的标记决定是否滚动到底部
          if (state.shouldScrollToBottom) {
            // 使用requestAnimationFrame确保DOM更新后再滚动
            requestAnimationFrame(() => {
              setTimeout(() => {
                scrollToBottomDelayed();
              }, 100);
            });
          } else if (state.scrollPosition !== undefined) {
            // 恢复之前的滚动位置
            setTimeout(() => {
              if (messagesEndRef.current?.parentElement) {
                messagesEndRef.current.parentElement.scrollTop =
                  state.scrollPosition;
              }
            }, 100);
          }

          console.log("🔄 type=%s 恢复sessionStorage %s | msg=%d", new Date().toLocaleTimeString(), state.messages?.length);
          return true;
        }
      } catch (e) {
        console.warn("恢复会话状态失败:", e);
        sessionStorage.removeItem(STORAGE_KEY); // 🔴 修复：清除损坏的数据
      }
    }
    return false;
  };

  // 页面可见性变化时保存和恢复状态
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        /**
         * 【小新修改 2026-03-16】
         * 页面隐藏时保存数据 - 解决SSE断开导致数据丢失问题
         * 
         * 问题背景：
         * - 页面切换（最小化/切换标签页）时，SSE可能断开，onComplete不触发
         * - 导致execution_steps和content丢失
         * 
         * 解决方案：
         * 1. 保存到sessionStorage
         * 2. 不断开SSE连接，让fetch自然进行
         * 
         * 【小强修复 2026-03-18】删除数据库保存，因为sessionStorage已经足够
         * 
         * 注意：页面刷新（F5/Ctrl+F5）由beforeunload处理（见第726行）
         */
        
        // 保存到sessionStorage（带 SSE 检查）
        saveStateWithSSECheck();
        
        // 不断开SSE连接，让fetch自然进行
        //   disconnect();
        // }
      } else {
        /**
         * 【小新修改 2026-03-16】
         * 页面恢复时强制从sessionStorage恢复 - 解决Debug模式下数据丢失问题
         * 
         * 问题背景：
         * - 第971行有 `!DEBUG_LOAD_FROM_API` 判断
         * - Debug模式开启时（DEBUG_LOAD_FROM_API = true），不会从sessionStorage恢复
         * - 直接从API加载，导致页面隐藏时的数据丢失
         * 
         * 解决方案：
         * - 移除 `!DEBUG_LOAD_FROM_API` 检查
         * - 强制从sessionStorage恢复，确保数据不丢失
         * - 只有在sessionStorage无效时才从API加载
         */
        // 页面重新可见时：不再重新请求API，避免覆盖当前消息
        // 改为从sessionStorage恢复状态，如果缓存有效的话
        
        // 【小新修复 2026-03-14】强制销毁可能残留的loading消息
        message.destroy("session-load");
        setSessionJumpLoading(false);
        
        const urlSessionId = new URLSearchParams(window.location.search).get(
          "session_id"
        );
        // 修复：移除 !DEBUG_LOAD_FROM_API 检查，强制从sessionStorage恢复
        if (urlSessionId && urlSessionId === sessionId) {
          // 先尝试从缓存恢复（忽略Debug模式检查）
          const saved = sessionStorage.getItem(STORAGE_KEY);
          if (saved) {
            try {
              const state = JSON.parse(saved);
              const currentTime = Date.now();
              const savedTime = state.timestamp || 0;
              const timeDiff = currentTime - savedTime;
              // console.log("🕒 距离上次保存: " + (timeDiff/1000).toFixed(1) + "秒", "| 过期时间: 5分钟");
              
              // 缓存有效（5分钟内），且当前有消息，则恢复缓存状态
              if (timeDiff <= SESSION_EXPIRY_TIME && state.messages && state.messages.length > 0) {
                // console.log("🔄 从缓存恢复会话状态，消息数:", state.messages.length, "isReceiving:", state.isReceiving);
                
                // 【问题2修复 2026-03-18】如果页面隐藏时SSE还在接收数据（state.isReceiving=true）
                // sessionStorage保存的可能不是最新steps，需要从API获取最新数据
                
                // 【小强增强防御 2026-04-18】防止由于浏览器节流等原因导致旧缓存倒灌覆盖新内存
                const memMsgs = messagesRef.current;
                const cacheMsgs = state.messages;
                
                let shouldRestore = true;
                if (memMsgs.length > 0 && cacheMsgs.length > 0) {
                  const lastMemMsg = memMsgs[memMsgs.length - 1];
                  const lastCacheMsg = cacheMsgs[cacheMsgs.length - 1];
                  
                  // 如果内存里的消息数更多，或者最后一条消息包含更多的执行步骤，则拒绝被旧缓存覆盖
                  if (memMsgs.length > cacheMsgs.length) {
                    shouldRestore = false;
                  } else if (lastMemMsg.role === 'assistant' && lastCacheMsg.role === 'assistant') {
                    const memSteps = lastMemMsg.executionSteps?.length || 0;
                    const cacheSteps = lastCacheMsg.executionSteps?.length || 0;
                    // 内存步骤比缓存多，或内存已结束流式而缓存还在流式中
                    if (memSteps > cacheSteps || (!lastMemMsg.isStreaming && lastCacheMsg.isStreaming)) {
                      shouldRestore = false;
                    }
                  }
                }
                
                if (shouldRestore) {
                  // 正常恢复
                  setMessages(state.messages);
                  if (state.sessionTitle) {
                    setSessionTitle(state.sessionTitle);
                  }
                } else {
                  console.log('🛡️ [restoreState] 内存数据比缓存更新，跳过恢复防止数据倒灌 (内存 steps=' + (memMsgs[memMsgs.length - 1]?.executionSteps?.length || 0) + ', 缓存 steps=' + (cacheMsgs[cacheMsgs.length - 1]?.executionSteps?.length || 0) + ')');
                }
                // 恢复暂停状态
                if (state.isPaused !== undefined) {
                  setIsPaused(state.isPaused);
                  isPausedRef.current = state.isPaused;
                  console.log("🔄 恢复暂停状态:", state.isPaused);
                }
                // 滚动到底部
                scrollToBottomDelayed();
                return; // 不再请求API
              }
            } catch (e) {
              console.warn("恢复缓存失败:", e);
            }
          }
          
          // 缓存无效或为空时，才从API加载（仅首次加载时）
          // 【小查修复】添加 isInitialized 和 isLoadingHistoryRef 检查，避免重复调用
          // 【小查修复2026-03-14】使用messagesRef.current避免依赖messages
          if (messagesRef.current.length === 0 && !isInitialized && !isLoadingHistoryRef.current) {
            console.log("🔄 首次加载，从API获取会话数据");
            isLoadingHistoryRef.current = true; // 加锁
            // 【小强优化 2026-04-08】API请求前显示Loading
            setIsRenderingMessages(true);
            setTimeout(async () => {
              try {
                // 调用统一的历史消息加载函数
                const result = await loadHistoryMessages(sessionId);
              if (result) {
                setMessages(result.messages);
                // 【小强修复 2026-04-08】补充sessionId设置，与其他位置保持一致
                setSessionId(result.sessionId);
                currentSessionIdRef.current = result.sessionId;
                setSessionTitle(result.title);
                if (result.version !== undefined) {
                  setSessionVersion(result.version);
                }
                if (result.title_locked !== undefined) {
                  setTitleLocked(result.title_locked);
                }
                // 渲染完成后关闭Loading和骨架屏
                requestAnimationFrame(() => {
                  setIsRenderingMessages(false);
                  setIsMessageListLoading(false);
                });
              }
              } catch (e) {
                console.warn("从API加载会话失败:", e);
                setIsRenderingMessages(false); // 关闭Loading
              }
              isLoadingHistoryRef.current = false; // 解锁
            }, 100);
          }
        }
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [sessionId, isReceiving]);  // 【小查修复2026-03-14】移除messages依赖，使用messagesRef.current

  // P1级别优化：状态验证和同步机制
  useEffect(() => {
    if (!sessionId || !isInitialized) return;

    const validateAndSyncState = async () => {
      try {
        // 验证前端状态与后端一致性
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
      } catch (error) {
        console.warn("状态验证失败:", error);
        // 状态验证失败不影响用户体验，静默处理
      }
    };

    // 每2分钟验证一次状态一致性
    const intervalId = setInterval(() => {
      validateAndSyncState();
    }, 2 * 60 * 1000);

    return () => clearInterval(intervalId);
  }, [sessionId, sessionTitle, messages, isInitialized]);

  // 全局快捷键 - 前端小新代修改 UX-G02: 全局快捷键
  // 【小强修复 2026-03-31】Ctrl+Enter快捷键已移至ChatInput组件内部处理
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
  }, []);

  // 注意：checkNetworkConnection 已迁移到 utils/network.ts

  // ============================================
  // 统一的标题管理函数
  // ============================================


  // ⭐ 确保标题持久化到后端（带防抖、重试、版本冲突处理）
  const ensureTitlePersisted = async (sessionId: string, title: string) => {
    if (!sessionId || !title.trim()) return;

    // ⭐ 防抖检查：标题未变化时跳过保存
    if (title === lastSavedTitle) {
      console.log("标题未变化，跳过保存");
      return;
    }

    // ⭐ 防抖检查：正在保存时跳过重复请求
    if (saveStatus === "saving") {
      console.log("正在保存中，跳过重复请求");
      return;
    }

    const retryKey = `title-save-${sessionId}`;
    const currentRetry = retryCount[retryKey] || 0;

    try {
      setSaveStatus("saving");
      setIsSavingTitle(true);

      // 如果标题不是默认标题，保存到后端
      if (title !== "新会话" && title !== "会话") {
        // ⭐ 直接使用状态中的版本号
        const response = await sessionApi.updateSession(
          sessionId,
          title.trim(),
          sessionVersion
        );

        // ⭐ 更新本地版本号
        if (response.version) {
          setSessionVersion(response.version);
        }

        // ⭐ 更新最后保存的标题
        setLastSavedTitle(title);

        console.log(
          "💾 标题持久化成功:",
          sessionId,
          title,
          "版本:",
          sessionVersion
        );
      }

      // 更新本地sessionStorage
      saveState();

      // 保存成功
      setSaveStatus("saved");
      setIsSavingTitle(false);
      setLastSaveTime(Date.now());
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

      // 2秒后恢复到idle状态
      setTimeout(() => {
        setSaveStatus("idle");
      }, 2000);
      } catch (error: any) {
        console.warn("标题持久化失败:", error);

        // ⭐ 处理409版本冲突错误
        if (error?.response?.status === 409) {
          // 使用统一错误处理中心
          handleApiError(error, { showError: false });
          
          // 显示同步提示 - 使用 chatMessages 工具
          const errorMsg = error.response.data?.detail || "版本冲突，该会话已被其他人修改";
          showConflictError(errorMsg);

        // ⭐ 从服务器重新获取最新数据
        try {
          const sessionData = await sessionApi.getSessionMessages(sessionId);
          if (sessionData.version) {
            setSessionVersion(sessionData.version);
          }
          if (sessionData.title) {
            setSessionTitle(sessionData.title);
          }
          if (sessionData.title_locked !== undefined) {
            setTitleLocked(sessionData.title_locked);
          }
          // 【小新第二修复 2026-03-02】title_source 由后端动态计算，前端不需要读取

          showInfo("已自动同步最新数据，请重试");
        } catch (syncError) {
          console.error("同步最新数据失败:", syncError);
        }

        setSaveStatus("error");
        setIsSavingTitle(false);
        return;
      }

      // 其他错误：重试机制 - 最多3次
      setSaveStatus("error");
      setIsSavingTitle(false);

      // 使用统一错误处理中心处理错误
      handleApiError(error);

      if (currentRetry < 3) {
        const newRetry = currentRetry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
        showRetryWarning(newRetry, 3);

        // 延迟1秒后重试
        setTimeout(() => {
          debouncedSaveTitle(sessionId, title);
        }, 1000);
      } else {
        // 超过重试次数，显示错误
        showSaveError("保存失败，请检查网络后重试");
        setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
      }
    }
  };

  // ⭐ 防抖版本的保存标题函数
  const debouncedSaveTitle = useCallback(
    debounce(async (sessionId: string, title: string) => {
      await ensureTitlePersisted(sessionId, title);
    }, 1000),
    []
  );

  // ============================================
  // 加载历史会话
  // ============================================
  useEffect(() => {
    const loadSession = async () => {
      const urlSessionId = searchParams.get("session_id");

      // 检测是否是强制刷新（Ctrl+F5或Cmd+Shift+R）
      // 使用最新的PerformanceNavigationTiming API（Navigation Timing Level 2标准）
      // 兼容性：Chrome/Edge/Firefox/Safari均支持（2021年10月起Baseline）
      const navigationEntry = performance.getEntriesByType("navigation")?.[0] as PerformanceNavigationTiming | undefined;
      const isReload = navigationEntry?.type === "reload";
      
      if (isReload) {
        console.log("🔄 检测到刷新操作，清除sessionStorage缓存");
        sessionStorage.removeItem(STORAGE_KEY);
      }

      // 🔴 修复1: URL参数绝对优先 - 清除旧的sessionStorage
      if (urlSessionId) {
        // P1级别优化：添加会话跳转加载状态
        setSessionJumpLoading(true);
        // 【小新修复 2026-03-14】显示loading前先销毁旧的，避免重复
        message.destroy("session-load");
        message.loading({
          content: "正在加载会话...",
          key: "session-load",
          duration: 0,
        });

        // 🔴 修复：不要清除sessionStorage
        // 原因：用户从历史页面点击会话后，如果清除了sessionStorage
        // 返回聊天页面时无法恢复之前的会话状态
        // 改为：加载URL会话后，也会更新sessionStorage（在下面代码中）
        // sessionStorage.removeItem(STORAGE_KEY);

        const retryKey = `session-load-${urlSessionId}`;
        const currentRetry = retryCount[retryKey] || 0;

        // 【小查修复】如果正在加载中，跳过此次调用
        if (isLoadingHistoryRef.current) {
          console.log("⏭️ 正在加载中，跳过重复调用");
          setSessionJumpLoading(false);
          message.destroy("session-load");
          return;
        }

        isLoadingHistoryRef.current = true; // 加锁
        // 【小强优化 2026-04-08】API请求前显示Loading，避免空白等待
        setIsRenderingMessages(true);
        try {
          // 调用统一的历史消息加载函数
          const result = await loadHistoryMessages(urlSessionId);
          if (result) {
            setSessionId(result.sessionId);
            // 【小新第二修复 2026-03-02】加载会话时也更新ref
            currentSessionIdRef.current = result.sessionId;
            setMessages(result.messages);
            setSessionTitle(result.title);
            if (result.version !== undefined) {
              setSessionVersion(result.version);
            }
            if (result.title_locked !== undefined) {
              setTitleLocked(result.title_locked);
            }
            // 加载成功
            setSessionJumpLoading(false);
            showLoadSuccess("会话加载成功");
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
            // 【小新修复 2026-03-14】销毁loading消息，避免一直显示
            message.destroy("session-load");
            // 渲染完成后关闭Loading和骨架屏
            requestAnimationFrame(() => {
              setIsRenderingMessages(false);
              setIsMessageListLoading(false);
            });

            console.log(
              "🔵 从URL加载会话:",
              urlSessionId,
              "标题:",
              sessionTitle,
              "版本:",
              sessionVersion
            );
            isLoadingHistoryRef.current = false; // 解锁
            return;
          } else {
            // 【小新第四修复 2026-03-02 15:45:30】URL会话加载失败（没有消息），清理状态避免混乱
            console.warn(
              "🔴 URL会话没有消息，清理状态并跳过加载:",
              urlSessionId
            );
            setSessionId(null);
            currentSessionIdRef.current = null; // 同步清理ref
            setMessages([]);
            setSessionTitle("新会话");
            setSessionVersion(1);
            setTitleLocked(false);
            setSessionJumpLoading(false);
            message.destroy("session-load");
            setIsRenderingMessages(false); // 关闭Loading
            isLoadingHistoryRef.current = false; // 解锁
            return;
          }
        } catch (error) {
          console.warn("加载URL会话失败:", error);
          setIsRenderingMessages(false); // 关闭Loading
          isLoadingHistoryRef.current = false; // 解锁

          // 重试机制 - 最多3次
          if (currentRetry < 3) {
            const newRetry = currentRetry + 1;
            setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
            showLoadRetryWarning(newRetry, 3, "session-load");

            // 延迟1秒后重试
            setTimeout(() => {
              loadSession();
            }, 1000);
          } else {
            // 超过重试次数，显示错误
            setSessionJumpLoading(false);
            isLoadingHistoryRef.current = false; // 解锁
            showLoadErrorWithKey("加载会话失败，请检查网络后重试", "session-load");
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
          }
        }
      }

      // 🔴 修复3: 只有在没有URL参数时才考虑sessionStorage
      if (!urlSessionId) {
        const restored = restoreState();
        if (restored) {
          console.log("🟢 从缓存恢复会话状态");
          // 如果是从缓存恢复，也要关闭加载状态
          setSessionJumpLoading(false);
          isLoadingHistoryRef.current = false; // 解锁
          message.destroy("session-load");
          return;
        }
      }

      // 【小新第二修复 2026-03-02】只有在没有URL参数时才加载最近会话
      if (urlSessionId) {
        console.warn("🔴 有URL参数，不加载最近会话:", urlSessionId);
        setSessionJumpLoading(false);
        message.destroy("session-load");
        return;
      }

      // 🔴 修复4: 如果都没有，加载最近的会话
      // 【小查修复】添加 isLoadingHistoryRef 检查，避免重复调用
      if (isLoadingHistoryRef.current) {
        console.log("⏭️ 正在加载中，跳过重复调用");
        setSessionJumpLoading(false);
        setIsInitialized(true);
        message.destroy("session-load");
        return;
      }
      
      isLoadingHistoryRef.current = true; // 加锁
      // 【小强优化 2026-04-08】API请求前显示Loading
      setIsRenderingMessages(true);
      try {
        const result = await loadLatestHistoryMessages();
        if (result) {
          setSessionId(result.sessionId);
          // 【小新第二修复 2026-03-02】加载最近会话时也更新ref
          currentSessionIdRef.current = result.sessionId;
          setSessionTitle(result.title);
          if (result.version !== undefined) {
            setSessionVersion(result.version);
          }
          if (result.title_locked !== undefined) {
            setTitleLocked(result.title_locked);
          }
          
          setMessages(result.messages);
          // 渲染完成后关闭Loading和骨架屏
          requestAnimationFrame(() => {
            setIsRenderingMessages(false);
            setIsMessageListLoading(false);
          });
          
          console.log(
            "🟡 加载最近会话:",
            result.sessionId,
            "标题:",
            result.title,
            "版本:",
            result.version
          );
        } else {
          // 如果没有获取到会话，显示提示信息
          console.log("🟡 没有找到任何会话，显示新会话界面");
          setSessionTitle("新会话");
          setMessages([]);
          setSessionId(null);
          setIsRenderingMessages(false); // 关闭Loading
        }

        // 关闭加载状态
        setSessionJumpLoading(false);
        isLoadingHistoryRef.current = false; // 解锁
        message.destroy("session-load");
      } catch (error) {
        console.warn("加载最近会话失败:", error);
        setIsRenderingMessages(false); // 关闭Loading
        // 即使失败也关闭加载状态
        setSessionJumpLoading(false);
        isLoadingHistoryRef.current = false; // 解锁
        message.destroy("session-load");
      }

      // 标记初始化完成
      setIsInitialized(true);
    };

    loadSession();
  }, [searchParams]);

// ============================================
  // 消息发送逻辑
  // ============================================

  /**
   * 执行流式消息发送（使用useChatStreaming.executeSend）
   * 【小强 2026-04-22】Phase 7.1: executeStreamSend已迁移到useChatStreaming.executeSend
   */
// 注意：executeSend方法已迁移到useChatStreaming hook
  // 注意：handleInterrupt和handleTogglePause已迁移到useChatTaskControl hook
  /**
   * 发送消息（带安全检测v2.0）
   * 【小强修复 2026-03-31】改为接收messageContent参数，不再依赖inputValue状态
   */
  const handleSend = async (messageContent: string) => {
      console.log("🔍 [handleSend] 函数开始执行");
      console.log("  messageContent:", messageContent);
      console.log("  loading:", loading);
      
      if (!messageContent.trim() || loading) return;

      // 【小新修复 2026-03-16】删除hasSavedStartMessageRef，不再需要防止重复保存
      // 后端已自动处理assistant消息创建
      
      // 🔴 修复：添加输入长度限制和验证
     if (messageContent.trim().length > 5000) {
       // 使用统一错误处理中心
       handleError({ message: "消息过长，请精简到5000字符以内", error_type: ErrorType.CONTENT_TOO_LONG });
       return;
     }

     // 🔴 修复：网络连接检查 - 移除过早的setLoading(false)
     setLoading(true);
try {
        console.log("🔍 [handleSend] 开始检查网络连接...");
        const isNetworkOK = await checkNetworkConnection(API_BASE_URL);
        if (!isNetworkOK) {
          console.error("❌ [handleSend] 网络连接异常");
          showNetworkError();
          setLoading(false);
          // ⭐ 停止等待计时器
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }
          setWaitTime(0);
          return;
        }
       console.log("✅ [handleSend] 网络连接正常");
     } catch (error) {
       console.warn("⚠️ [handleSend] 网络检查异常:", error);
     }

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      try {
        const newSession = await sessionApi.createSession(
          messageContent.trim().substring(0, 50)
        );
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        // 【小新第二修复 2026-03-02】保存到ref，确保onComplete时使用正确的ID
        currentSessionIdRef.current = currentSessionId;
        console.log("创建新会话:", currentSessionId);
      } catch (error) {
        // 使用统一错误处理中心 - 创建会话失败
        handleError(error, { source: "api" });
        console.error("创建会话失败:", error);
        return; // 🔴 修复：创建会话失败时停止发送
      }
    } else {
      // 【小新第二修复 2026-03-02】已有会话时也保存到ref
      currentSessionIdRef.current = currentSessionId;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: messageContent.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);

    // ========== 红色开始标志 ==========
    logUserSend(userMessage.content);
    // ==================================

    // 【小强 2026-04-20】移除前端安全检测，直接发送消息
    // 安全检测完全由后端处理，后端返回error步骤时前端会正确显示
    // 【小强 2026-04-22】Phase 7.1: 使用chatStreaming.executeSend替代executeStreamSend
    await executeSend(userMessage);
  };

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
          onEditingStart={() => {
            if (!editingTitle && sessionId) {
              setTitleInput(sessionTitle || "");
            }
            setEditingTitle(true);
          }}
onEditingCancel={() => {
            setEditingTitle(false);
          }}
        />
      }
      extra={
        <ChatToolbar
          useStream={useStream}
          showExecution={showExecution}
          onNewSession={handleNewSession}
          onClear={handleClear}
          onToggleStream={(checked) => {
            console.log("🔍 [流式开关] 被点击，新状态:", checked);
            setUseStream(checked);
            if (!checked) {
              setShowExecution(false);
            }
          }}
          onToggleExecution={() => {
            console.log("🔍 [显示过程] 按钮被点击");
            setShowExecution(!showExecution);
          }}
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
        isReceiving={isReceiving}
        useStream={useStream}
        isMessageListLoading={isMessageListLoading}
        messagesEndRef={messagesEndRef}
        userScrolledUpRef={userScrolledUpRef}
        scrollToBottomIfNeeded={scrollToBottomIfNeeded}
        scrollToBottomDelayed={scrollToBottomDelayed}
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
