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

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Input,
  Button,
  Card,
  Tag,
  Space,
  message,
  Tooltip,
} from "antd";
import {
  RobotOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  InfoCircleOutlined,
  LockOutlined,
} from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { sessionApi, API_BASE_URL, taskControlApi } from "../../services/api";
import { securityApi } from "../../services/api";
import DangerConfirmModal from "../DangerConfirmModal";
import SecurityAlert from "../SecurityAlert";
import { showSecurityNotification } from "../SecurityNotification";
import { getRiskLevel } from "../../types/security";
import { useSSE, ExecutionStep } from "../../utils/sse";
import { handleError, handleApiError, handleSSEError, ErrorType } from "../../utils/errorHandler";

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
import { logAIComplete, logAIError, logUserSend } from "../../utils/chatLogger";
import { getClientInfo } from "../../utils/clientInfo";  // 【小沈 2026-03-24】获取客户端信息
import {
  showSaveError,
  showLoadSuccess,
  showNetworkError,
  showSessionConflict,
  showConflictError,
  showInfo,
  showRetryWarning,
  showTaskControlMessage,
  showTaskResultMessage,
  showTaskControlInfo,
  showNoActiveTaskWarning,
  showLoadRetryWarning,
  showLoadErrorWithKey,
  showDangerCancelled,
  showNewSessionSuccess,
  showNewSessionRetryWarning,
  showNewSessionError,
  showTitleSaved,
  showTitleUpdated,
} from "../../utils/chatMessages";

// 【小强修复 2026-03-31】独立输入框组件，隔离inputValue状态避免父组件重渲染
import ChatInput from "./ChatInput";

// 【小强 2026-04-12】骨架屏组件
import { MessageListSkeleton } from "../Skeleton";

// 【小强 2026-04-12】Phase 2 P1级优化 - 消息列表useMemo优化（使用独立hook）
import { useMessageListRender } from '../../hooks/useMessageListRender';

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
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  // 【小强修复 2026-03-31】inputValue状态已移至ChatInput组件，避免每次按键触发整个组件重渲染
  const [loading, setLoading] = useState(false);
  // ⭐ 新增：等待时间计时器（正计时）
  const [waitTime, setWaitTime] = useState(0);
  const waitTimerRef = useRef<number | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);  // ⭐ 新增：重试状态
  const [isPaused, setIsPaused] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>("新会话");
  const [sessionVersion, setSessionVersion] = useState<number>(1); // ⭐ 新增：会话版本号
  const [titleLocked, setTitleLocked] = useState<boolean>(false); // ⭐ 新增：标题锁定状态
  // 【小新第二修复 2026-03-02】title_source 是后端根据 title_locked 动态计算的，
  // 不需要前端维护状态，直接使用 titleLocked 即可
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const [lastSavedTitle, setLastSavedTitle] = useState<string>(""); // ⭐ 新增：记录最后保存的标题
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // 【小新第二修复 2026-03-02】用于保存当前会话ID，确保onComplete时使用正确的ID
  const currentSessionIdRef = useRef<string | null>(null);
  // 【小新第二修复 2026-03-02】用于同步跟踪消息数量，确保保存时能获取准确值
  const messagesCountRef = useRef<number>(0);
  // 【小新第三修复 2026-03-02】用于同步存储pendingMessage，解决React闭包陷阱
  const pendingMessageRef = useRef<Message | null>(null);
  // 【小查修复2026-03-14】添加messagesRef避免visibilitychange useEffect频繁重新注册
  const messagesRef = useRef<Message[]>([]);
  // 【小新修复 2026-03-16】保存用户消息ID，用于AI消息关联
  const replyUserMessageIdRef = useRef<number | null>(null);

  // ⭐ 暂停功能缓冲区：暂存暂停期间接收的数据
  const displayBufferRef = useRef<any[]>([]);
  // ⭐ 暂停状态ref，用于在回调中同步访问
  const isPausedRef = useRef(false);
  // 【小查修复】用于在回调中获取最新的executionSteps
  const executionStepsRef = useRef<ExecutionStep[]>([]);

  // ===== 【小资优化 2026-04-13】流式性能优化 =====
  // 1. 流式累积ref - 不触发重渲染
  const streamingContentRef = useRef('');           // 累积AI回复内容
  const streamingStepsRef = useRef<ExecutionStep[]>([]); // 累积执行步骤
  const lastUpdateTimeRef = useRef(0);              // 上次更新时间
  const UPDATE_INTERVAL = 5;                        // 更新间隔5ms（实时更新）

  // 2. 滚动控制ref
  const userScrolledUpRef = useRef(false);
  const lastScrollTimeRef = useRef(0);
  const SCROLL_THRESHOLD = 150;  // ChatGPT实践：超过150px认为用户主动滚动
  const SCROLL_INTERVAL = 100;   // 滚动节流间隔

  // 3. debounce保存函数ref - 使用chatHistory.ts已存在的debounce
  const saveMessagesToStorage = useRef(
    debounce((msgs: Message[], sid: string, title: string, paused: boolean, receiving: boolean) => {
      if (receiving && sid) {
        const state = {
          messages: msgs,
          sessionId: sid,
          sessionTitle: title,
          timestamp: Date.now(),
          scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
          isPaused: paused,
          isReceiving: receiving,
        };
        
        try {
          const stateStr = JSON.stringify(state);
          // 原有4MB检查保留
          if (stateStr.length > 4 * 1024 * 1024) {
            const lightState = {
              sessionId: sid,
              sessionTitle: title,
              timestamp: Date.now(),
              messageCount: msgs.length,
              isPaused: paused,
              isReceiving: receiving,
            };
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lightState));
          } else {
            sessionStorage.setItem(STORAGE_KEY, stateStr);
          }
        } catch (e) {
          if (e instanceof DOMException && e.name === 'QuotaExceededError') {
            console.warn("⚠️ sessionStorage容量满，跳过保存");
          } else {
            console.error("保存会话状态失败:", e);
          }
        }
      }
    }, 500)  // 500ms防抖
  );
  // ===== 【小资优化 2026-04-13】结束 =====

  // 流式输出相关状态
  const [showExecution, setShowExecution] = useState(true);
  const [useStream, setUseStream] = useState(true); // 默认使用流式

  // 安全检测v2.0状态
  const [dangerModalVisible, setDangerModalVisible] = useState(false);
  const [dangerCommand, setDangerCommand] = useState("");
  const [dangerScore, setDangerScore] = useState(0);
  const [dangerMessage, setDangerMessage] = useState("");
  const [pendingMessage, setPendingMessage] = useState<Message | null>(null);
  const [_checkingDanger, setCheckingDanger] = useState(false);
  const [blockedCommand, setBlockedCommand] = useState<{
    command: string;
    score: number;
    message: string;
  } | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  // 【小查修复】使用 ref 存储加载状态，避免触发 useEffect
  const isLoadingHistoryRef = useRef(false);

  // 防重日志标记
  const logFlagsRef = useRef({
    chunkFirstDone: false,
    showStepsFalseDone: false,
    showStepsTrueDone: false,
  });

  // P1级别优化：新增状态变量
  type SaveStatus = "idle" | "saving" | "saved" | "error";
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [_sessionJumpLoading, setSessionJumpLoading] = useState(false);
  const [__isRenderingMessages, setIsRenderingMessages] = useState(false); // 渲染大量消息时的loading
  const [isMessageListLoading, setIsMessageListLoading] = useState(true); // 消息列表骨架屏状态
  const [retryCount, setRetryCount] = useState<Record<string, number>>({});
  const [_isSavingTitle, setIsSavingTitle] = useState(false);

  // 【小强 2026-04-12】Phase 2 P1级优化 - 消息列表渲染hook
  const messageElements = useMessageListRender({
    messages,
    showExecution,
    sessionId,
    sessionTitle,
  });

  const [_lastSaveTime, setLastSaveTime] = useState<number>(0);

  // SSE Hook配置（用于流式输出）
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    serverTaskId,
  } = useSSE(
    {
      baseURL: API_BASE_URL,
      sessionId: sessionId || "default-session",
    },
    // onStep - 收到执行步骤
    useCallback((step: ExecutionStep) => {
      // type 处理流程日志（解析 -> 存储 -> 渲染）
      console.log("📝 type=%s timestamp=%s", step.type, step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : 'N/A');
      // 只打印第一个chunk，减少日志
      if (step.type === "chunk") {
        if (!logFlagsRef.current.chunkFirstDone) {
          console.log("🔍 [onStep] 收到步骤, type= chunk (第一个)");
          logFlagsRef.current.chunkFirstDone = true;
        }
      }
      
      // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
      if (isPausedRef.current) {
        console.log("⏸️ [onStep] 暂停中，存入缓冲区, type:", step.type);
        displayBufferRef.current.push({ type: "step", step });
        return;
      }
      
      // ⭐ 累积到ref，不触发重渲染
      streamingStepsRef.current = [...streamingStepsRef.current, step];
      
      // 【修复】第一个step时streamingStepsRef还是空的，需要用当前step
      const currentSteps = streamingStepsRef.current.length > 0 
        ? streamingStepsRef.current 
        : [step];
      
      // ⭐ 50ms间隔更新，使用leading+trailing策略
      const now = Date.now();
      // 【修复 2026-04-16】当收到 final/error 步骤时，必须强制更新
      // 否则 isStreaming 不会被更新为 false，DynamicStatusDisplay 继续显示 "AI正在思考"
      const isFinalOrError = step.type === "final" || step.type === "error";
      const shouldUpdate = isFinalOrError 
        || now - lastUpdateTimeRef.current >= UPDATE_INTERVAL 
        || lastUpdateTimeRef.current === 0;  // 首次立即更新
      
      console.log("📝 [onStep] type=%s shouldUpdate=%s now=%s last=%s interval=%s isFinalOrError=%s", 
        step.type, shouldUpdate, now, lastUpdateTimeRef.current, UPDATE_INTERVAL, isFinalOrError);
      
      if (shouldUpdate) {
        lastUpdateTimeRef.current = now;
        // 使用函数式更新，确保获取最新state
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (!lastMessage || lastMessage.role !== "assistant") {
            // 【关键修复 2026-04-13】任何step都创建消息，不只是start
            // 因为后端可能直接发incident/retrying，不发start
            const extractedDisplay_name = step.display_name;
            let finalDisplay_name = extractedDisplay_name;
            if (!finalDisplay_name && step.model && step.provider) {
              finalDisplay_name = `${step.provider} (${step.model})`;
            }
            
            const newAssistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: "assistant",
              content: step.content || (step.type === "error" ? step.error_message || "执行出错" : "🤔 AI 正在思考..."),
              timestamp: step.timestamp ? new Date(step.timestamp) : new Date(),
              executionSteps: currentSteps,
              isStreaming: step.type !== "error" && step.type !== "final",
              model: step.model,
              provider: step.provider,
              display_name: finalDisplay_name,
            };
            // console.log("📝 [onStep] 创建新消息, isStreaming=", newAssistantMessage.isStreaming, "steps数=", currentSteps.length);
            return [...prev, newAssistantMessage];
          }
          
          // 更新最后一条消息的executionSteps
          // 【修复 2026-04-16】同时更新 isStreaming，确保 final/error 时显示正确状态
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            executionSteps: currentSteps,
            // final/error 时必须设置 isStreaming=false，停止 DynamicStatusDisplay
            isStreaming: step.type !== "error" && step.type !== "final" 
              ? lastMessage.isStreaming 
              : false,
          };
          return updated;
        });

        // 【小沈修复 2026-04-13】onStep更新后滚动到底部
        // 使用setTimeout确保DOM更新完成后再滚动
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }, 50);
      }
    }, []),

    // onChunk - 收到内容片段 【小资优化】使用50ms throttle
    useCallback((chunk: string, is_reasoning?: boolean) => {
      // 精简日志：调试通过，不再打印每个chunk
      
      // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
      if (isPausedRef.current) {
        console.log("⏸️ [onChunk] 暂停中，存入缓冲区");
        displayBufferRef.current.push({ type: "chunk", content: chunk, is_reasoning });
        return;
      }
      
      // ⭐ 累积到ref，不触发重渲染
      streamingContentRef.current += chunk;
      
      // ⭐ 50ms间隔更新，leading+trailing策略
      const now = Date.now();
      const shouldUpdate = now - lastUpdateTimeRef.current >= UPDATE_INTERVAL 
        || lastUpdateTimeRef.current === 0;  // 首次立即更新
      
      if (shouldUpdate) {
        lastUpdateTimeRef.current = now;
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (
            lastMessage &&
            lastMessage.role === "assistant" &&
            lastMessage.isStreaming
          ) {
            const updated = [...prev];
            const newIs_reasoning = is_reasoning ?? false;
            updated[updated.length - 1] = {
              ...lastMessage,
              content: streamingContentRef.current,
              is_reasoning: newIs_reasoning,
            };
            return updated;
          }
          return prev;
        });
      }
    }, []),
    // onComplete - 流式完成 - 前端小新代修改：适配后端新格式
    // 【小新修复 2026-03-12】第三个参数改为接收完整的data对象
    // 【小沈修复 2026-03-14】第三个参数实际是ExecutionStep[]数组，不是对象
    useCallback(
      async (
        fullResponse: string,
        metadata?: string | {
          model?: string;
          provider?: string;
          display_name?: string;
        },
        executionStepsFromSSE?: ExecutionStep[]
      ) => {
        // ✅ 支持旧格式（model 字符串）和新格式（metadata 对象）
        const metadataObj =
          typeof metadata === "string" ? { model: metadata } : metadata || {};

        // 🔴 修复：处理 AI 返回空内容的情况
        // 【小新修复 2026-03-14】补充完整的错误字段，避免导出时缺少error_type等
        let finalResponse = fullResponse;
        let isError = false;
        let errorType: string | undefined = undefined;
        // 【小沈修改2026-04-15】删除errorCode字段，统一使用errorMessage
        let errorMessage: string | undefined = undefined;
        
        if (!finalResponse || !finalResponse.trim()) {
          finalResponse = "抱歉，我暂时无法回答这个问题。请您稍后再尝试，或者换个方式提问。";
          isError = true; // 标记为错误类型，以便显示红色样式
          // 【小新修复 2026-03-14】补充错误字段，与onError保持一致
          errorType = "empty_response";
          // 【小沈修改2026-04-15】删除errorCode
          errorMessage = "模型未能生成有效回复，请尝试更换问题或稍后重试";
          console.warn("⚠️ AI 返回了空内容，已使用默认回复，errorType:", errorType);
        }

        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === "assistant") {
            const updated = [...prev];
            // 【小强修复 2026-03-18】修复竞争条件导致的final/steps丢失问题
            // 问题：onStep异步更新message.executionSteps，onComplete可能在其完成前执行，导致覆盖
            // 解决：优先使用message中已有的executionSteps（如果更长），否则使用SSE传递的
            const sseSteps = executionStepsFromSSE || executionStepsRef.current || [];
            const msgSteps = lastMessage.executionSteps || [];
            // 选择更长的那个，避免覆盖已存在的数据
            const latestSteps = msgSteps.length >= sseSteps.length ? msgSteps : sseSteps;
            
            // 【调试日志】说明：为什么有两个steps数量？
            // - SSE传递的steps：本次对话实时收到的步骤数量（比如：start → thought → chunk → final）
            // - message已有的steps：这个消息之前保存的步骤数量（比如：历史会话加载进来的）
            // - 最终选择：取两者中更多的那个来保存（确保不丢失数据）
            console.log("📊 type=%s AI完成 实时=%d 历史=%d 保存=%d", sseSteps.length, msgSteps.length, latestSteps.length);
            
            // 【小健修复 2026-04-13】优先使用streamingContentRef累积内容，确保不丢失
            const finalContent = streamingContentRef.current || finalResponse;
            
            // 【小健修复 2026-04-13】优先使用streamingStepsRef累积步骤，再与SSE和message比较
            const refSteps = streamingStepsRef.current || [];
            // 取三者中最长的，确保不丢失任何数据
            const allSteps = [refSteps, executionStepsFromSSE || [], msgSteps];
            const finalSteps = allSteps.reduce((longest, curr) => 
              curr.length > longest.length ? curr : longest, []);
            
            updated[updated.length - 1] = {
              ...lastMessage,
              content: finalContent,
              isStreaming: false,
              is_reasoning: false,
              isError: isError,
              errorType: errorType,
              // 【小沈修改2026-04-15】删除errorCode
              errorMessage: errorMessage,
              model: metadataObj.model || lastMessage.model,
              provider: metadataObj.provider || lastMessage.provider,
              display_name: metadataObj.display_name || lastMessage.display_name,
              executionSteps: finalSteps,
            };
            console.log("  └─ ✅ 已更新 (ref累积+SSE+历史) steps:", finalSteps.length, "| last3:", finalSteps.slice(-3).map((s: any) => s.type).join(","));
            console.log("  └─ ✅ 已更新 steps:", latestSteps.length, "| last3:", latestSteps.slice(-3).map((s: any) => s.type).join(","));
            return updated;
          }
          return prev;
        });

        // 保存AI回复到会话
        // 【小沈修复2026-03-03】现在只保存AI回复消息，用户消息已在发送前保存
        // 这样更加健壮，即使AI响应失败，用户消息也已保存
        const currentSessionId = currentSessionIdRef.current || sessionId;
        // 【小查修复 2026-03-14】恢复使用executionStepsFromSSE参数
        // 历史教训：2026-03-12 小沈提交commit 800f0fd27时，将参数从ExecutionStep[]改为{sseData?: {execution_steps?: ExecutionStep[]}}
        // 但调用方sse.ts第716行仍然传递ExecutionStep[]数组，导致类型不匹配
        // 结果：sseData?.execution_steps永远是undefined，思考过程(execution_steps)无法保存到数据库
        // 症状：AI回复完成后刷新页面，"思考"部分的详细内容丢失，只剩下"正在分析任务..."
        // 教训：修改函数签名时必须同步修改所有调用方，不能单方面改变参数结构！
        // const stepsFromSSE = executionStepsFromSSE;  // 已废弃，后端自动保存
        if (currentSessionId && finalResponse && finalResponse.trim()) {
          // 🔴 修复：添加详细的调试日志
          // console.log("💾 [保存AI回复] 正在保存到数据库:");
          // console.log("  ├─ 会话ID:", currentSessionId);
          // console.log("  ├─ 回复长度:", finalResponse.length, "字符");
          // console.log("  ├─ SSE传递的步骤数:", stepsFromSSE?.length, "个");
          // console.log("  └─ ref中的步骤数:", executionStepsRef.current?.length, "个");

          try {
            // 后端在流式结束时自动保存steps到数据库，无需前端触发
            // console.log("✅ type=%s 后端已保存steps");

            // ⭐ 【小新修复 2026-03-04】保存AI回复后不再调用 ensureTitlePersisted
            // 原因：标题应该在用户修改时立即保存，避免版本冲突
            // 如果需要同步最新数据，应该在用户修改标题时处理
            // console.log("✅ [保存AI回复] 保存成功！");
          } catch (saveError: any) {
            console.error("❌ [保存AI回复] 保存失败:", saveError?.message || saveError);
            console.error("   └─ 保存时使用的会话ID:", currentSessionId);
            
            // 使用统一错误处理中心
            const errorResult = handleApiError(saveError);
            
            // 根据错误类型进行特殊处理
            if (errorResult.errorType === ErrorType.SESSION_CONFLICT) {
              // 409版本冲突 - 尝试从服务器获取最新数据
              try {
                const sessionData = await sessionApi.getSessionMessages(currentSessionId);
                if (sessionData.title) setSessionTitle(sessionData.title);
              } catch (syncError) {
                console.error("   └─ 同步最新数据失败:", syncError);
              }
              return;
            }
            
            // 如果是需要继续执行的错误（如用户消息保存失败），不阻断流程
            if (errorResult.shouldContinue) {
              console.warn("   └─ 保存失败但继续执行:", errorResult.errorType);
              return;
            }
            
            // 其他错误已经通过errorHandler显示提示
            return;
          }
        } else {
          console.warn("⚠️ [保存AI回复] 跳过保存：缺少必要数据");
          console.log("   ├─ 会话ID是否为空:", !currentSessionId ? "是（跳过保存）" : "否");
          console.log("   └─ 回复内容是否为空:", !fullResponse ? "是（跳过保存）" : "否");
        }

           console.log("✅ type=%s AI流式完成 %s", new Date().toLocaleTimeString());
         
           // ========== 黄色结束标志 ==========
           logAIComplete(fullResponse?.length || 0);
           // ==================================
          
          setLoading(false);
          // ⭐ 停止等待计时器
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }
          setWaitTime(0);
          setIsRetrying(false);
           // 【小新第三修复 2026-03-02】清理ref和state
           pendingMessageRef.current = null; // 同步清理
           setPendingMessage(null); // 异步清理
           
           // ⭐ 【小资优化 2026-04-13】使用累积的ref内容一次性更新
           setMessages((prev) => {
             const lastMessage = prev[prev.length - 1];
if (lastMessage && lastMessage.role === "assistant") {
                const updated = [...prev];
                // 【小健修复 2026-04-13】优先使用streamingContentRef累积内容
                const finalContent = streamingContentRef.current || finalResponse;
                
                // 【小健修复 2026-04-13】优先使用streamingStepsRef累积步骤，再与SSE和message比较
                const refSteps = streamingStepsRef.current || [];
                const msgSteps = lastMessage.executionSteps || [];
                const sseSteps = executionStepsFromSSE || [];
                // 取三者中最长的，确保不丢失任何数据
                const allSteps = [refSteps, sseSteps, msgSteps];
                const finalSteps = allSteps.reduce((longest, curr) => 
                  curr.length > longest.length ? curr : longest, []);
                
                console.log("📊 type=%s AI完成 ref=%d SSE=%d 历史=%d 保存=%d", 
                  finalContent.length, refSteps.length, sseSteps.length, msgSteps.length, finalSteps.length);
                
                updated[updated.length - 1] = {
                  ...lastMessage,
                  content: finalContent,
                  executionSteps: finalSteps,
                  isStreaming: false,
                  is_reasoning: false,
                  isError: isError,
                  errorType: errorType,
                  // 【小沈修改2026-04-15】删除errorCode
                  errorMessage: errorMessage,
                  model: metadataObj.model || lastMessage.model,
                  provider: metadataObj.provider || lastMessage.provider,
                  display_name: metadataObj.display_name || lastMessage.display_name,
                };
                console.log("  └─ ✅ 已更新 (ref累积+SSE+历史) steps:", finalSteps.length, "| last3:", finalSteps.slice(-3).map((s: any) => s.type).join(","));
                return updated;
             }
             return prev;
           });
           
           // ⭐ 【小资优化 2026-04-13】完成后清理ref，准备下一次对话
           streamingContentRef.current = '';
           streamingStepsRef.current = [];
           lastUpdateTimeRef.current = 0;
           
             // console.log("✅ [onComplete] AI回答保存完成！");
          },
        [] // 依赖数组为空，因为使用 ref 而不是 state
      ),
    // onError - 流式错误 - 【小资优化】同步节流 + errorHandler统一处理
    // 【小沈修改2026-04-15】适配API文档的新字段：删除code，统一使用error_message
    useCallback(
      (
        error:
          | string
          | {
              // 必填字段（4个）
              type: string;
              error_type: string;
              error_message: string;
              timestamp: string;
              // 可选字段（8个）
              model?: string;
              provider?: string;
              details?: string;
              stack?: string;
              retryable?: boolean;
              retry_after?: number;
              recoverable?: boolean;
              context?: {
                step?: number;
                model?: string;
                provider?: string;
                thought_content?: string;
              };
            }
      ) => {
        // ✅ 支持字符串和对象两种格式
        const errorObj =
          typeof error === "string"
            ? { type: "error", error_type: "unknown_error", error_message: error, timestamp: new Date().toISOString() }  // 【小沈修改2026-04-15】message → error_message
            : error;

        console.error("🔴 [onError] SSE 流式错误:", errorObj);
        
        // ⭐ 使用统一错误处理中心errorHandler处理提示
        const errorResult = handleSSEError(errorObj, { 
          reconnectAttempts: 0, 
          maxRetries: 0,
          onReconnect: undefined 
        });
        
        // 如果errorHandler认为不需要显示（如静默错误），则跳过
        if (errorResult.handled === false) {
          return;
        }
        
        // ⭐ 暂停时存入缓冲区（原有逻辑保留）
        if (isPausedRef.current) {
          displayBufferRef.current.push({ type: "error", error: errorObj });
          return;
        }

        // ⭐ 50ms间隔更新，leading+trailing策略
        const now = Date.now();
        const shouldUpdate = now - lastUpdateTimeRef.current >= UPDATE_INTERVAL 
          || lastUpdateTimeRef.current === 0;
        
        if (shouldUpdate) {
          lastUpdateTimeRef.current = now;
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant") {
              // 【小强修复 2026-03-18】修复竞争条件 - 选择更长的executionSteps
              const refSteps = executionStepsRef.current || [];
              const msgSteps = lastMessage.executionSteps || [];
              const latestSteps = msgSteps.length >= refSteps.length ? msgSteps : refSteps;
              
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...lastMessage,
                // 错误时直接用错误消息替换内容，不保留"思考中"
                // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
                content: (errorObj as any).error_message || (errorObj as any).message || "未知错误",
                isError: true,
                isStreaming: false,
                executionSteps: latestSteps,
                // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
                errorType: errorObj.error_type,
                errorMessage: (errorObj as any).error_message || (errorObj as any).message || "",  // 【小沈修改2026-04-15】优先使用error_message
                errorRetryAfter: errorObj.retry_after,
                errorTimestamp: errorObj.timestamp,
                // 【小沈添加2026-04-15】新增recoverable和context字段
                errorRecoverable: (errorObj as any).recoverable,
                errorContext: (errorObj as any).context,
                // 如果 errorObj 中没有 model/provider，使用消息中已有的值
                model: errorObj.model || lastMessage.model,
                provider: errorObj.provider || lastMessage.provider,
              };
              return updated;
            }
            return prev;
          });
        }
        
        // 清理状态
        setLoading(false);
        if (waitTimerRef.current) {
          clearInterval(waitTimerRef.current);
          waitTimerRef.current = null;
        }
        setWaitTime(0);
        setIsRetrying(false);
        
        // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
        logAIError((errorObj as any).error_message || (errorObj as any).message || "未知错误");
        
        // ⭐ 完成后清理ref
        streamingContentRef.current = '';
        streamingStepsRef.current = [];
        lastUpdateTimeRef.current = 0;
      },
      []
    ),
    // onPaused - 暂停事件
    useCallback(() => {
      console.log("⏸️ [onPaused] 收到暂停事件");
      setIsPaused(true);
    }, []),
    // onResumed - 恢复事件
    useCallback(() => {
      console.log("▶️ [onResumed] 收到恢复事件，缓冲区长度:", displayBufferRef.current.length);
      
      // 从缓冲区按顺序显示数据
      displayBufferRef.current.forEach(data => {
        if (data.type === "chunk" && data.content) {
          // 处理 chunk 类型
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + data.content,
              };
              return updated;
            }
            return prev;
          });
        } else if (data.type === "step" && data.step) {
          // 【关键修复】恢复时要把step添加到executionSteps
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...lastMessage,
                executionSteps: [...(lastMessage.executionSteps || []), data.step],
              };
              return updated;
            }
            return prev;
          });
        }
      });
      
      displayBufferRef.current = []; // 清空缓冲区
      setIsPaused(false);
    }, []),
    // onShowSteps - 控制步骤显示/隐藏（收到chunk时关闭步骤UI）
    useCallback((show: boolean) => {
      // 只在状态变化时打印
      // if (show) {
      //   console.log("👁️ [onShowSteps] 设置步骤显示状态: true");
      // } else {
      //   console.log("👁️ [onShowSteps] 设置步骤显示状态: false");
      // }
      setShowExecution(show);
    }, []),
    // ⭐ onRetry - 重试事件 - 【小查修复2026-03-13】添加waitTime参数
    useCallback((message: string, waitTime?: number) => {
      console.log("🔄 [onRetry] 收到重试事件:", message, "等待时间:", waitTime);
      setIsRetrying(true);  // 设置重试状态
      // 如果有wait_time，设置等待时间
      if (waitTime !== undefined) {
        setWaitTime(waitTime);
      } else {
        setWaitTime(0);
      }
    }, [])
  );

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
  const saveStateWithSSECheck = () => {
    if (isReceiving) {
      console.log("⚠️ [saveState] SSE 正在接收数据，延迟保存...");
      // 延迟 300ms 后再保存，给 SSE 时间处理 final 步骤
      setTimeout(() => {
        console.log("⚠️ [saveState] 延迟后执行保存...");
        saveState();
      }, 300);
    } else {
      // SSE 已完成，直接保存
      saveState();
    }
  };
  
  const saveState = () => {
    // 【小沈修复 2026-03-17】直接使用 messages 状态，而不是 messagesRef.current
    // 根因：messagesRef.current 是通过 useEffect 异步同步的，当页面隐藏时可能还没更新完成
    //      导致 sessionStorage 保存的消息缺少 start 步骤
    // 修复：直接使用 messages 状态，确保获取最新数据
    if (sessionId) {
      // 【问题2修复 2026-03-18】当正在接收SSE数据时，messages状态可能是异步更新未完成的
      // 需要从executionStepsRef获取最新steps并更新到messages中保存
      // 【修复 2026-03-18】使用messagesRef.current获取最新messages，而不是闭包中的messages
      let messagesToSave = messagesRef.current;
      if (isReceiving && executionStepsRef.current.length > 0) {
        console.log("🔧 [saveState] SSE正在接收，合并最新steps到messages保存:", executionStepsRef.current.length);
        messagesToSave = messagesRef.current.map((msg, idx) => {
          // 找到最后一条assistant消息（正在流式输出的）
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
        messages: messagesToSave,  // ← 使用合并后的messages
        sessionId,
        sessionTitle,
        timestamp: Date.now(),
        scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
        // 保存暂停/中断状态，避免页面切换时状态丢失
        isPaused,
        isReceiving,
      };
      
      // 【2026-04-08修复】sessionStorage容量满时不崩溃
      try {
        const stateStr = JSON.stringify(state);
        // 检查大小（sessionStorage限制约5-10MB）
        const sizeInMB = (stateStr.length / 1024 / 1024).toFixed(2);
        if (stateStr.length > 4 * 1024 * 1024) {
          // 超过4MB，只保存消息摘要
          console.warn(`⚠️ 会话数据过大(${sizeInMB}MB)，只保存摘要`);
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
        console.log("💾 type=%s 保存sessionStorage %s | msg=%d steps=%d", new Date().toLocaleTimeString(), messagesToSave.length, executionStepsRef.current.length);
      } catch (e) {
        if (e instanceof DOMException && e.name === 'QuotaExceededError') {
          console.warn("⚠️ sessionStorage容量满，只保存会话ID和标题");
          // 保存最小信息，下次打开时从API重新加载
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
            sessionId,
            sessionTitle,
            timestamp: Date.now(),
          }));
        } else {
          console.error("保存会话状态失败:", e);
        }
      }
    }
  };

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
                // 正常恢复（页面隐藏时SSE已完成）
                setMessages(state.messages);
                if (state.sessionTitle) {
                  setSessionTitle(state.sessionTitle);
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

  // ============================================
  // 网络连接检查
  // ============================================

  /**
   * 检查网络连接状态
   */
  const checkNetworkConnection = async (): Promise<boolean> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      clearTimeout(timeoutId);
      console.warn("网络连接检查失败:", error);
      return false;
    }
  };

  // ============================================
  // 统一的标题管理函数
  // ============================================


  /**
   * 生成新会话标题 - 智能生成有意义的标题
   * 🔄 优化：添加更多时间细分，使标题更精确
   */
  const generateNewSessionTitle = (): string => {
    const now = new Date();
    const hours = now.getHours();
    let timeOfDay = "";

    // 更精确的时间段划分
    if (hours >= 5 && hours < 8) timeOfDay = "清晨";
    else if (hours >= 8 && hours < 12) timeOfDay = "上午";
    else if (hours >= 12 && hours < 14) timeOfDay = "午间";
    else if (hours >= 14 && hours < 18) timeOfDay = "下午";
    else if (hours >= 18 && hours < 21) timeOfDay = "晚间";
    else if (hours >= 21 && hours < 24) timeOfDay = "深夜";
    else timeOfDay = "深夜"; // 0-5点

    const dateStr = `${now.getMonth() + 1}月${now.getDate()}日`;
    return `${dateStr} ${timeOfDay}会话 ${hours}:${now
      .getMinutes()
      .toString()
      .padStart(2, "0")}`;
  };

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
   * 执行流式消息发送（使用useSSE hook）
   *
    * @update 2026-02-23 修复：添加assistant消息占位，确保onStep/onChunk能正确更新
    */
  const executeStreamSend = async (userMessage: Message) => {
    console.log("📡 type=%s 开始发送消息");
    
    setLoading(true);
    // ⭐ 启动等待计时器
    setWaitTime(0);
    setIsRetrying(false);
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
    }
    waitTimerRef.current = setInterval(() => {
      setWaitTime(t => t + 1);
    }, 1000);
    clearSteps();

    // 保存待发送消息到ref（同步）和state（异步）
    pendingMessageRef.current = userMessage; // 同步更新，立即生效 ✅
    setPendingMessage(userMessage);

    // 【小沈修复2026-03-03】在调用 /chat/stream 之前先保存用户消息
    // 这样即使AI响应失败，用户消息也不会丢失
    const currentSessionId = currentSessionIdRef.current || sessionId;
    // console.log("🔍 [executeStreamSend] 使用的sessionId:", currentSessionId);
    
    let backendUserMessageId: number | null = null;
    
    if (currentSessionId) {
      try {
        // 【小沈 2026-03-24】获取客户端信息
        const clientInfo = getClientInfo();
        console.log("🔍 客户端信息:", clientInfo);
        
        console.log("🔍 在调用AI之前先保存用户消息:", userMessage);
        const saveResult = await sessionApi.saveMessage(currentSessionId, {
          role: "user",
          content: userMessage.content,
          // 【小沈 2026-03-24】传递客户端信息
          client_os: clientInfo.client_os,
          browser: clientInfo.browser,
          device: clientInfo.device,
          network: clientInfo.network,
        });
        // 保存用户消息ID，用于AI消息关联
        backendUserMessageId = saveResult?.message_id || null;
        replyUserMessageIdRef.current = backendUserMessageId;
        
        // 【关键修复】用后端返回的ID更新用户消息ID
        if (backendUserMessageId) {
          setMessages((prev) => {
            const newMessages = [...prev];
            // 找到用户消息，用后端ID更新
            const userMsgIndex = newMessages.findIndex(m => m.id === userMessage.id);
            if (userMsgIndex !== -1) {
              newMessages[userMsgIndex] = {
                ...newMessages[userMsgIndex],
                id: backendUserMessageId!.toString()
              };
              console.log("✅ 用户消息ID已更新:", backendUserMessageId);
            }
            return newMessages;
          });
        }
        
        console.log("✅ 用户消息保存成功, message_id:", saveResult?.message_id);
      } catch (error) {
        console.error("❌ 保存用户消息失败:", error);
        // 使用统一错误处理中心 - 错误消息保存失败但继续发送AI
        const result = handleError(error, { source: "api", continueOnError: true });
        if (!result.shouldContinue) {
          console.warn("   └─ 保存失败且不能继续");
        }
      }
    } else {
      console.warn("⚠️ 未找到sessionId，无法保存用户消息:", userMessage.id);
    }

    // 【关键修复】用后端返回的message_id生成assistant消息ID（后端逻辑：user_id + 1 = assistant_id）
    const assistantId = backendUserMessageId 
      ? (backendUserMessageId + 1).toString() 
      : (Date.now() + 1).toString();
    console.log("🔍 assistant消息ID:", assistantId, "(后端ID:", backendUserMessageId, "+1)");

    // 【关键修复】用后端返回的ID创建assistant消息
    // 【小沈修复 2026-03-26】timestamp会在SSE回调的onStep中更新为后端返回的正确时间戳
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "🤔 AI 正在思考...", // 【修复问题 2】显示占位文本，避免空白气泡
      timestamp: new Date(), // 临时值，会被onStep回调中的正确时间戳覆盖
      executionSteps: [],
      isStreaming: true,
      model: undefined, // 前端小新代修改：明确设置可选属性
    };
    // console.log("🔍 [executeStreamSend] 创建assistant占位消息:", assistantMessage);
    setMessages((prev) => [...prev, assistantMessage]);

    // console.log("🔍 [executeStreamSend] 准备调用sendStreamMessage...");
    // console.log("  content:", userMessage.content);
    // console.log("  sessionId:", currentSessionIdRef.current || sessionId);
    
    // 发送流式请求 - 【小沈添加 2026-03-03】传递sessionId用于后端缓存display_name
    sendStreamMessage(userMessage.content, currentSessionIdRef.current ?? sessionId ?? undefined);
    console.log("✅ type=%s sendStreamMessage已调用");
  };

  /**
   * 任务中断处理 - 前端小新代修改
   * 【小查修复2026-03-14】传递true参数，阻止重连
   */
  const handleInterrupt = async () => {
    const taskIdToCancel = serverTaskId;
    console.log(`[中断] serverTaskId=${serverTaskId}, taskIdToCancel=${taskIdToCancel}`);
    if (taskIdToCancel) {
      try {
        showTaskControlInfo("正在中断任务...");
        console.log("[中断] 已显示 '正在中断任务...' 提示");
        
        // 使用统一的 taskControlApi
        const result = await taskControlApi.cancel(taskIdToCancel, sessionId ?? undefined);
        console.log("[中断] cancel API 返回:", result);
        
        // ✅ 先断开连接，停止自动重连！传递true表示手动中断
        disconnect(true);
        console.log("[中断] 已调用 disconnect(true)");
        
        // 显示后端返回的具体消息
        showTaskResultMessage("interrupt", result.message);
        console.log("[中断] 已显示中断成功提示");
      } catch (error) {
        console.error("[中断] 错误:", error);
        showTaskControlMessage("interrupt", false, error instanceof Error ? error.message : String(error));
      }
    } else {
      console.warn("[中断] 没有有效的 taskId，无法中断");
      showNoActiveTaskWarning();
    }
  };

  /**
   * 任务暂停/继续
     */
  const handleTogglePause = async () => {
    if (!serverTaskId) {
      showNoActiveTaskWarning();
      return;
    }

    try {
      if (!isPaused) {
        // 暂停：发送暂停请求
        const result = await taskControlApi.pause(serverTaskId ?? undefined, sessionId ?? undefined);
        console.log("⏸️ 已发送暂停请求，后端返回:", result);
        
        // 更新前端暂停状态
        setIsPaused(true);
        isPausedRef.current = true;
        
        // 显示后端返回的具体消息
        showTaskResultMessage("pause", result.message);
      } else {
        // 继续：发送恢复请求
        const result = await taskControlApi.resume(serverTaskId ?? undefined, sessionId ?? undefined);
        console.log("▶️ 已发送恢复请求，后端返回:", result);
        
        // 更新前端暂停状态
        setIsPaused(false);
        isPausedRef.current = false;
        
        // 显示后端返回的具体消息
        showTaskResultMessage("resume", result.message);
      }
    } catch (error) {
      console.error("❌ 暂停/继续请求失败:", error);
      // 使用统一错误处理中心 - 任务控制失败
      handleError(error, { source: "api" });
    }
  };

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
       const isNetworkOK = await checkNetworkConnection();
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
    setBlockedCommand(null);

    // ========== 红色开始标志 ==========
    logUserSend(userMessage.content);
    // ==================================

    // 安全检测v2.0
    setCheckingDanger(true);
    try {
      const checkResult = await securityApi.checkCommand(userMessage.content);
      setCheckingDanger(false);

      if (!checkResult.success || !checkResult.data) {
        console.warn("安全检测失败:", checkResult.error);
        await executeStreamSend(userMessage);
        return;
      }

      const { score, message: riskMessage } = checkResult.data;
      const riskLevel = getRiskLevel(score);

      switch (riskLevel.level) {
        case "SAFE":
          await executeStreamSend(userMessage);
          break;
        case "MEDIUM":
          showSecurityNotification(userMessage.content, score, riskMessage);
          await executeStreamSend(userMessage);
          break;
        case "HIGH":
          setDangerCommand(userMessage.content);
          setDangerScore(score);
          setDangerMessage(riskMessage);
          // 【小新第三修复 2026-03-02】同步更新ref
          pendingMessageRef.current = userMessage;
          setPendingMessage(userMessage);
          setDangerModalVisible(true);
          break;
        case "CRITICAL":
          setBlockedCommand({
            command: userMessage.content,
            score,
            message: riskMessage,
          });
          setMessages((prev) =>
            prev.filter((msg) => msg.id !== userMessage.id)
          );
          // 使用统一错误处理中心 - 危险操作拦截
          handleError({ 
            error_type: ErrorType.DANGEROUS_OPERATION,
            message: "危险操作已被系统拦截"
          }, { source: "api" });
          break;
        }
      } catch (error) {
        console.warn("安全检测异常:", error);
        setCheckingDanger(false);
        // 使用统一错误处理中心 - 安全服务降级
        handleError({
          error_type: ErrorType.SECURITY_SERVICE_DOWN,
          message: "安全检测服务暂时不可用，将以普通模式发送消息"
        }, { source: "api" });
        await executeStreamSend(userMessage);
      }
    };

  // ============================================================

  /**
   * 危险命令确认执行
   */
  const handleDangerConfirm = async () => {
    // 【强制修复】立即关闭弹窗，重置loading状态
    setDangerModalVisible(false);
    setLoading(false);
    
    // 【小新第五修复 2026-03-02】优先使用ref中的pendingMessage，确保获取正确的值
    const messageToProcess = pendingMessageRef.current || pendingMessage;
    if (messageToProcess) {
      await executeStreamSend(messageToProcess);
    }
  };

  /**
   * 危险命令取消执行
   */
  const handleDangerCancel = () => {
    // 【强制修复】立即关闭弹窗，重置loading状态
    setDangerModalVisible(false);
    setLoading(false);
    
    // 【小新第五修复 2026-03-02】优先使用ref中的pendingMessage
    const messageToCancel = pendingMessageRef.current || pendingMessage;
    if (messageToCancel) {
      setMessages((prev) =>
        prev.filter((msg) => msg.id !== messageToCancel.id)
      );
      showDangerCancelled();
    }
    // 【小新第五修复 2026-03-02】同步清理ref和state
    pendingMessageRef.current = null;
    setPendingMessage(null);
  };

  /**
   * 新建会话 - 内部实现，支持重试机制
   */
  const handleNewSessionInternal = async (retry: number = 0) => {
    const retryKey = "new-session";
    const maxRetries = 3;

    setLoading(true);
    try {
      // 生成智能标题
      const newTitle = generateNewSessionTitle();
      const newSession = await sessionApi.createSession(newTitle);
      setSessionId(newSession.session_id);
      // 【小新第二修复 2026-03-02】新建会话时也更新ref
      currentSessionIdRef.current = newSession.session_id;
      setSessionTitle(newTitle);
      setMessages([]);
      
      // 重置日志标记
      logFlagsRef.current = {
        chunkFirstDone: false,
        showStepsFalseDone: false,
        showStepsTrueDone: false,
      };

      // 🔴 修复：清除旧的sessionStorage
      sessionStorage.removeItem(STORAGE_KEY);

      // 添加系统提示消息 - 新会话提示
      const systemMessage: Message = {
        id: (Date.now() + 1000).toString(),
        role: "system",
        content: "💡 新会话已创建！开始与AI助手对话吧。",
        timestamp: new Date(),
      };
      setMessages([systemMessage]);

      clearSteps();
      disconnect();
      window.history.pushState({}, "", `/?session_id=${newSession.session_id}`);

      // 🎨 优化：添加更丰富的反馈
      showNewSessionSuccess(newTitle);

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } catch (error) {
      // P1级别优化：重试机制
      if (retry < maxRetries) {
        const newRetry = retry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));

        showNewSessionRetryWarning(newRetry, maxRetries);

        // 延迟1秒后重试
        setTimeout(() => {
          handleNewSessionInternal(newRetry);
        }, 1000);
        return;
      }

      // 🔴 修复：更好的错误处理
      const errMsg = error instanceof Error ? error.message : "未知错误";
      showNewSessionError(errMsg);
      console.error("创建会话失败:", error);

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } finally {
      setLoading(false);
      // ⭐ 停止等待计时器
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
        waitTimerRef.current = null;
      }
      setWaitTime(0);
    }
  };

  /**
   * 新建会话 - 按钮点击处理函数
   */
  const handleNewSession = () => {
    console.log("🔍 [handleNewSession] 按钮被点击");
    handleNewSessionInternal(0);
  };

  /**
   * 清空对话
   */
  const handleClear = () => {
    console.log("🔍 [handleClear] 清空对话按钮被点击");
    setMessages([]);
    clearSteps();
    disconnect();
  };

  return (
    <Card
      styles={{ body: { padding: "0 4px 4px 4px" } }}
      title={
        <span 
          style={{ cursor: "pointer", display: "inline-flex", alignItems: "center" }}
                onClick={() => {
                  if (!editingTitle && sessionId) {
                    setTitleInput(sessionTitle || "");
                  }
                  setEditingTitle(true);
                }}
        >
          <RobotOutlined />
          {/* 【小强优化2026-04-14】显示"会话"标签 + 分隔符 + 实际标题 */}
          <span style={{ marginLeft: 8, color: "#666", fontSize: 14 }}>会话</span>
          {/* 优雅的分隔符：带渐变效果的竖线 */}
          <span style={{
            marginLeft: 8,
            marginRight: 8,
            height: 16,
            width: 1,
            background: "linear-gradient(to bottom, transparent, #d9d9d9, transparent)",
          }} />
          {sessionId && editingTitle ? (
              <Space>
                <Input
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  onPressEnter={async (e) => {
                    e.preventDefault();
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：回车时保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                         setSessionTitle(titleInput.trim());
                         setTitleLocked(true); // 【小新第二修复 2026-03-02】用户修改标题后锁定
                         showTitleSaved();
                        } catch (error: any) {
                         // ⭐ 处理 409 版本冲突
                        if (error?.response?.status === 409) {
                          showSessionConflict();
                          // 尝试重新获取最新的会话信息
                          try {
                            const sessionData =
                              await sessionApi.getSessionMessages(sessionId);
                            if (sessionData.version) {
                              setSessionVersion(sessionData.version);
                            }
                            if (sessionData.title) {
                              setSessionTitle(sessionData.title);
                            }
                          } catch (refreshError) {
                            console.error("刷新会话数据失败:", refreshError);
                          }
                        } else {
                          console.warn("保存标题失败:", error);
                          showSaveError("保存标题失败，请重试");
                        }
                      }
                    }
                    setEditingTitle(false);
                  }}
                  onBlur={async () => {
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：失去焦点时也保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                         setSessionTitle(titleInput.trim());
                         setTitleLocked(true); // 【小新第二修复 2026-03-02】用户修改标题后锁定
                         showTitleUpdated();
                        } catch (error: any) {
                         // ⭐ 处理 409 版本冲突
                        if (error?.response?.status === 409) {
                          showSessionConflict();
                          // 尝试重新获取最新的会话信息
                          try {
                            const sessionData =
                              await sessionApi.getSessionMessages(sessionId);
                            if (sessionData.version) {
                              setSessionVersion(sessionData.version);
                            }
                            if (sessionData.title) {
                              setSessionTitle(sessionData.title);
                            }
                          } catch (refreshError) {
                            console.error("刷新会话数据失败:", refreshError);
                          }
                        } else {
                          showSaveError("更新标题失败");
                        }
                      }
                    }
                    setEditingTitle(false);
                  }}
                  style={{ width: 200 }}
                  autoFocus
                  placeholder={sessionTitle || "输入会话标题"}
                />
              </Space>
            ) : (
              <span
                style={{
                  cursor: "pointer",
                  color: titleLocked ? "#000" : "#666", // 【小新第二修复 2026-03-02】使用 titleLocked 替代 titleSource
                  fontSize: titleLocked ? "16px" : "14px",
                  fontWeight: titleLocked ? "bold" : "normal",
                }}
          onClick={() => {
            if (!editingTitle && sessionId) {
              setTitleInput(sessionTitle || "");
            }
            setEditingTitle(true);
          }}
              >
                {sessionTitle || "未命名会话"}
                {!titleLocked && ( // 【小新第二修复 2026-03-02】使用 titleLocked 替代 titleSource
                  <Tooltip title="AI自动生成的标题">
                    <InfoCircleOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: "#999" }}
                    />
                  </Tooltip>
                )}
                {titleLocked && (
                  <Tooltip title="标题已锁定，防止自动覆盖">
                    <LockOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: "#1890ff" }}
                    />
                  </Tooltip>
                )}
              </span>
            )}
        </span>
      }
      extra={
        <Space>
          {/* 新建会话按钮 */}
          <Button
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            size="small"
            type="primary"
            style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
          >
            新建会话
          </Button>

          {/* 流式开关（同时控制显示过程） */}
          <Tag.CheckableTag
            checked={useStream}
            onChange={(checked) => {
              console.log("🔍 [流式开关] 被点击，新状态:", checked);
              setUseStream(checked);
              if (!checked) {
                setShowExecution(false);
              }
            }}
            style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
          >
            <ThunderboltOutlined /> {useStream ? "流式关闭" : "流式开启"}
          </Tag.CheckableTag>

          {/* 执行过程显示开关（仅在流式模式下显示） */}
          {useStream && (
            <Button
              size="small"
              icon={showExecution ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              onClick={() => {
                console.log("🔍 [显示过程] 按钮被点击");
                setShowExecution(!showExecution);
              }}
              style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
            >
              {showExecution ? "隐藏过程" : "显示过程"}
            </Button>
          )}

          <Button 
            onClick={handleClear} 
            size="small"
            style={{ cursor: 'pointer', position: 'relative', zIndex: 100 }}
          >
            清空对话
          </Button>
        </Space>
      }
    >
      {/* AI思考过程面板已移至MessageItem内部 - 前端小新代修改 */}

      {/* 消息列表 - 前端小新代修改 UX-C04: 时间分隔线 */}
      <div
        style={{
          height: 500,
          overflowY: "auto",
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: "0 2px 2px 0",
          marginBottom: 0,
          backgroundColor: "#fafafa",
          position: "relative",
        }}
        >
        
        {messages.length === 0 ? (
          isMessageListLoading ? (
            <MessageListSkeleton count={4} />
          ) : (
            <div style={{ textAlign: "center", color: "#999", marginTop: 50 }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <p>开始与 AI 助手对话</p>
              <p style={{ fontSize: 12 }}>
                {useStream
                  ? "流式模式已开启 - 可实时查看 AI 思考过程"
                  : "普通模式 - 一次性返回完整回复"}
              </p>
            </div>
          )
        ) : (
          <div>
            {/* 【小强 2026-04-12】Phase 2 P1级优化：使用独立hook优化消息列表渲染 */}
            {messageElements}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 - 【小强修复 2026-03-31】使用独立ChatInput组件隔离inputValue状态 */}
      <ChatInput
        loading={loading}
        isReceiving={isReceiving}
        isPaused={isPaused}
        isRetrying={isRetrying}
        waitTime={waitTime}
        useStream={useStream}
        checkingDanger={_checkingDanger}
        onSend={handleSend}
        onInterrupt={handleInterrupt}
        onTogglePause={handleTogglePause}
      />

      {/* 被拦截的命令警告 */}
      {blockedCommand && (
        <SecurityAlert
          command={blockedCommand.command}
          score={blockedCommand.score}
          message={blockedCommand.message}
        />
      )}

      {/* 危险命令确认弹窗 */}
      <DangerConfirmModal
        visible={dangerModalVisible}
        command={dangerCommand}
        score={dangerScore}
        message={dangerMessage}
        onConfirm={handleDangerConfirm}
        onCancel={handleDangerCancel}
        loading={loading}
      />
    </Card>
  );
};

export default NewChatContainer;
