// 编辑历史: 2026-07-18 小欧 - FinalStep终态规整: 取消判定改为type=final+outcome=cancelled
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.5-9删后端自动保存死代码/10抽pickMsg/11终态清executionSteps
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - hooks修复#1/2/3/4/5/6/7/8: 取消事件识别/暂停ref同步/末条非assistant回写/thought回落/暂停分块保留
// 编辑历史: 2026-08-28 小强 - hooks修复#9: onComplete依赖数组补executionStepsRef/streamingStepsRef(闭包陈旧)
// 编辑历史: 2026-08-28 小强 - hooks修复#10: onResumed缓冲区回放改为单次setMessages原子合并(防批处理乱序)
// 编辑历史: 2026-08-28 小强 - hooks修复#11: 删onComplete后端保存空分支+else warn(YAGNI, 后端已自动落库)
// 编辑历史: 2026-09-03 小欧 Bug-26: onAuthorizationRequired 类型补全 4→8 字段(trust_path/auto_confirm/confirm_timeout/backend_timeout), 与 sseParser 下发契约一致, 全量透传保弹窗正确渲染 — 小欧-2026-09-03
// 编辑历史: 2026-09-07 小欧 - 4.4.1取消终态: isCancelEvent 窄化为 type=final+outcome=cancelled(删 type=cancelled
//   分支)/isStreaming 终态条件同步移除 cancelled/取消日志文案对齐新契约 — 小欧-2026-09-07
// 编辑历史: 2026-09-08 小欧 - 六章6.3.3(北京老陈裁定回归总原则): onError 分道——errorObj.from_backend===true
//   (后端业务错误) 时只清三refs即return, 不进 handleSSEError(弹窗)与 isPausedRef(缓冲)与 setMessages(P2红字),
//   不等下发 loading/计时(计时不停) — P3 由 useChatFacade 包装器(6.3.4)无条件写入 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - A1修复(356步残留类累积根治): onStep入口任务内指纹去重(type|step|preview|content前64),
//   拦截 SSE 重复行/重连GET重放导致的同一执行轮事件重复 append; preview 与 canonical 因 preview 位不同不误杀,
//   chunk 逐块 content 不同不误杀; onComplete/onError 终态 clear Set 供下任务重新计数 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - A类死代码清理: 删handleApiError/ErrorType/sessionApi死导入; onCancel/其他useCallback依赖数组去setIsPaused(272-274)与sessionId(497-503);
//   连带删除解构sessionId/setSessionTitle(死解构) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B4/B5: onError依赖数组真补streamingStepsRef/executionStepsRef(修复终态清空时机陈旧);
//   onResumed依赖数组真补isPausedRef(修复缓冲复位时机陈旧) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「该清理的清理」): 删 onStep 每步「📝 type= timestamp=」打点
//   ——sseParser 各 case 已统一打 [STEP]/[ACTION] [收到数据], 此处与解析层重复(D.R.Y); 删 onComplete 注释掉的死日志
//   (AI回答保存完成 等)——终态已由 ✅ type=AI流式完成 保留打点(测试断言锚点) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 失败终态修复(北京老陈「还是没有找到问题在哪里」追问实证): onComplete 前置判定
//   final.outcome=failed / final.error_type 有值——失败任务优先展示 final.response('任务执行失败')并置 isError 错误态,
//   不再把 responseBuffer 全程累积的思考草稿(实证 4333字 = 五轮流式chunk: 1737+169+447+668+1312)当"完整回复"正常展示;
//   与 sseParser final 分支 outcome/error_type/error_message 透传配套, 正常/cancelled 终态不受影响 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - bug-2修复(task2 step5/step6丢失): onComplete 读 lastMessage.executionSteps 是 React
//   批处理旧态(不含 final step), 导致 PipelineRenderer 缺数据; 改为优先取 executionStepsFromSSE(sseParser 传入的完整
//   ref 含 final), 与 sseParser final 分支 :499-500 更新 ref + :520 读 ref + :522 传参配套 — 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - 阶段一零风险清障: ①S1 删streamingStepsRef解构+清空+依赖数组(133/528/539/576/664/680);
//   ②S5 onResumed复位提前(isPausedRef=false移至for回放循环前, 根治死循环);
//   ③S6 cancelInProgress收紧(条件从!isCancelEvent&&type!=='final'改为!isCancelEvent, 根治双final) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段二S2收尾(方案A): useChatCallbacks 彻底移除 executionStepsRef 依赖——
//   ①读点(onComplete 失败终态判定)改取 sseParser 三参 executionStepsFromSSE, fallback 置空(该接口永传三参);
//   ②清空点(终态/from_backend/错误)删除——useSSE 新请求经 clearSteps()(:660-672) 统一清 executionSteps state+ref,
//   此处冗余; executionSteps 生命周期自此归 useSSE 单一职责 — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - [A1/A2/A3/A5/A8]暂停/取消终态五缺陷修复(北京老陈排查35失败, 全部系统缺陷)——
//   ①A1 onResumed 回放分块未累积 streamingContentRef, 后续 onChunk 以暂停前旧值拼正文覆盖缓冲内容;
//   ②A2 缓冲 chunk 的 is_reasoning 回放丢失; ③A3 并发暂停无计数, 单恢复全复位(并发HITL场景破坏);
//   ④A5 onComplete 不检查 cancelInProgressRef, 取消窗口期 completed 终态被当正常完成写入;
//   ⑤A8 errorItems 在 setMessages updater 内收集, 末条 isStreaming=false 时 updater return → error 永久丢弃
//   (重构: error 收集移出条件, 回放与错误处理解耦) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - S22 错误终态幂等清理: onError from_backend 分道之后插入 request_level 判据闸门
//   (isRequestLevel = step===0 || error_type==='request_timeout'), 请求级错误立即清 waitTimerRef+指纹Set,
//   执行级错误保持"等 final"不动; 幂等保证——即便随后 final 到达, onComplete 再清无副作用 — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - [A9]final暂停期到达后onResumed不再重置接收态: setIsReceiving 加
//   hasReplayable 守卫——final 在暂停期间到达 → onComplete 设 isStreaming=false → onResumed
//   若无条件 setIsReceiving(true) 会把已结束的流重新标记为接收中, 任务结束后 UI 再次转"等待图标";
//   无回放内容(流已终态/空暂停)不重置 isReceiving — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 契约化(method2, 北京老陈 2026-09-11 定案): 空响应判断删除对 SSE 实时
//   thought 步骤的依赖(thought=仅历史回显事件, 实时 SSE 永不发, 后端 _SSE_EXCLUDE_TYPES 过滤)。
//   原 hasThoughtContent 兜底是 thought 泄漏到实时流时期"把思考草稿顶成回答"的历史错逻辑(老陈指正
//   "前端的毛病"), 现回归"真实产出正文"判断: final.response ∨ final.thought — 小欧-2026-09-11
// 编辑历史: 2026-09-13 小欧 - Prettier 格式统一(前端源码格式专项, 纯格式零逻辑): 对齐项目 prettier 排版规范 — 小欧-2026-09-13
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

import { useCallback, useRef } from 'react'; // 2026-09-09 小欧 A1: 加useRef(任务内指纹去重Set) — 小欧-2026-09-09
import type { Message } from '../../../types/chat';
import type { ExecutionStep } from '../../../types/execution';
import type { UseChatStateReturn } from './useChatState';
import { handleSSEError } from '@/services/error/handler';
import { logAIComplete, logAIError } from '../../../utils/logStyles';

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

    // Refs
    messagesEndRef,
    currentSessionIdRef,
    displayBufferRef,
    isPausedRef,
    streamingContentRef,

    logFlagsRef,
    hasReceivedCancelEventRef,
    cancelInProgressRef,
    waitTimerRef,
  } = state;

  // ==================== onStep回调 ====================

  // ---- A1(2026-09-09 小欧): 任务内步骤指纹去重 ----
  // 根治356步残留类累积: sseParser 对同一SSE行/重连GET重放会无条件 append + onStep 回调,
  //   前端无 seq 去重护栏, 同一执行轮事件(断线重连续传尤甚)被重复消费直入消息 executionSteps.
  //   此处以"任务内指纹Set"在唯一消费枢纽拦截: 指纹=type|step|preview|content(前64字符),
  //   preview 与 canonical 因 preview 位不同不误杀, chunk 逐块 content 不同不误杀;
  //   onComplete/onError 终态清空 Set, 供下一任务重新计数 — 小欧-2026-09-09
  const onStepFingerprintRef = useRef<Set<string>>(new Set());
  const _dbgRoundRef = useRef(0); // [DEBUG-4] 轮次计数器
  // 小欧 2026-09-10 [A3]: 并发暂停计数 —— 多个暂停来源(并发HITL/服务端)依次进入,
  //   仅当最后一个来源恢复才解除暂停; 单恢复不再误灭其他来源的暂停
  const pauseCountRef = useRef(0);

  const onStep = useCallback(
    (step: ExecutionStep) => {
      // [DEBUG-4] 2026-09-09 执行路径追踪(轮次)
      if (step.type === 'thought-start') _dbgRoundRef.current++;
      console.log(`[DBG-4] → ${step.type}/R${_dbgRoundRef.current}`);
      // A1(2026-09-09 小欧): 指纹去重——同 type|step|preview|content(前64) 事件视为重放/重复行跳过,
      //   防 executionSteps 无界膨胀(356步残留)与渲染错乱 — 小欧-2026-09-09
      const fingerprint = [
        step.type,
        step.step ?? '',
        step.preview ? 'p' : '',
        (step.content ?? '').slice(0, 64),
      ].join('|');
      if (onStepFingerprintRef.current.has(fingerprint)) {
        // [onStep] 去重跳过重复事件
        return;
      }
      onStepFingerprintRef.current.add(fingerprint);
      // 【北京老陈 2026-07-12 小欧】统一取消语义：interrupted → cancelled
      // 2026-09-07 小欧 4.4.1: type=cancelled 已从链路移除, 取消心跳/收尾单一由 final+outcome=cancelled 承担
      const isCancelEvent =
        step.type === 'final' && step.outcome === 'cancelled';
      if (isCancelEvent) {
        hasReceivedCancelEventRef.current = true;
        // 2026-09-07 小欧 4.4.1(B10): 日志文案对齐新契约, type=cancelled 事件已不存在
        console.log('[取消] 收到取消终态 final+cancelled');
      }

      // ✅ 如果正在取消中，跳过非取消且与终态无关的事件（避免旧 chunk/步骤污染 UI）
      // 2026-08-27 小欧 修复#1/10: 取消进行中允许 final 终态步骤通过, 否则 final(completed)被吞导致消息无内容
      if (cancelInProgressRef.current) {
        // 小欧 2026-09-10 S6: 取消态只放行 cancelled 帧
        // 原条件 type !== 'final' 放行了 final(completed)，导致双 final
        if (!isCancelEvent) {
          console.log(`[取消] 忽略取消过程中收到的事件: ${step.type}`);
          return;
        }
        // 是取消事件或 final 终态，继续处理（显示到 UI）
      }

      // 2026-08-27 小欧 修复#8: 删除"收到非chunk步骤即复位暂停"逻辑, 否则用户/服务端暂停被任意步骤打破(暂停形同虚设)
      // 暂停仅在 onResumed 时由 isPausedRef.current=false 显式解除, 暂停期间步骤统一进 displayBufferRef 缓冲

      // type 处理流程日志（解析 -> 存储 -> 渲染）
      // 2026-09-09 小欧 清理: sseParser 各 case 已统一打 [STEP]/[ACTION] [收到数据], 此处 📝 type= 每step重复打点即删(DRY)

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
          // 因为后端可能直接发 paused/retrying/resumed，不发 start(2026-09-07 小欧 4.4.1: cancelled 移出该集合)
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
        // [DEBUG-4d] 2026-09-09 北京老陈 追加step到已有消息
        console.log(
          `[DBG-4d] onStep: 追加到assistant消息 type=${step.type} step=${step.step}`,
          `msgSteps=${(lastMessage.executionSteps || []).length}→${(lastMessage.executionSteps || []).length + 1}`
        );
        updated[updated.length - 1] = {
          ...lastMessage,
          content: stepDisplayContent,
          executionSteps: [...(lastMessage.executionSteps || []), step], // 直接追加到现有steps
          // final/error 时必须设置 isStreaming=false，停止 DynamicStatusDisplay
          // 2026-09-07 小欧 4.4.1: type=cancelled 已从链路移除, 条件不再需要
          isStreaming:
            step.type !== 'error' && step.type !== 'final'
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
      // 小欧 2026-09-10 [A5]: 取消进行中 final(completed) 不当正常完成写入消息 ——
      //   cancelInProgress 窗口期后端 completed 终态短窗到达, 否则与"取消=静默收尾"语义冲突;
      //   取消终态由 cancelled final 帧经 onStep 展示, 此处直接 return(标志由 useChatTaskControl finally 复位)
      if (cancelInProgressRef.current) {
        console.log('[onComplete] 取消进行中，跳过完成态写入');
        return;
      }

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

      // 【2026-09-09 小欧 失败终态先判定】
      // 实证案例(004924): final.outcome=failed/error_type=quota_exceeded, 但 responseBufferRef 全程累积
      //   5轮流式思考草稿(4333字, 1737+169+447+668+1312 精确) → 原逻辑 fullResponse 非空即跳过判空分支,
      //   isError 恒 false, 失败任务被当"完整回复"正常展示。此处前置判定: 失败终态优先展示 final.response
      //   失败文案并置错误态, 杜绝草稿冒充最终回答 — 小欧-2026-09-09
      const sseStepsAll = executionStepsFromSSE || [];
      const finalStepAll = sseStepsAll.find(
        (s: ExecutionStep) => s.type === 'final'
      ) as (ExecutionStep & Record<string, unknown>) | undefined;
      if (
        (finalStepAll?.outcome as string) === 'failed' ||
        (finalStepAll?.error_type as string)
      ) {
        console.warn(
          '🔴 [onComplete] 终态失败: outcome=%s error_type=%s, 展示失败文案而非思考草稿',
          finalStepAll?.outcome,
          finalStepAll?.error_type
        );
        finalResponse = (finalStepAll?.response as string) || '任务执行失败';
        isError = true;
        errorType = finalStepAll?.error_type as string | undefined;
        errorMessage = finalStepAll?.error_message as string | undefined;
      } else if (!finalResponse || !finalResponse.trim()) {
        // 2026-09-11 小欧 契约化(method2, 北京老陈 2026-09-11 定案): 删除对 SSE 实时 thought 步骤的依赖——
        //   thought=仅历史回显事件(DB executionSteps), 实时 SSE 永不发(后端 _SSE_EXCLUDE_TYPES 过滤)。
        //   原 hasThoughtContent(SSE thoughtSteps) 兜底是 thought 泄漏到实时流时期"把思考草稿顶成回答"
        //   的历史错逻辑; 真实空响应(模型零输出, 无 final.response/thought)即判 empty_response — 小欧-2026-09-11
        const sseSteps = executionStepsFromSSE || [];
        const finalStep = sseSteps.find(
          (s: ExecutionStep) => s.type === 'final'
        ) as (ExecutionStep & Record<string, unknown>) | undefined;
        const finalStepResponse = (finalStep?.response as string) || '';
        const finalStepThought = (finalStep?.thought as string) || '';

        // response或thought任一有内容，都不算error
        const hasValidContent =
          (finalStepResponse && finalStepResponse.trim()) ||
          (finalStepThought && finalStepThought.trim());

        if (hasValidContent) {
          finalResponse = finalStepResponse || finalStepThought;
          console.info(
            '✅ finalResponse为空但final步骤有有效内容，不标记error'
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
          // 2026-09-09 小欧 bug-2修复: sseParser final分支在调onComplete前已将final step追加到ref(:499-500),
          //   并作为executionStepsFromSSE(:520)传入; 此处优先用它(含final), 防React批处理prev旧态覆盖
          const finalSteps =
            executionStepsFromSSE &&
            executionStepsFromSSE.length >
              (lastMessage.executionSteps?.length || 0)
              ? executionStepsFromSSE
              : lastMessage.executionSteps || [];

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

      // A1(2026-09-09 小欧): 终态清空任务内指纹去重Set, 供下一任务重新计数 — 小欧-2026-09-09
      onStepFingerprintRef.current.clear();
    },
    [
      setMessages,
      setLoading,
      setWaitTime,
      setIsRetrying,
      // Refs dependencies
      currentSessionIdRef,
      streamingContentRef,
      waitTimerRef,
      cancelInProgressRef,
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

      // 2026-09-08 小欧 6.3.3 分道: 后端业务错误(from_backend=true)只进P3——不弹窗/不替换消息/不进缓冲/不停计时,
      //   仅清三refs准备下一轮(最终终态由随后 final 承担); P3 显示由 useChatFacade 包装器(6.3.4)无条件写入 — 小欧-2026-09-08
      if (errorObj.from_backend === true) {
        console.info(
          '[onError] 后端业务错误: 只进P3, 不弹窗/不替换消息/不停计时 (6.3.3)'
        );
        streamingContentRef.current = '';

        // A1(2026-09-09 小欧): from_backend 错误后会话终止, 同步清空任务内指纹Set——查漏补洞:
        //   防"错误后异常断链(无 final/无 onComplete)致 Set 残留, 下一任务同 step 同 content 被误拦" — 小欧-2026-09-09
        onStepFingerprintRef.current.clear();
        return;
      }

      // 小欧 2026-09-10 S22: request_level 幂等清理闸门
      // 仅请求级错误(整个请求失败, 不可能再有 final)做终态清理
      // 执行级错误(blocked/timeout, 任务仍继续)保持"等 final"不动
      const isRequestLevel =
        errorObj.step === 0 || errorObj.error_type === 'request_timeout';
      if (isRequestLevel) {
        console.info('[onError] 请求级错误: 幂等清理 waitTimer + 聚合状态');
        if (waitTimerRef.current) {
          clearInterval(waitTimerRef.current);
          waitTimerRef.current = null;
        }
        onStepFingerprintRef.current.clear();
      }

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

      // A1(2026-09-09 小欧): 终态清空任务内指纹去重Set, 供下一任务重新计数 — 小欧-2026-09-09
      onStepFingerprintRef.current.clear();
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
    // 小欧 2026-09-10 [A3]: 并发暂停计数 —— 每来源暂停计数+1, isPaused 恒为 true(最强暂停语义)
    pauseCountRef.current += 1;
    setIsPaused(true);
    // 2026-08-27 小欧 修复#3: 同步 isPausedRef.current, 否则服务端暂停不生效(分块仍直接显示而非缓冲)
    isPausedRef.current = true;
  }, [setIsPaused, isPausedRef, pauseCountRef]);

  // ==================== onResumed回调 ====================

  const onResumed = useCallback(() => {
    console.log(
      '▶️ [onResumed] 收到恢复事件，缓冲区长度:',
      displayBufferRef.current.length
    );

    // 小欧 2026-09-10 [A3]: 并发暂停计数递减 —— 仍有其他来源暂停时保持暂停, 不清缓冲不回放;
    //   最后一个来源恢复才统一回放(缓冲数据跨来源累积, 提前回放会破坏暂停中来源的暂存)
    if (pauseCountRef.current > 0) pauseCountRef.current -= 1;
    if (pauseCountRef.current > 0) {
      console.log(
        `⏸️ [onResumed] 仍有 ${pauseCountRef.current} 个暂停来源, 保持暂停`
      );
      return;
    }

    // 小欧 2026-09-10 [A8]: error 收集移出 setMessages 条件 —— 原实现 errorItems 在 updater 内收集,
    //   最后一条消息 isStreaming=false(暂停期 final 已定稿)时 updater 整体 return, error 一个都收不到,
    //   且 buffer 随后被清空 → error 永久丢失。先独立遍历收集, 再决定回放。
    const buffered = displayBufferRef.current;
    const errorItems: Array<string | SSEError> = [];
    let hasReplayable = false;
    for (const data of buffered) {
      const item = data as BufferItem;
      if (item.type === 'error' && item.error) {
        errorItems.push(item.error);
      } else if (
        (item.type === 'chunk' && item.content) ||
        item.type === 'step'
      ) {
        hasReplayable = true;
      }
    }

    // 编辑历史: 2026-08-28 小欧 - BUG10修复: onResumed改用单次setMessages原子合并(防批处理乱序)
    if (hasReplayable) {
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
          lastMessage.isStreaming
        ) {
          let content = lastMessage.content;
          let isReasoning = lastMessage.is_reasoning;
          const newSteps = [...(lastMessage.executionSteps || [])];

          for (const data of buffered) {
            const item = data as BufferItem;
            if (item.type === 'chunk' && item.content) {
              content += item.content;
              // 小欧 2026-09-10 [A1]: 回放分块同步累积 streamingContentRef —— 原实现只合并消息内容,
              //   sCR 保持暂停前旧值, 后续 onChunk 以旧值拼正文 → 缓冲内容被覆盖永久丢失
              streamingContentRef.current += item.content;
              // 小欧 2026-09-10 [A2]: 回放分块回带 is_reasoning —— 缓冲 chunk 的思考标记不丢失
              if (item.is_reasoning !== undefined) {
                isReasoning = item.is_reasoning;
              }
            } else if (item.type === 'step' && item.step) {
              newSteps.push(item.step);
            }
          }

          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            content,
            executionSteps: newSteps,
            is_reasoning: isReasoning,
          };
          return updated;
        }
        return prev;
      });
    }

    // 小欧 2026-09-10 S5: 先复位 isPausedRef 再回放 — 死循环根治
    // 原 isPausedRef 复位在回放循环之后(:747)，onError(:600) 命中暂停态
    // 将 error 推回 buffer → 死循环。提前到回放前，onError 不再命中暂停。
    isPausedRef.current = false;

    // error类型需单独处理（调用onError回调）
    for (const err of errorItems) {
      onError(err);
    }

    // 清空缓冲区
    displayBufferRef.current = [];

    // 更新暂停状态
    setIsPaused(false);

    // 通知流式组件恢复接收（仅当有可回放数据时 —— 流仍活跃;
    //   无回放内容说明流已终态(isStreaming=false)或空暂停, 不应重置 isReceiving）
    //   小欧 2026-09-10 [A9]: final 到达暂停期间 → onComplete 设 isStreaming=false →
    //   onResumed 不应将已结束的流重新标记为接收中
    if (hasReplayable && streaming?.setIsReceiving) {
      streaming.setIsReceiving(true);
    }
  }, [
    setMessages,
    setIsPaused,
    onError,
    streaming,
    displayBufferRef,
    isPausedRef,
    streamingContentRef,
    pauseCountRef,
  ]);

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
