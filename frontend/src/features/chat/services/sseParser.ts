// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 抽离 processSSEData(1002-1835)与 normalizeIsReasoning(995-997)至特性层services, 零逻辑变更 - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 13.14 usage帧废止前端累加、直取后端本轮+三累计(P/C/T)四字段 - 小欧-2026-08-30
import type { ExecutionStep } from '@/types/execution';
import type { SSEMetadata, SSEError, TaskMetaFrames } from '@/types/sse';

// 2026-08-27 小欧 修复(B2/base-2): is_reasoning 归一化统一helper, 兼容 true/'true'/1/'1'
const normalizeIsReasoning = (v: unknown): boolean =>
  v === true || v === 'true' || v === 1 || v === '1';

const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    getCurrentExecutionSteps: () => ExecutionStep[];
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>; // 【小新添加 2026-03-15】用于同步更新 ref
    saveStepsToStorage?: (steps: ExecutionStep[]) => void; // 【小强添加 2026-03-18】保存到 sessionStorage
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, is_reasoning?: boolean) => void;
    onComplete?: (
      fullResponse: string,
      metadata?: string | SSEMetadata,
      executionSteps?: ExecutionStep[]
    ) => void;
    onError?: (error: string | SSEError) => void;
    onPaused?: () => void;
    onResumed?: () => void;
    onRetry?: (message: string, waitTime?: number) => void;
    onAuthorizationRequired?: (data: {
      confirm_id: string;
      tool_name: string;
      params: Record<string, unknown>;
      safety_level: string;
    }) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
    setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
    disconnect: (
      manualDisconnect?: boolean,
      clearStorage?: boolean,
      onDisconnect?: () => void
    ) => void;
    setServerTaskId?: (taskId: string) => void;
    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，用于断线重连 after_seq 续传
    onSeq?: (seq: number) => void;
    // 【小欧 2026-08-26 8.4.14】元信息帧状态注入（useSSE 闭包 state/ref 透传进模块级 processSSEData）
    setMetaFrames?: React.Dispatch<React.SetStateAction<TaskMetaFrames>>;
    usageAccumRef?: React.MutableRefObject<{
      prompt: number;
      completion: number;
      total: number;
    }>;
    lastUsageSeqRef?: React.MutableRefObject<number>;
  },
  _isProcessingRef: React.MutableRefObject<boolean>
) => {
  const {
    setExecutionSteps,
    saveStepsToStorage,
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onRetry,
    setCurrentResponse,
    responseBufferRef,
    setIsReceiving,
    setIsConnected,
    disconnect: _disconnect,
    setServerTaskId,
    onSeq,
  } = handlers;

  // 2026-08-27 小欧 修复: SSE数据行可能带前导空格, 先trim再判断前缀
  const trimmedLine = line.trim();
  if (!trimmedLine || !trimmedLine.startsWith('data: ')) {
    return;
  }

  try {
    let jsonStr = trimmedLine.slice(6);
    jsonStr = jsonStr.trim();
    const rawData = JSON.parse(jsonStr);

    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，断线重连时用于 after_seq 续传避免重复
    if (typeof rawData.seq === 'number' && onSeq) {
      onSeq(rawData.seq);
    }

    // 【小强修复 2026-03-18】统一处理timestamp转换
    // 后端有些字段返回字符串格式timestamp，前端需要转换为毫秒数
    let timestampValue = Date.now();
    if (rawData.timestamp) {
      if (typeof rawData.timestamp === 'number') {
        timestampValue = rawData.timestamp;
      } else if (typeof rawData.timestamp === 'string') {
        // 尝试解析字符串时间戳
        const parsed = Date.parse(rawData.timestamp);
        timestampValue = isNaN(parsed) ? Date.now() : parsed;
      }
    }

    const step: ExecutionStep = {
      type: rawData.type as ExecutionStep['type'],

      // 根据不同type使用不同字段（后端字段拆分方案）
      thinking_prompt: rawData.thinking_prompt,
      action_description: rawData.action_description,
      content: rawData.content,
      error_message: rawData.error_message,
      message: rawData.message,

      // 保留字段
      step: Number(rawData.step) || 1, // 2026-08-27 小欧 修复base-3: 加Number()数值化
      thought: rawData.thought, // Agent.thought的值
      // 2026-07-18 小欧 FinalStep 终态规整：终态统一 type=final，由 outcome 声明；同步解析出后端字段
      outcome: rawData.outcome,
      error_type: rawData.error_type,
      action: rawData.action, // 执行动作名称，与后端一致
      observation: rawData.observation, // 保留原始对象，用于调试
      result: rawData.result, // simplify_observation处理后的文本
      action_input: rawData.action_input, // 工具调用参数

      // 【小沈修复】思考过程与正式内容区分字段
      // 【小查修复】统一使用 snake_case: is_reasoning
      // 2026-08-27 小欧 修复B2/base-2: 统一归一化helper, 补'1'分支(原缺导致true被当false)
      is_reasoning: normalizeIsReasoning(rawData.is_reasoning),
      // reasoning: rawData.reasoning || "",  // 【小强删除 2026-04-08】reasoning与content重复，后端已删除

      timestamp: timestampValue,
    };

    if (rawData.task_id && setServerTaskId) {
      setServerTaskId(rawData.task_id);
    }

    switch (rawData.type) {
      // 【小欧 2026-08-26 8.4.3】start/startinfo 拆双（4.9.2.7）：
      //  - start.content=context_summary -> 元信息帧 contextSummary（任务信息条上下文概况，三分归位③），
      //    不进右侧查看区流水线（4.4.4）；user_message 对话界面已可见不重复渲染（4.9.1）；
      //    model/provider 由顶栏徽标承载（4.8.3-A）。
      //  - startinfo -> 元信息帧 startInfo（驱动状态徽标），同样不入步骤列表。
      case 'start':
      case 'startinfo': {
        if (rawData.type === 'start') {
          const summary =
            typeof rawData.content === 'string' ? rawData.content : '';
          handlers.setMetaFrames?.((prev) => ({
            ...prev,
            contextSummary: summary,
            startTimestamp: Date.now(),
          }));
          break;
        }
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          startInfo: {
            task_id: rawData.task_id,
            display_name: rawData.display_name,
            provider: rawData.provider,
            model: rawData.model,
            ai_message_id: rawData.ai_message_id,
          },
        }));
        break;
      }

      // thought-start："开始思考"实时信号 —— 业务流标记，入列且同步 ref（ThinkingStream 光标）
      case 'thought-start': {
        const ts: ExecutionStep = {
          type: 'thought-start',
          content: '',
          step: Number(rawData.step) || 1, // 2026-08-27 小欧 修复base-3: 加Number()
          timestamp: timestampValue,
        };
        setExecutionSteps((prev) => {
          const next = [...prev, ts];
          handlers.executionStepsRef.current = next;
          // 2026-08-27 小欧 三堂会审: thought-start为瞬时光标信号, 仅内存帧不落sessionStorage, 故无持久化逻辑
          return next;
        });
        onStep?.(ts);
        break;
      }

      // usage：单任务 token 帧 —— 后端直发本轮+三累计(P/C/T)，前端直存直显不另算【13.14】
      case 'usage': {
        if (typeof rawData.seq === 'number') {
          if (rawData.seq <= (handlers.lastUsageSeqRef?.current ?? -1)) break;
          if (handlers.lastUsageSeqRef)
            handlers.lastUsageSeqRef.current = rawData.seq;
        }
        const round = {
          prompt: rawData.prompt_tokens ?? 0,
          completion: rawData.completion_tokens ?? 0,
          total: rawData.total_tokens ?? 0,
        };
        const taskAcc = rawData.task_accumulated_tokens ?? null;
        const sessAcc = rawData.session_accumulated_tokens ?? null;
        const chainAcc = rawData.chain_accumulated_tokens ?? null;
        const taskLike = taskAcc
          ? {
              prompt: taskAcc.prompt_tokens ?? 0,
              completion: taskAcc.completion_tokens ?? 0,
              total: taskAcc.total_tokens ?? 0,
            }
          : { ...round };
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          usage: taskLike,
          roundUsage: round,
          taskAccumulated: taskAcc,
          sessionAccumulated: sessAcc,
          chainAccumulated: chainAcc,
        }));
        if (handlers.usageAccumRef)
          handlers.usageAccumRef.current = { ...taskLike };
        break;
      }

      // stats：耗时/轮次流式帧
      case 'stats': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          stats: {
            step_count: rawData.step_count,
            llm_call_count: rawData.llm_call_count,
            retry_count: rawData.retry_count,
            duration: rawData.duration,
          },
        }));
        break;
      }

      // final_stats：终态统计独立步（duration/tool_stats/artifacts）
      case 'final_stats': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          finalStats: {
            duration: rawData.duration,
            tool_stats: rawData.tool_stats,
            artifacts: rawData.artifacts,
            final_status: rawData.final_status,
            retry_count: rawData.retry_count,
          },
        }));
        break;
      }

      // context_overview：上下文概况帧
      case 'context_overview': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          contextOverview: {
            summary: rawData.summary ?? '',
            message_count: rawData.message_count,
            estimated_tokens: rawData.estimated_tokens,
            truncated: rawData.truncated === true,
            injected_ratio: rawData.injected_ratio,
          },
        }));
        break;
      }

      // truncated：输出截断提示帧（severity=warn，字段=content）
      case 'truncated': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          truncated: {
            content: rawData.content ?? '',
            severity: rawData.severity ?? 'warn',
          },
        }));
        break;
      }

      case 'thought': {
        const stepNum = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()
        console.log(
          `%c[STEP] [type=thought] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小沈修改2026-04-16】使用后端字段存储
        step.step = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()数值化
        step.timestamp = timestampValue; // 2026-08-27 小欧 修复base-1: 用已转换number
        // 后端有两个字段：content(完整思考内容)和thought(parsed获取的thought)
        step.content = rawData.content || ''; // 完整思考内容
        step.thought = rawData.thought || ''; // parsed的thought
        step.reasoning = rawData.reasoning || '';
        step.tool_name = rawData.tool_name || '';
        step.tool_params = rawData.tool_params || rawData.params || {}; // 兼容旧字段
        // console.log("🔍 [sse thought] step对象=", JSON.stringify(step));
        // 添加到步骤数组，显示思考过程
        // 【小新修复 2026-03-15 V2】在回调中同步更新 executionStepsRef.current
        // 根因：setExecutionSteps 更新 React state 是异步的，useEffect 依赖 executionSteps 更新
        //      但 useEffect 在 onComplete 调用时还未执行，导致 getCurrentExecutionSteps() 获取到旧值
        // 修复：在 setExecutionSteps 回调中同步更新 ref，确保其他代码立即获取到最新值
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      case 'chunk': {
        // 精简日志：chunk不打印，避免日志过多

        // 传递 is_reasoning 区分思考过程和最终答案
        const is_reasoning = normalizeIsReasoning(rawData.is_reasoning); // 2026-08-27 小欧 修复: 复用统一helper
        const chunkContent = rawData.content || '';
        responseBufferRef.current += chunkContent;
        setCurrentResponse(responseBufferRef.current);
        onChunk?.(chunkContent, is_reasoning);

        // 【小新修复 2026-03-15 V3】chunk只保存当前小块内容，不保存累积
        // 核心原则：保存不能多也不能少，每个chunk只保存当前增量
        //
        // 实时显示逻辑（NewChatContainer.tsx）：
        //   - content累加显示：lastMessage.content + chunk（这是正确的，需要累加才能看到完整内容）
        //
        // 保存数据逻辑（此处）：
        //   - chunk保存当前小块：step.content = chunkContent（不是累积，只存当前块）
        //   - final保存完整内容：在final事件中保存message.content完整内容
        //
        // 历史消息显示逻辑（MessageItem.tsx）：
        //   - 遍历所有chunk逐个显示（每个chunk只显示自己的内容）
        //   - 如果没有is_reasoning=false的chunk，则显示message.content补充
        //
        // 错误做法会导致的问题：
        //   - 如果chunk保存累积内容 → 导出JSON每个chunk都重复 → 数据错误
        //   - 历史教训：不能为了解决刷新问题而破坏保存数据的正确性！
        step.content = chunkContent;

        // 【小沈带小强修改 2026-03-17】
        // 问题描述：前端导出 JSON 时只有 3 个步骤（start, thought, chunk），但数据库有 55 个步骤
        // 【小强修复 2026-04-10】使用回调函数模式，与 start/thought/action/observation 保持一致
        // 问题：之前使用直接同步更新，导致 ref 和 state 不同步
        // 解决：在 setExecutionSteps 回调函数内部更新 ref，确保同步
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      case 'final': {
        const stepNum = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()
        console.log(
          `%c[STEP] [type=final] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小沈修改2026-04-16】添加step和timestamp字段
        step.step = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()数值化
        step.timestamp = timestampValue; // 2026-08-27 小欧 修复base-1: 用已转换number

        // 【小强修复 2026-04-15】后端final类型没有content字段，直接使用response
        // 解析后端所有字段
        step.response = rawData.response || '';
        step.is_finished = rawData.is_finished;
        step.thought = rawData.thought || '';
        step.is_streaming = rawData.is_streaming;
        step.is_reasoning = normalizeIsReasoning(rawData.is_reasoning); // 2026-08-27 小欧 修复B3: 归一化避免存字符串
        step.content = step.response; // content只用于前端显示，使用response的值

        if (step.content) {
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }

        // 设置 display_name、model、provider 字段
        step.display_name = rawData.display_name;
        step.model = rawData.model;
        step.provider = rawData.provider;

        // 【小欧 2026-08-26 8.4/8.8】FinalStep._extra_fields：token 终值 + 四维累计
        step.prompt_tokens = rawData.accumulated_usage?.prompt_tokens;
        step.completion_tokens = rawData.accumulated_usage?.completion_tokens;
        step.total_tokens = rawData.accumulated_usage?.total_tokens;
        step.llm_call_count_token = rawData.llm_call_count_token;
        step.task_accumulated_tokens = rawData.task_accumulated_tokens;
        step.session_accumulated_tokens = rawData.session_accumulated_tokens;
        step.chain_accumulated_tokens = rawData.chain_accumulated_tokens;

        const displayName = rawData.display_name;

        // 【关键修复 2026-04-13】在回调之前先更新ref，确保onComplete获取完整数据
        // 问题：setExecutionSteps回调是异步的，导致onComplete拿到旧值
        // 解决：先直接更新ref，再调用onComplete
        const updatedSteps = [...handlers.executionStepsRef.current, step];
        handlers.executionStepsRef.current = updatedSteps;

        // 【小查修复】保存final到executionSteps，以便导出功能能获取到
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);

        // 【关键修复 2026-04-13】在onComplete调用前手动构建完整的steps数组
        // 问题：setExecutionSteps回调是异步的，handlers.executionStepsRef.current已更新为最新值
        // 解决：直接使用已更新的ref
        const finalStepsWithCurrent = handlers.executionStepsRef.current;

        onComplete?.(
          responseBufferRef.current,
          {
            model: rawData.model,
            provider: rawData.provider,
            display_name: displayName,
          } as SSEMetadata,
          finalStepsWithCurrent
        );

        console.log(
          `[SSE] [连接断开] 时间=${new Date().toLocaleTimeString()} 收到steps=${handlers.getCurrentExecutionSteps().length}`
        );

        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case 'error': {
        const stepNum = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()
        console.log(
          `%c[STEP] [type=error] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小强修复 2026-04-15】后端error类型只有以下字段，只解析后端存在的字段
        // 【小欧 2026-08-18 三堂会审】P4 起 error 文本统一由 MetaStep.content 承载(新)，
        //   兼容读 content，再回退旧 ErrorStep 的 error_message，杜绝实时显示退化为'未知错误'
        const errorMsg = rawData.content || rawData.error_message || '未知错误';
        step.content = errorMsg;
        step.error_message = errorMsg;
        step.error_type = rawData.error_type || '';

        // 解析后端存在的字段
        if (rawData.step) {
          step.step = rawData.step;
        }
        if (rawData.model) {
          step.model = rawData.model;
        }
        if (rawData.provider) {
          step.provider = rawData.provider;
        }
        if (rawData.details !== undefined) {
          step.details = rawData.details;
        }
        if (rawData.stack !== undefined) {
          step.stack = rawData.stack;
        }
        if (rawData.context) {
          step.context = {
            step: rawData.context.step,
            model: rawData.context.model,
            provider: rawData.context.provider,
            thought_content: rawData.context.thought_content,
          };
        }
        if (rawData.retry_after !== undefined) {
          step.retry_after = rawData.retry_after;
        }
        if (rawData.timestamp) {
          step.timestamp = rawData.timestamp;
        }
        // 【小欧 2026-08-26 8.4】error 收敛为事件通知：不进执行步骤列表、不落库不回放
        // （4.9.2.6）；失败态展示 = 任务信息条状态徽标(final.outcome=failed) + RightViewer
        // 经 onError→liveErrorText 直渲错误行（8.10，非 StatusLine）+ 静态统计块错误项。
        // 文本读 content（P4 已收敛），回退 error_message。
        // 【小沈修改2026-04-15】传递完整的错误对象，统一使用error_message，删除code字段
        onError?.({
          type: 'error',
          error_type: rawData.error_type || 'unknown_error',
          error_message: errorMsg,
          model: rawData.model,
          provider: rawData.provider,
          details: rawData.details,
          stack: rawData.stack,
          retryable: rawData.retryable,
          retry_after: rawData.retry_after,
          context: rawData.context,
          timestamp: rawData.timestamp || timestampValue,
        });
        // 【小强修复 2026-04-09】关键：不再调用onComplete（和v0.8.75一致），error步骤由onError处理
        // v0.8.75版本没有调用onComplete，UI显示正常
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      // 【小欧 2026-08-26 8.4】action 新结构：exec_type(single/multi) + tools 数组
      // 单工具也是一个元素不做特判（4.9.2.9）；禁止保留 旧动作类型名 兼容分支
      case 'action': {
        const receiveTime = Date.now(); // 【收到数据】时间
        const actionStepNum = step.step; // step 序号
        const stepLabel = ` [type=action] [step=${actionStepNum}]`;

        step.exec_type = rawData.exec_type === 'multi' ? 'multi' : 'single';
        const tools: Array<{
          tool: string;
          target?: string;
          params?: Record<string, unknown>;
        }> = Array.isArray(rawData.tools)
          ? rawData.tools.map(
              (t: {
                tool: string;
                target?: string;
                params?: Record<string, unknown>;
              }) => ({
                tool: t.tool,
                target: t.target,
                params: t.params,
              })
            )
          : [];
        step.tools = tools;
        step.content = tools
          .map((t) => (t.target ? `${t.tool}(${t.target})` : t.tool))
          .join(' + ');

        // 【红色】收到数据
        console.log(
          `%c[ACTION]${stepLabel} [收到数据] 时间=${new Date(receiveTime).toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【蓝色】ExecutionSteps保存开始时间
        const execStepsStartTime = Date.now();
        console.log(
          `%c[ACTION]${stepLabel} [ExecutionSteps保存开始] 时间=${new Date(execStepsStartTime).toLocaleTimeString()}`,
          'color: blue; font-weight: bold;'
        );

        setExecutionSteps((prev) => {
          // 【蓝色】ExecutionSteps保存完成
          const execStepsDoneTime = Date.now();
          const execStepsDuration = execStepsDoneTime - execStepsStartTime;
          console.log(
            `%c[ACTION]${stepLabel} [ExecutionSteps保存完成] 完成=${new Date(execStepsDoneTime).toLocaleTimeString()} 耗时=${execStepsDuration}ms`,
            'color: blue; font-weight: bold;'
          );

          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;

          // 【紫色】sessionStorage保存开始时间
          const storageStartTime = Date.now();
          console.log(
            `%c[ACTION]${stepLabel} [sessionStorage保存开始] 时间=${new Date(storageStartTime).toLocaleTimeString()}`,
            'color: #006400; font-weight: bold;'
          );

          setTimeout(() => {
            try {
              // 【紫色】sessionStorage保存完成
              const storageDoneTime = Date.now();
              const storageDuration = storageDoneTime - storageStartTime;
              console.log(
                `%c[ACTION]${stepLabel} [sessionStorage保存完成] 完成=${new Date(storageDoneTime).toLocaleTimeString()} 耗时=${storageDuration}ms`,
                'color: #006400; font-weight: bold;'
              );
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });

        // 【青色】渲染开始时间点
        const renderStartTime = Date.now();
        console.log(
          `%c[ACTION]${stepLabel} [渲染开始] 时间=${new Date(renderStartTime).toLocaleTimeString()}`,
          'color: cyan; font-weight: bold;'
        );

        onStep?.(step);

        // 【青色】渲染完成时间点
        const renderDoneTime = Date.now();
        const renderDuration = renderDoneTime - renderStartTime;
        console.log(
          `%c[ACTION]${stepLabel} [渲染完成] 完成=${new Date(renderDoneTime).toLocaleTimeString()} 耗时=${renderDuration}ms`,
          'color: cyan; font-weight: bold;'
        );

        break;
      }

      // 【小沈修复 2026-04-11】新增：observation类型处理
      // 【小沈改造 2026-05-22】支持observation为JSON对象（第13章设计方案）
      case 'observation': {
        const stepNum = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()
        console.log(
          `%c[STEP] [type=observation] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        step.step = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()数值化
        step.timestamp = timestampValue; // 2026-08-27 小欧 修复base-1: 用已转换number
        step.code = rawData.code; // 状态码（SUCCESS/ERROR/WARNING）

        // 【兼容层 2026-05-22 小资】支持两种格式，添加完整性验证
        // 先检查null（typeof null === 'object'是历史bug）
        // 2026-08-27 小欧 三堂会审: 适配后端08-18新契约 — observation步骤仅携带rawData.tool_result数组(顶层), 无observation字段
        if (Array.isArray(rawData.tool_result) && rawData.tool_result.length) {
          // 新契约(§10.3.3(3)): tool_result数组在rawData顶层, 每元素自包含{tool_name,llm_data,data_text,other_data}
          const tr = rawData.tool_result as Array<Record<string, unknown>>;
          step.tool_result = tr; // 供ToolResultRenderer早退/DefaultRenderer读取
          const el = (tr[0] || {}) as Record<string, unknown>;
          const llmData = (el.llm_data as Record<string, unknown>) || {};
          const status = (llmData.status as Record<string, unknown>) || {};
          // data_text承载原data对象(JSON字符串), 解析为data供专用渲染器读取data.* — 2026-08-27 小欧 三堂会审
          let dataObj: Record<string, unknown> = {};
          const dataText = el.data_text;
          if (typeof dataText === 'string' && dataText.trim()) {
            try {
              dataObj = JSON.parse(dataText) as Record<string, unknown>;
            } catch {
              dataObj = { raw: dataText };
            }
          } else if (dataText && typeof dataText === 'object') {
            dataObj = dataText as Record<string, unknown>;
          }
          step.execution_result = {
            data: dataObj,
            llm_data: llmData,
            other_data: (el.other_data as Record<string, unknown>) || {},
          }; // 2026-08-27 小欧 三堂会审: 构造execution_result供专用渲染器读取data/llm_data, 修复删早退后渲染空回归
          step.tool_name = (el.tool_name as string) || '';
          step.tool_params = (el.tool_params as Record<string, unknown>) || {};
          step.return_direct = Boolean(
            (el.other_data as Record<string, unknown>)?.return_direct
          );
          step.summary = (llmData.summary as string) || '';
          step.execution_status =
            (status.exec_code as 'success' | 'error' | 'warning') || undefined;
          step.error_message = (status.message as string) || undefined;
          step.content = step.summary;
          step.parallel_results =
            (rawData.parallel_results as typeof step.parallel_results) ||
            undefined;
        } else if (
          rawData.observation !== null &&
          rawData.observation !== undefined &&
          typeof rawData.observation === 'object'
        ) {
          // 兼容旧格式（observation 对象）
          const obsData = rawData.observation as Partial<{
            llm_data: Record<string, unknown>;
            tool_result: unknown;
            other_data: Record<string, unknown>;
            summary: string;
            tool_name: string;
            tool_params: Record<string, unknown>;
            return_direct: boolean;
            execution_status?: string;
            error_message?: string;
          }>;
          const llmDataRaw = obsData.llm_data;
          const llmData = (
            Array.isArray(llmDataRaw) ? llmDataRaw[0] : llmDataRaw
          ) as Record<string, unknown> | undefined;
          const otherData = obsData.other_data as
            | Record<string, unknown>
            | undefined;
          step.observation = obsData;
          step.tool_result = obsData.tool_result;
          step.execution_result = obsData;
          step.tool_name =
            ((llmData?.action as Record<string, unknown>)?.tool as string) ??
            obsData.tool_name ??
            '';
          step.tool_params =
            ((llmData?.action as Record<string, unknown>)?.params as Record<
              string,
              unknown
            >) ??
            obsData.tool_params ??
            {};
          step.return_direct =
            (otherData?.return_direct as boolean) ??
            obsData.return_direct ??
            false;
          step.summary = (llmData?.summary as string) ?? obsData.summary ?? '';
          step.execution_status =
            ((llmData?.status as Record<string, unknown>)?.exec_code as
              | 'success'
              | 'error'
              | 'warning') ??
            (obsData.execution_status as 'success' | 'error' | 'warning') ??
            undefined;
          step.error_message =
            ((llmData?.status as Record<string, unknown>)?.message as string) ??
            obsData.error_message;
          step.content = step.summary;
          step.parallel_results = (
            obsData as { parallel_results?: typeof step.parallel_results }
          ).parallel_results;
        } else {
          // 旧格式：observation是字符串或null/undefined
          const obsStr =
            rawData.observation != null ? String(rawData.observation) : '';
          step.observation = obsStr;
          step.tool_name = rawData.tool_name ?? '';
          step.tool_params = rawData.tool_params ?? {};
          step.return_direct = rawData.return_direct ?? false;
          step.content = obsStr;
        }

        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      // 【北京老陈 2026-07-13 小欧】incident 类型已废弃: 后端统一用 type=cancelled/paused/retrying/resumed 直接表示

      // 【北京老陈 2026-07-12 小欧】直接处理 cancelled/paused/resumed/retrying 类型
      case 'cancelled':
      case 'paused':
      case 'resumed':
      case 'retrying': {
        const stepNum = Number(rawData.step) || 1; // 2026-08-27 小欧 修复base-3: 加Number()
        console.log(
          `%c[STEP] [type=${rawData.type}] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );
        // 小欧 2026-07-13: 后端 MetaStep 统一以 content 字段承载文本(与 ThoughtStep/FinalStep 契约一致),
        // 前端须读 content 而非旧 message 字段, 否则用户取消/重试提示显示为空(真实跨层缺陷, 已修)。
        const statusMessage = rawData.content || '';

        // 直接使用rawData.type作为step.type
        step.type = rawData.type as ExecutionStep['type'];
        step.content = statusMessage;

        // 统一调用onStep（所有类型都需要添加到executionSteps）
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);

        // 根据type调用对应的回调
        switch (rawData.type) {
          case 'cancelled':
            onComplete?.(
              responseBufferRef.current,
              undefined,
              handlers.executionStepsRef.current
            );
            setIsReceiving(false);
            setIsConnected(false);
            break;
          case 'paused':
            onPaused?.();
            if (rawData.confirm_id) {
              // 【北京老陈 2026-07-13 小欧】HITL 授权请求：paused + confirm_id 触发授权弹窗
              handlers.onAuthorizationRequired?.({
                confirm_id: rawData.confirm_id,
                tool_name: rawData.tool_name,
                params: rawData.params,
                safety_level: rawData.safety_level,
              });
            }
            break;
          case 'resumed':
            onResumed?.();
            break;
          case 'retrying':
            // 小欧 2026-07-13: 同上, 读取后端 content 字段作为重试提示文本。
            onRetry?.(rawData.content || '正在重试...', rawData.wait_time);
            break;
          default:
            console.warn('[SSE] 未知的type:', rawData.type);
            onRetry?.(
              rawData.content || `事件: ${rawData.type}`,
              rawData.wait_time
            );
            break;
        }
        // 2026-08-27 小欧 修复base-1: 用已转换number timestampValue, 避免string覆盖
        step.timestamp = timestampValue;
        // 添加wait_time字段（仅retrying使用）
        if (rawData.wait_time !== undefined) {
          step.wait_time = rawData.wait_time;
        }
        break;
      }
    }
  } catch (error) {
    console.error('[SSE] 解析数据失败:', error);
  }
};

export { processSSEData };
