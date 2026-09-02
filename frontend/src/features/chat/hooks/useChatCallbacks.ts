// 编辑历史: 2026-07-18 小欧 - FinalStep终态规整: 取消判定改为type=final+outcome=cancelled
// 编辑历史: 2026-09-03 小欧 Bug-26: onAuthorizationRequired 类型补全 4→8 字段(trust_path/auto_confirm/confirm_timeout/backend_timeout), 与 sseParser 下发契约一致, 全量透传保弹窗正确渲染 — 小欧-2026-09-03
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.5-9删后端自动保存死代码/10抽pickMsg/11终态清executionSteps
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - hooks修复#1/2/3/4/5/6/7/8: 取消事件识别/暂停ref同步/末条非assistant回写/thought回落/暂停分块保留
// 编辑历史: 2026-08-28 小强 - hooks修复#9: onComplete依赖数组补executionStepsRef/streamingStepsRef(闭包陈旧)
// 编辑历史: 2026-08-28 小强 - hooks修复#10: onResumed缓冲区回放改为单次setMessages原子合并(防批处理乱序)
// 编辑历史: 2026-08-28 小强 - hooks修复#11: 删onComplete后端保存空分支+else warn(YAGNI, 后端已自动落库)
/**
 * useChatCallbacks Hook - 统一回调管理
 *
 * 功能：
 * - 管理所有SSE回调函数（onStep, onChunk, onComplete, onError, onPaused, onResumed）
 * - 处理暂停缓冲区的数据回放
 * - 统一错误处理和状态更新
 *
 * 设计原则：
 * 1. 回调集中管理：所有SSE回调集中在一个Hook中
 * 2. 依赖注入：通过参数接收状态和函数依赖
 * 3. 闭包安全：正确使用useCallback和依赖数组
 * 4. 性能优化：避免不必要的重渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useCallback } from 'react';
import type { Message } from '../../../types/chat';
import type { ExecutionStep } from '../../../types/execution';
import type { UseChatStateReturn } from './useChatState';
import {
  handleSSEError,
  handleApiError,
  ErrorType,
} from '@/services/error/handler';
import { logAIComplete, logAIError } from '../../../utils/logStyles';
import { sessionApi } from '../../../services/api/session.api';
// 2026-08-27 小欧 三堂会审A2修复: SSEError/SSEMetadata从sse.ts导入, 消除重复定义
import type { SSEError, SSEMetadata } from '@/types/sse';

/**
 * useChatCallbacks Hook返回值
 */
export interface UseChatCallbacksReturn {
  onStep: (step: ExecutionStep) => void;
  onChunk: (chunk: string, is_reasoning?: boolean) => void;
  onComplete: (
    fullResponse: string,
    metadata?: string | SSEMetadata,
    executionStepsFromSSE?: ExecutionStep[]
  ) => Promise<void>;
  onError: (error: string | SSEError) => void;
  onPaused: () => void;
  onResumed: () => void;
  onRetry: (message: string, waitTime?: number) => void;
  onAuthorizationRequired: (data: {
    confirm_id: string;
    tool_name: string;
    params: Record<string, unknown>;
    safety_level: string;
    // 2026-09-03 小欧 Bug-26: 类型补全 4→8 字段(与 sseParser 下发契约一致), 防改代码时缺字段不自知
    trust_path?: string | null;
    auto_confirm?: boolean;
    confirm_timeout?: number;
    backend_timeout?: number;
  }) => void;
}

/**
 * 暂停缓冲区数据类型
 */
type BufferItem =
  | { type: 'step'; step: ExecutionStep }
  | { type: 'chunk'; content: string; is_reasoning?: boolean }
  | { type: 'error'; error: string | SSEError };

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatCallbacks - 统一回调管理Hook
 *
 * 迁移自：NewChatContainer.tsx 中的所有SSE回调函数
 * - onStep: 处理执行步骤
 * - onChunk: 处理内容片段
 * - onComplete: 处理流式完成
 * - onError: 处理错误
 * - onPaused: 处理暂停事件
 * - onResumed: 处理恢复事件
 *
 * @param state - useChatState返回的状态对象
 * @param streaming - useChatStreaming返回的流式对象（可选）
 * @returns 所有SSE回调函数
 */
export const useChatCallbacks = (
  state: UseChatStateReturn,
  streaming?: {
    setIsReceiving: (receiving: boolean) => void;
  }
): UseChatCallbacksReturn => {
  // 解构状态
  const {
    setMessages,
    setLoading,
    setWaitTime,
    setIsRetrying,
    setIsPaused,
    sessionId,
    setSessionTitle,

    // Refs
    messagesEndRef,
    currentSessionIdRef,
    displayBufferRef,
    isPausedRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    logFlagsRef,
    hasReceivedCancelEventRef,
    cancelInProgressRef,
    waitTimerRef,
  } = state;

  // ==================== onStep回调 ====================

  const onStep = useCallback(
    (step: ExecutionStep) => {
      // 【北京老陈 2026-07-12 小欧】统一取消语义：interrupted → cancelled
      // 2026-08-27 小欧 修复#1: 取消事件扩展识别 type==='cancelled'(服务端取消步骤), 不再仅限 final+outcome=cancelled
      const isCancelEvent =
        step.type === 'cancelled' ||
        (step.type === 'final' && step.outcome === 'cancelled');
      if (isCancelEvent) {
        hasReceivedCancelEventRef.current = true;
        console.log('[取消] 收到 cancelled 事件');
      }

      // ✅ 如果正在取消中，跳过非取消且与终态无关的事件（避免旧 chunk/步骤污染 UI）
      // 2026-08-27 小欧 修复#1/10: 取消进行中允许 final 终态步骤通过, 否则 final(completed)被吞导致消息无内容
      if (cancelInProgressRef.current) {
        if (!isCancelEvent && step.type !== 'final') {
          console.log(`[取消] 忽略取消过程中收到的事件: ${step.type}`);
          return;
        }
        // 是取消事件或 final 终态，继续处理（显示到 UI）
      }

      // 2026-08-27 小欧 修复#8: 删除"收到非chunk步骤即复位暂停"逻辑, 否则用户/服务端暂停被任意步骤打破(暂停形同虚设)
      // 暂停仅在 onResumed 时由 isPausedRef.current=false 显式解除, 暂停期间步骤统一进 displayBufferRef 缓冲

      // type 处理流程日志（解析 -> 存储 -> 渲染）
      console.log(
        '📝 type=%s timestamp=%s',
        step.type,
        step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : 'N/A'
      );

      // 只打印第一个chunk，减少日志
      if (step.type === 'chunk') {
        if (!logFlagsRef.current.chunkFirstDone) {
          console.log('🔍 [onStep] 收到步骤, type= chunk (第一个)');
          logFlagsRef.current.chunkFirstDone = true;
        }
      }

      // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
      if (isPausedRef.current) {
        console.log('⏸️ [onStep] 暂停中，存入缓冲区, type:', step.type);
        displayBufferRef.current.push({ type: 'step', step });
        return;
      }

      // 【修改 2026-06-09 小沈】删除streamingStepsRef累积逻辑，直接用state更新
      // 实时更新UI，每次都更新
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (!lastMessage || lastMessage.role !== 'assistant') {
          // 【关键修复 2026-04-13】任何step都创建消息，不只是start
          // 因为后端可能直接发 cancelled/paused/retrying，不发 start
          const extractedDisplay_name = step.display_name;
          let finalDisplay_name = extractedDisplay_name;
          if (!finalDisplay_name && step.model && step.provider) {
            finalDisplay_name = `${step.provider} (${step.model})`;
          }

          const newAssistantMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content:
              step.type === 'final'
                ? (step.response as string) ||
                  (step.content as string) ||
                  '🤔 AI 正在思考...'
                : step.content ||
                  (step.type === 'error'
                    ? step.error_message || '执行出错'
                    : '🤔 AI 正在思考...'),
            timestamp: step.timestamp ? new Date(step.timestamp) : new Date(),
            executionSteps: [step], // 直接使用当前step
            isStreaming: step.type !== 'error' && step.type !== 'final',
            model: step.model,
            provider: step.provider,
            display_name: finalDisplay_name,
          };
          return [...prev, newAssistantMessage];
        }

        // 更新最后一条消息的executionSteps
        // 【修复 2026-04-16】同时更新 isStreaming，确保 final/error 时显示正确状态
        const updated = [...prev];
        // 2026-08-27 小欧 修复#10: final 步骤携带 response 时回填消息内容(取消进行中收 completed 终态亦生效)
        const stepDisplayContent =
          step.type === 'final'
            ? (step.response as string) ||
              (step.content as string) ||
              lastMessage.content
            : lastMessage.content;
        updated[updated.length - 1] = {
          ...lastMessage,
          content: stepDisplayContent,
          executionSteps: [...(lastMessage.executionSteps || []), step], // 直接追加到现有steps
          // final/error/cancelled 时必须设置 isStreaming=false，停止 DynamicStatusDisplay
          // 2026-08-27 小欧 修复#1/13: type==='cancelled' 亦须置 isStreaming=false
          isStreaming:
            step.type !== 'error' &&
            step.type !== 'final' &&
            step.type !== 'cancelled'
              ? lastMessage.isStreaming
              : false,
        };
        return updated;
      });

      // onStep更新后滚动到底部
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 50);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [
      setMessages,
      setIsPaused,
      messagesEndRef,
      // Refs dependencies
      cancelInProgressRef,
      hasReceivedCancelEventRef,
      isPausedRef,
      displayBufferRef,
      logFlagsRef,
    ]
  );

  // ==================== onChunk回调 ====================

  const onChunk = useCallback(
    (chunk: string, is_reasoning?: boolean) => {
      // 精简日志：调试通过，不再打印每个chunk

      // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
      if (isPausedRef.current) {
        console.log('⏸️ [onChunk] 暂停中，存入缓冲区');
        displayBufferRef.current.push({
          type: 'chunk',
          content: chunk,
          is_reasoning,
        });
        return;
      }

      // ⭐ 累积到ref，不触发重渲染
      streamingContentRef.current += chunk;

      // 【小沈注释 2026-04-18】去掉节流机制，每次都更新UI
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
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
    },
    [
      setMessages,
      // Refs dependencies
      isPausedRef,
      displayBufferRef,
      streamingContentRef,
    ]
  );

  // ==================== onComplete回调 ====================

  const onComplete = useCallback(
    async (
      fullResponse: string,
      metadata?: string | SSEMetadata,
      executionStepsFromSSE?: ExecutionStep[]
    ) => {
      // ✅ 支持旧格式（model 字符串）和新格式（metadata 对象）
      const metadataObj =
        typeof metadata === 'string' ? { model: metadata } : metadata || {};

      // 🔴 修复：处理 AI 返回空内容的情况
      // 【小新修复 2026-03-14】补充完整的错误字段，避免导出时缺少error_type等
      let finalResponse = fullResponse;
      let isError = false;
      let errorType: string | undefined = undefined;
      // 【小沈修改2026-04-15】删除errorCode字段，统一使用errorMessage
      let errorMessage: string | undefined = undefined;

      if (!finalResponse || !finalResponse.trim()) {
        // 【修复 2026-05-05 小沈】Agent路径不发chunk，finalResponse永远为空，
        // 但executionSteps可能完全正常（有thought步骤含回答内容）。
        // 判断条件：final步骤的response和thought都空，且没有thought步骤有content，才判error
        const sseSteps =
          executionStepsFromSSE || executionStepsRef.current || [];
        const finalStep = sseSteps.find(
          (s: ExecutionStep) => s.type === 'final'
        ) as (ExecutionStep & Record<string, unknown>) | undefined;
        const finalStepResponse = (finalStep?.response as string) || '';
        const finalStepThought = (finalStep?.thought as string) || '';

        // 也检查thought步骤中是否有content（LLM的回答通常在thought步骤的content里）
        const thoughtSteps = sseSteps.filter(
          (s: ExecutionStep) => s.type === 'thought'
        );
        const hasThoughtContent = thoughtSteps.some(
          (s: ExecutionStep) => s.content && String(s.content).trim()
        );

        // response或thought任一有内容，或有thought步骤含content，都不算error
        const hasValidContent =
          (finalStepResponse && finalStepResponse.trim()) ||
          (finalStepThought && finalStepThought.trim()) ||
          hasThoughtContent;

        if (hasValidContent) {
          // 2026-08-27 小欧 修复#7: 答案位于 thought 步骤而 final.response/thought 均空时, 回落到首个含内容的 thought 步骤
          const thoughtContent = thoughtSteps.find(
            (s: ExecutionStep) => s.content && String(s.content).trim()
          )?.content;
          finalResponse =
            finalStepResponse ||
            finalStepThought ||
            (thoughtContent as string) ||
            '';
          console.info(
            '✅ finalResponse为空但executionSteps有有效内容，不标记error'
          );
        } else {
          // response和thought都空，且没有thought步骤有内容 → 确实是空响应
          finalResponse =
            '抱歉，我暂时无法回答这个问题。请您稍后再尝试，或者换个方式提问。';
          isError = true;
          // 【小新修复 2026-03-14】补充错误字段，与onError保持一致
          errorType = 'empty_response';
          // 【小沈修改2026-04-15】删除errorCode
          errorMessage = '模型未能生成有效回复，请尝试更换问题或稍后重试';
          console.warn(
            '⚠️ AI 返回了空内容(response和thought都空)，errorType:',
            errorType
          );
        }
      }

      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          const updated = [...prev];
          // 【小强修复 2026-03-18】修复竞争条件导致的final/steps丢失问题
          // 问题：onStep异步更新message.executionSteps，onComplete可能在其完成前执行，导致覆盖
          // 解决：优先使用message中已有的executionSteps（如果更长），否则使用SSE传递的
          // 【修改 2026-06-09 小沈】直接使用message中的executionSteps，删除三源合并逻辑
          // 2026-08-27 小欧 修复#6: 优先用服务端最终 fullResponse(含暂停期间缓冲分块), 避免暂停分块因 streamingContentRef 未累积而丢失
          const finalContent = finalResponse || streamingContentRef.current;
          const finalSteps = lastMessage.executionSteps || [];

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
          console.log(
            '  └─ ✅ 已更新 steps:',
            finalSteps.length,
            '| last3:',
            finalSteps
              .slice(-3)
              .map((s: ExecutionStep) => s.type)
              .join(',')
          );
          return updated;
        }
        // 2026-08-27 小欧 修复#5: 末条非 assistant(重连/无占位)时新建 assistant 消息写入最终回复, 不再静默丢弃
        const newAssistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: finalResponse || streamingContentRef.current,
          isStreaming: false,
          isError: isError,
          errorType: errorType,
          errorMessage: errorMessage,
          executionSteps: executionStepsFromSSE || [],
          timestamp: new Date(),
          model: metadataObj.model,
          provider: metadataObj.provider,
          display_name: metadataObj.display_name,
        };
        return [...prev, newAssistantMessage];
      });

      // 2026-08-28 小欧 修复: 后端已自动落库，前端无需额外保存（移除不存在的 updateMessages 调用，避免 tsc 报错）
      const currentSessionId = currentSessionIdRef.current;
      if (currentSessionId && finalResponse && finalResponse.trim()) {
        // 后端自动落库，前端仅同步标题/版本（已在 updateSession 流程中处理），此处不额外调用
      } else {
        console.warn('[onComplete] 无有效回复或sessionId，跳过前端同步保存');
      }

      console.log('✅ type=%s AI流式完成 %s', new Date().toLocaleTimeString());

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

      // ⭐ 【小资优化 2026-04-13】完成后清理ref，准备下一次对话
      streamingContentRef.current = '';
      streamingStepsRef.current = [];
      executionStepsRef.current = []; // 2026-08-27 小欧 三堂会审: 终态清理executionSteps
      // lastUpdateTimeRef.current = 0;

      // console.log("✅ [onComplete] AI回答保存完成！");
    },
    [
      setMessages,
      setLoading,
      setWaitTime,
      setIsRetrying,
      setSessionTitle,
      sessionId,
      // Refs dependencies
      currentSessionIdRef,
      streamingContentRef,
      streamingStepsRef,
      executionStepsRef,
      waitTimerRef,
    ]
  );

  // ==================== onError回调 ====================

  const onError = useCallback(
    (error: string | SSEError) => {
      // ✅ 支持字符串和对象两种格式
      // 2026-08-27 小欧 三堂会审A3修复: 显式标注SSEError类型, 消除冗长双重断言
      const errorObj: SSEError =
        typeof error === 'string'
          ? {
              type: 'error',
              error_type: 'unknown_error',
              error_message: error,
              timestamp: new Date().toISOString(),
            }
          : error;

      // 2026-08-27 小欧 三堂会审: 统一取错误消息, 去as unknown双重转换
      const pickMsg = (e: SSEError): string => {
        const o = e as SSEError & { message?: string };
        return o.error_message || o.message || '未知错误';
      };

      console.error('🔴 [onError] SSE 流式错误:', errorObj);

      // ⭐ 使用统一错误处理中心errorHandler处理提示
      const errorResult = handleSSEError(errorObj, {
        reconnectAttempts: 0,
        maxRetries: 0,
        onReconnect: undefined,
      });

      // 如果errorHandler认为不需要显示（如静默错误），则跳过
      if (errorResult.handled === false) {
        return;
      }

      // ⭐ 暂停时存入缓冲区（原有逻辑保留）
      if (isPausedRef.current) {
        displayBufferRef.current.push({ type: 'error', error: errorObj });
        return;
      }

      // 【小沈注释 2026-04-18】去掉节流机制，每次都更新UI
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          // 【修改 2026-06-09 小沈】直接使用message中的executionSteps
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            // 错误时直接用错误消息替换内容，不保留"思考中"
            // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
            content: pickMsg(errorObj), // 2026-08-27 小欧 三堂会审: 统一取错误消息
            isError: true,
            isStreaming: false,
            executionSteps: lastMessage.executionSteps || [], // 直接使用message中的steps
            // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
            errorType: errorObj.error_type,
            errorMessage: pickMsg(errorObj), // 2026-08-27 小欧 三堂会审: 统一取错误消息(原回落'')
            errorRetryAfter: errorObj.retry_after,
            errorTimestamp: errorObj.timestamp,
            errorContext: errorObj.context,
            // 如果 errorObj 中没有 model/provider，使用消息中已有的值
            model: errorObj.model || lastMessage.model,
            provider: errorObj.provider || lastMessage.provider,
          };
          return updated;
        }
        // 2026-08-27 小欧 修复#4: 末条非 assistant(重连/无占位)时新建 assistant 错误消息, 不再静默丢弃
        const newErrorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: pickMsg(errorObj),
          isError: true,
          isStreaming: false,
          executionSteps: [],
          timestamp: new Date(),
          errorType: errorObj.error_type,
          errorMessage: pickMsg(errorObj),
          errorRetryAfter: errorObj.retry_after,
          errorTimestamp: errorObj.timestamp,
          errorContext: errorObj.context,
          model: errorObj.model,
          provider: errorObj.provider,
        };
        return [...prev, newErrorMessage];
      });

      // 清理状态
      setLoading(false);
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
        waitTimerRef.current = null;
      }
      setWaitTime(0);
      setIsRetrying(false);

      // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
      logAIError(pickMsg(errorObj)); // 2026-08-27 小欧 三堂会审: 统一取错误消息

      // ⭐ 完成后清理ref
      streamingContentRef.current = '';
      streamingStepsRef.current = [];
      executionStepsRef.current = []; // 2026-08-27 小欧 三堂会审: 终态清理executionSteps
      // lastUpdateTimeRef.current = 0;
    },
    [
      setMessages,
      setLoading,
      setWaitTime,
      setIsRetrying,
      // Refs dependencies
      isPausedRef,
      displayBufferRef,
      streamingContentRef,
      waitTimerRef,
    ]
  );

  // ==================== onPaused回调 ====================

  const onPaused = useCallback(() => {
    console.log('⏸️ [onPaused] SSE 暂停');
    setIsPaused(true);
    // 2026-08-27 小欧 修复#3: 同步 isPausedRef.current, 否则服务端暂停不生效(分块仍直接显示而非缓冲)
    isPausedRef.current = true;
  }, [setIsPaused, isPausedRef]);

  // ==================== onResumed回调 ====================

  const onResumed = useCallback(() => {
    console.log(
      '▶️ [onResumed] 收到恢复事件，缓冲区长度:',
      displayBufferRef.current.length
    );

    // 编辑历史: 2026-08-28 小欧 - BUG10修复: onResumed改用displayBufferRef.current.forEach+单次setMessages原子合并
    const errorItems: Array<string | SSEError> = [];

    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (
        lastMessage &&
        lastMessage.role === 'assistant' &&
        lastMessage.isStreaming
      ) {
        let content = lastMessage.content;
        const newSteps = [...(lastMessage.executionSteps || [])];

        displayBufferRef.current.forEach((data) => {
          const item = data as BufferItem;
          if (item.type === 'chunk' && item.content) {
            content += item.content;
          } else if (item.type === 'step' && item.step) {
            newSteps.push(item.step);
          } else if (item.type === 'error' && item.error) {
            errorItems.push(item.error);
          }
        });

        const updated = [...prev];
        updated[updated.length - 1] = {
          ...lastMessage,
          content,
          executionSteps: newSteps,
        };
        return updated;
      }
      return prev;
    });

    // error类型需单独处理（调用onError回调）
    for (const err of errorItems) {
      onError(err);
    }

    // 清空缓冲区
    displayBufferRef.current = [];

    // 2026-08-27 小欧 修复#2: 同步复位 isPausedRef.current, 否则恢复后分块仍进缓冲而丢失
    isPausedRef.current = false;
    // 更新暂停状态
    setIsPaused(false);

    // 通知流式组件恢复接收
    if (streaming?.setIsReceiving) {
      streaming.setIsReceiving(true);
    }
  }, [setMessages, setIsPaused, onError, streaming, displayBufferRef]);

  // ==================== onRetry回调 ====================

  const onRetry = useCallback(
    (message: string, waitTime?: number) => {
      console.log('🔄 [onRetry] 收到重试事件:', message, '等待时间:', waitTime);
      setIsRetrying(true);
      if (waitTime !== undefined) {
        setWaitTime(waitTime);
      } else {
        setWaitTime(0);
      }
    },
    [setIsRetrying, setWaitTime]
  );

  // ==================== 返回值 ====================

  // 【v3.4新增 2026-06-09 小沈】授权请求回调
  const onAuthorizationRequired = useCallback(
    (data: {
      confirm_id: string;
      tool_name: string;
      params: Record<string, unknown>;
      safety_level: string;
      // 2026-09-03 小欧 Bug-26: 类型补全 4→8 字段, 全量透传 trust/计时字段保弹窗正确渲染
      trust_path?: string | null;
      auto_confirm?: boolean;
      confirm_timeout?: number;
      backend_timeout?: number;
    }) => {
      console.log('[Authorization] 收到授权请求:', data);
      // 触发授权弹窗（通过自定义事件通知NewChatContainer）
      window.dispatchEvent(
        new CustomEvent('authorization_required', { detail: data })
      );
    },
    []
  );

  return {
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onRetry,
    onAuthorizationRequired, // 【v3.4新增】
  };
};
