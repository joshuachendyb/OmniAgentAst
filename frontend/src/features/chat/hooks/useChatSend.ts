// 编辑历史: 2026-08-26 小欧 - 参与改造: 发送逻辑对齐CommandPanel/TaskType/contextLink
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 删pendingMessageIdRef(回滚靠userMessage.id)
// 编辑历史: 2026-08-27 小欧 - hooks修复#9: executeSend抛错清理isStreaming占位幽灵消息
// 编辑历史: 2026-08-28 小强 - hooks修复#12: 防重由loading state改isSendingRef(useRef同步), 消除双击竞态
// 编辑历史: 2026-08-29 小强 - 修复#20: 超长/网络失败early-return前复位isSendingRef, 避免绕过finally永久卡死发送 - 小强-2026-08-29
// 编辑历史: 2026-09-13 小欧 - 会话标题截断50→10(北京老陈复查, 30仍显冗长): 待界面查看效果 - 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 北京老陈定案: 生成端取消标题截断,创建会话存全量标题(截断只发生在显示端ChatHeader SESSION_TITLE_DISPLAY_MAX=10) - 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧 v1.3 - 复位点迁址 + async回滚(北京老陈裁定): ①finally不再无条件setLoading(false)
//   (loading复位职责归SSE终态: 正常完成→onFinal(:510)/error→onError(:655)/取消→resetUiFlags(:126)——根治
//   "任务执行中finally提前掐loading → 停止/暂停按钮消失"病根) ②catch分支显式兜底setLoading(false)
//   (取消失败/网络失败/发送异常路径不依赖SSE终态, 防loading永久为true卡"思考中") — 小欧-2026-09-15
// 编辑历史: 2026-09-30 14:30 小欧 - 自动建会话也上抛写 URL（原只 setSessionId，刷新后地址栏无 id）；删零读取的三入参
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.11: 第二参 contextLinkMode 改名 linkEnabled: boolean
//   (值随消息落库, 见 5.7.14), 继续透传至 chatStreamStore; 建会话逻辑(:142-157)不动 — 小欧-2026-10-03
/**
 * useChatSend Hook - 消息发送逻辑
 *
 * 功能：
 * - 消息验证（空消息、长度限制）
 * - 网络连接检查
 * - 乐观更新（先显示用户消息）
 * - 创建会话
 * - 发送消息
 * - 错误处理和回滚
 *
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-23
 */

import { useCallback, useRef } from 'react'; // 2026-08-28 小强: 加回useRef(isSendingRef同步防重)
import {
  handleError,
  classifyError,
  ErrorType,
} from '@/services/error/handler'; // 2026-10-07 小欧 - 文档[11] 3.5.4: classifyError 供 :174 SESSION_BUSY 分支
import { checkNetworkConnection } from '../../../utils/network';
import { showNetworkError } from '../../../utils/chatMessages';
import { sessionApi } from '../../../services/api/session.api';
import { API_BASE_URL } from '../../../services/api/client';
import { logUserSend } from '../../../utils/logStyles';
import type { Message } from '../../../types/chat';
import type { SendOpts } from '../../../types/chat'; // 2026-10-07 小欧 - 文档[11] 3.5.4(决策 14 对象参数)

interface UseChatSendOptions {
  // 状态
  // 2026-09-30 小欧 - 删 loading/messages/waitTime 三入参：声明并全量传入却函数体零读取，
  //   属假接口面（每加一处调用方都要跟着传三个没人用的值）
  sessionId: string | null;
  // 设置方法
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setSessionId: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setWaitTime: React.Dispatch<React.SetStateAction<number>>;
  // Refs
  waitTimerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
  currentSessionIdRef: React.MutableRefObject<string | null>;
  // 2026-10-07 小欧 - 文档[11] 决策 9/13: 供 handleSend 判"执行中插话"(仅此处读, 不新建 ref 副本)
  isReceiving: boolean;
  // 发送方法
  executeSend: (userMessage: Message, opts: SendOpts) => Promise<void>;
  // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话发送(执行中追加输入)——与 executeSend 分流,
  //   因 executeSend 的 isSendingRef 防双发与"新任务编排副作用"都不适用于插话(会破坏运行中任务)。
  interjectSend: (userMessage: Message) => Promise<void>;
  // 2026-09-30 小欧 - URL 写入的唯一出口（与 useChatSession 同一注入形状）：
  //   自动建会话原先只 setSessionId 不写 URL，导致该会话 id 从不进地址栏，刷新后退回
  //   "最近会话"猜测，且与 handleNewSessionInternal 的写 URL 行为不一致（写入口未收口）。
  onUrlSessionChange?: (sessionId: string | null) => void;
}

interface UseChatSendReturn {
  handleSend: (messageContent: string, opts: SendOpts) => Promise<void>;
}

/**
 * useChatSend Hook
 */
export const useChatSend = (options: UseChatSendOptions): UseChatSendReturn => {
  const {
    sessionId,
    setLoading,
    setSessionId,
    setMessages,
    setWaitTime,
    waitTimerRef,
    currentSessionIdRef,
    isReceiving, // 2026-10-07 小欧 - 文档[11] 3.5.4: 插话判定入参
    executeSend,
    interjectSend,
    onUrlSessionChange,
  } = options;

  // 2026-08-27 小欧 三堂会审: 回滚改靠userMessage.id, 删pendingMessageIdRef
  // 2026-08-28 小强 修复#12: useRef同步防重, 消除Boolean state异步绕过竞态
  const isSendingRef = useRef(false);

  const handleSend = useCallback(
    async (
      messageContent: string,
      { linkEnabled, allowInterject }: SendOpts
    ) => {
      // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话判定（执行中 + 开关开 = 追加输入, 非新任务）
      //   isSendingRef 只锁"新任务流"：它在 finally 复位, 而 finally 要等整条 SSE 跑完,
      //   即任务执行期间恒为 true。若不区分, 插话永远被本行挡掉(决策 9"开=执行中可用"落空)。
      const isInterject = allowInterject && isReceiving;
      // 1. 基础验证（插话不受 isSendingRef 约束, 也不占用该标记）
      if (!messageContent.trim()) return;
      if (!isInterject) {
        if (isSendingRef.current) return;
        isSendingRef.current = true;
      }

      // 2. 消息长度验证
      if (messageContent.trim().length > 5000) {
        handleError({
          message: '消息过长，请精简到5000字符以内',
          error_type: ErrorType.CONTENT_TOO_LONG,
        });
        isSendingRef.current = false; // 2026-08-29 小强 修复#20: early-return前复位防重标记, 避免绕过finally永久卡死
        return;
      }

      // 3. 设置加载状态
      setLoading(true);

      // 4. 网络连接检查
      try {
        const isNetworkOK = await checkNetworkConnection(API_BASE_URL);
        if (!isNetworkOK) {
          console.error('[handleSend] 网络连接异常');
          showNetworkError();
          setLoading(false);
          // 停止等待计时器
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }
          setWaitTime(0);
          isSendingRef.current = false; // 2026-08-29 小强 修复#20: 网络失败early-return前复位防重标记
          return;
        }
      } catch (error) {
        console.warn('[handleSend] 网络检查异常:', error);
      }

      // 5. 创建用户消息（乐观更新）
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user' as const,
        content: messageContent.trim(),
        timestamp: new Date(),
      };
      // 6. 乐观更新：立即添加到状态显示给用户
      setMessages((prev) => [...prev, userMessage]);
      logUserSend(userMessage.content);

      try {
        // 7. 创建会话（如果需要）
        let currentSessionId = sessionId;
        if (!currentSessionId) {
          const newSession = await sessionApi.createSession(
            messageContent.trim() // 2026-09-13 小欧 北京老陈定案: 生成端不截断,标题存全量(截断只在显示端,见ChatHeader SESSION_TITLE_DISPLAY_MAX)
          );
          currentSessionId = newSession.session_id;
          setSessionId(currentSessionId);
          currentSessionIdRef.current = currentSessionId;
          // 2026-09-30 小欧 - 自动建会话同样要把 id 写进 URL（经唯一写入口上抛），
          //   否则刷新后地址栏无 session_id，只能回退到"最近会话"猜测
          onUrlSessionChange?.(currentSessionId);
        } else {
          currentSessionIdRef.current = currentSessionId;
        }

        // 8. 发送消息
        // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话走独立投递路径(不建 assistant 占位/不清 steps/
        //   不重置取消态——executeSend 的新任务编排副作用会破坏正在跑的任务)。
        if (isInterject) {
          await interjectSend(userMessage);
        } else {
          await executeSend(userMessage, { linkEnabled, allowInterject });
        }

        // 9. 发送成功，不需要额外操作（用户消息已在列表中）
      } catch (error) {
        // 10. 发送失败，更新消息状态为failed（不移除消息）
        console.error('[handleSend] 发送失败:', error);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === userMessage.id
              ? { ...msg, sendStatus: 'failed' as const }
              : msg
          )
        );
        // 2026-10-07 小欧 - 文档[11] 决策 9/13: 以下三段是"新任务流"的失败清理,
        //   插话失败时**必须跳过**——它们会误伤正在跑的任务(删它的流式占位/清它的 loading 与等待计时器)。
        if (!isInterject) {
          // 2026-08-27 小欧 修复#9: 清理 executeSend 抛错残留的 isStreaming 占位 assistant 消息(幽灵消息), 避免会话卡"思考中"
          setMessages((prev) =>
            prev.filter(
              (msg) => !(msg.role === 'assistant' && msg.isStreaming === true)
            )
          );
          // 2026-09-15 小欧 [暂停/取消按钮不显示根因修复]: send失败时兜底重置loading（finally不再无条件重置）
          setLoading(false);
        }
        // 2026-10-07 小欧 三堂会审补 - 文档[11] 决策 20: SESSION_BUSY 分支先撤回乐观消息再上抛。
        //   决策 13 是"退回输入框"(消息不应留气泡), 但本函数 :159 已把该条标 failed 留在列表、
        //   ChatInput 回填 draft 后会形成"失败气泡 + 输入框草稿"双份。不撤回即与决策 13 矛盾。
        if (classifyError(error) === ErrorType.SESSION_BUSY) {
          setMessages((prev) =>
            prev.filter((msg) => msg.id !== userMessage.id)
          );
          handleError(error, { source: 'api' }); // 先按既有流程弹提示
          throw error; // 再上抛, 触发 ChatInput draft 回填
        }
        handleError(error, { source: 'api' });
      } finally {
        // 2026-09-15 小欧 [暂停/取消按钮不显示根因修复]: 删finally中无条件setLoading(false)
        // loading重置职责归SSE终态回调：正常完成→onFinal(:510)、错误→onError(:655)、取消→resetUiFlags(:126)
        // finally只负责清理防重标记和计时器
        // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话不碰这些(计时器属运行中任务, 清它=把等待钟面打没)
        if (!isInterject) {
          isSendingRef.current = false; // 2026-08-28 小强 修复#12: 重置防重标记
          // 停止等待计时器
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }
          setWaitTime(0);
        }
      }
    },
    [
      sessionId,
      setLoading,
      setSessionId,
      setMessages,
      setWaitTime,
      waitTimerRef,
      currentSessionIdRef,
      executeSend,
      interjectSend, // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话分流目标
      isReceiving, // 2026-10-07 小欧 - 文档[11]: 插话判定读它(漏依赖=判定用过期值)
      onUrlSessionChange,
    ]
  );

  return {
    handleSend,
  };
};

export default useChatSend;
