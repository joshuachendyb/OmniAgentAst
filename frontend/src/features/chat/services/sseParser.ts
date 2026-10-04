// 编辑历史: 2026-08-30 小欧 - 13.14 usage帧废止前端累加、直取后端本轮+三累计(P/C/T)四字段 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5(北京老陈定案, 后端设计定案): paused帧 onAuthorizationRequired 透传四字段——
//   trust_path(仅bypass时=rawData.trust_path, trust_panel的双写/撤回核心)、auto_confirm、confirm_timeout(前端倒计时=后端窗口-提前量)、backend_timeout - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 Bug修复(24项): ㉒/㉗镜像 assignTimeout(合法0保留) + auto_confirm严格判断(防"false"误判), 与 useAuthorization 语义一致 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 D2-10: normalizeAutoConfirm四态归一(true/'true'/1/'1')，与normalizeIsReasoning同策略，防bypass误判 - 小欧-2026-09-03
// 编辑历史: 2026-09-06 小欧 - B2方案C(北京老陈裁定): 拒绝独立 type="user_rejected" 单独发(不占 error 通道/liveErrorText),
//   新增独立回调 onDenied(step,message) 供 useChatStreaming 聚合 deniedStepSet 停齿轮 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - 方案C观察点1/2根治: action 解析 preview 标记(后端 preview=True, 仅SSE齿轮先行预览行),
//   刷新恢复时剔除, 与 DB 回放语义一致 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定 被拒工具 UI 灰字痕迹): ①onDenied 回调两参→三参
//   (step,message,toolName)——user_rejected 事件透传 rawData.tool_name 供聚合被拒工具点名条; ②error blocked/timeout
//   构造对象补 tool_name(rawData.tool_name, 后端 6.2 事件已带被拒工具名)——两路同源承灰字链路 — 小欧-2026-09-06
// 编辑历史: 2026-09-18 小欧 - 实施: paused帧透传新增 content 字段(后端 ConfirmSpec.content 弹窗原因) — 小欧-2026-09-18
// 编辑历史: 2026-09-07 小欧 - 4.4.1取消终态: 删外层 case 'cancelled' 与内层 switch 分支, 取消收尾单一由
//   type=final+outcome=cancelled 承担(paused/resumed/retrying 保留); incident 废弃注释同步移出 cancelled — 小欧-2026-09-07
// 编辑历史: 2026-09-07 小欧 - 4.4.3 start/startinfo 双信号拆分(前端消息分类处理分析及设计-小欧-2026-09-06.md):
//   startinfo 合并入 start——后端 start 现已自带 ai_message_id, 删除 case 'startinfo' 分支;
//   case 'start' 合并写入 contextSummary + startTimestamp + startInfo(含 ai_message_id),
//   徽标(running/idle)/过程条首行/计时/概况支付行为全不变(startInfo 到达提前到 start, 徽章 running 只更早亮) — 小欧-2026-09-07
// 编辑历史: 2026-09-08 小欧 - 六章6.3.1/6.3.4(北京老陈裁定回归总原则): error case onError 构造对象无条件打
//   from_backend=true(来源判据, 不做类型匹配) + request_level=rawData.step===0(层级判据, 读原始值禁stepNum归一;
//   请求级step=0为真, 执行级step≥1/缺失为false) — useChatCallbacks 据此分道只进第三类; step/tool_name 仍照传(聚合源不变) — 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 回归修复(全量回归红): case 'start' 的 contextSummary 承接对象 content——
//   后端 StartStep.get_content() 返回 context_summary 对象(非字符串), 原 typeof==='string' 三元把对象丢弃为 '',
//   任务信息条上下文概况(tooltip)空白(数据退化)。改: 对象 JSON 序列化承接, null/undefined 仍为空 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「该清理的清理、与后端消息不匹配的必须一致」):
//   case 'action' 删 6 条耗时打点(执行Steps保存开始/完成、sessionStorage保存开始/完成、渲染开始/完成)与 9 个计时变量
//   (execStepsStartTime/execStepsDoneTime/execStepsDuration、storageStartTime/storageDoneTime/storageDuration、
//   renderStartTime/renderDoneTime/renderDuration)——sseParser 性能打点与 sse_parser 职责无关且高噪(D.R.Y);
//   final 分支「[连接断开]」误导文案改为「[收到final终态]」——该处实为收到 final 终态事件, 非连接异常收尾 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - thought-start/action/observation 到达打点精确化(北京老陈指示「准确记录到达时间、单步并行准确log」):
//   ①thought-start 补到达打点(原无 log) [type=thought-start][step][开始思考]+秒级到达时间;
//   ②action 打点补 exec_type 直标 single/multi(单步橙标·并行 orange 多×N) + 工具点名(与 step.content 同源 join('+')),
//     到达时间=receiveTime(收到帧即时截取, 原用解析后时间不精确);
//   ③observation 打点移出解析前占位(原在解析前打无工具名/状态), 移到解析完成后直打 [工具名][状态=exec_code][结果×N] + 收到帧时刻 receiveTime,
//     并行观察由 tool_result 数组长度反映(>1=并行动作多次观察); 均秒级 toLocaleTimeString — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - action 双发事件独立点名(北京老陈指示「每次 action 都记, 分别记为 action_preview/action_canonical」):
//   后端 handle_action 同一步 preview(齿轮先行 tools=all_calls _live_only) 与 canonical(真实执行集 _exec_calls) 双发,
//   打点 type 字段据 step.preview 前缀化 [type=action_preview]/[type=action_canonical], observation 不参与(单次到达) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 时序统一核查(北京老陈指示「核查时序准确性, log标签简洁明了准确」):
//   ①新增 frameTime=本条SSE帧到达时刻(processSSEData 逐行调用即帧到达), 各分支日志统一引用,
//     消除原分支内 Date.now()/接收时间 各自截取的毫秒级不一致(同帧各日志时间必然一致);
//   ②thought-start/thought/action/observation/error/final/user_rejected/paused/resumed/retrying 全部换用 frameTime;
//   ③删 action/observation 分支内私有 receiveTime(回归 frameTime 单一真源) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 失败终态透传修复(北京老陈「UI冻住/日志不完整」排查实证): final 分支补解析
//   outcome/error_type/error_message —— 后端 FinalStep(2026-07-18 规整) 已稳定下发, 前端漏解析导致
//   useChatCallbacks.onComplete 无法识别失败终态, 4333字思考草稿(5轮流式chunk累积)被当"完整回复"正常展示 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - saveStepsToStorage防抖配套: thought/chunk/final/action/observation/paused六处去掉外层
//   setTimeout(() => { saveStepsToStorage?.(newSteps); }, 0), 改为直接调用(防抖已在useSSE内部处理),
//   消除N个事件→N个宏任务排队→O(N²)主线程阻塞 — 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: processSSEData签名删除未使用形参_isProcessingRef — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - S12批量commit: thought-start/thought/chunk/action/observation/paused/resumed六处改push+scheduleFlush,
//   零同步序列化消除O(N²)主线程阻塞; final分支同步flush防组件卸载前丢尾; handlers新增pendingStepsRef/scheduleFlush — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - S15并发HITL: onPaused/onResumed加可选confirmId参数(并发HITL区分), paused/resumed分支透传rawData.confirm_id — 小欧-2026-09-10
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计文档[76] 6.14): 加merged分支+onMerged回调 — 小欧-2026-09-28
// 编辑历史: 2026-09-10 小欧 - S3 seq守卫: handlers新增lastSeqRef, 入口层拦截重复事件(seq<=lastSeqRef.current即跳过), 防断连重连重复帧 — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段三S12.2残留死参清理(v2.17): handlers删saveStepsToStorage字段(:78)+解构(:133,
//   与useSSE两处传参同步删), 该参已无调用点(S12改用pendingStepsRef+scheduleFlush, 落库收敛于flushPendingSteps) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段三final分支ref权威源修复(v2.17, 与useSSE flushPendingSteps同款):
//   原实现函数式updater(prev=>[...prev,...batch])且updater内含写ref副作用, 违反T11更新器零副作用(StrictMode双执行双写ref);
//   且原ref先行只补当前step、漏早前未flush的pending, onComplete读ref缺失早前步骤。
//   改非函数式set: batch全量+ref权威源展开, ref同步赋值后再setState, StrictMode幂等 — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - [C1/C2]终态后作废守卫(北京老陈排查35失败): handlers新增可选中terminalSeqRef,
//   final/error分支记录终态seq, 入口层拦截终态后到达的更高seq晚到帧(防pendingSteps被污染);
//   start/final_stats/usage元信息帧放行(终态统计仍需落) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - TS类型修复: final/error分支 terminalSeqRef.current 赋值由 step.step 改
//   stepNum——step.step 类型为 number|undefined, stepNum 经 Number(rawData.step)||1 保证 number,
//   消除类型安全隐患, 终态 seq 记录值语义不变 — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 契约化(method2, 北京老陈 2026-09-11 定案): thought=仅历史回显事件(DB executionSteps),
//   实时 SSE 永不发(后端 stream_reader 经 _SSE_EXCLUDE_TYPES 过滤)。case 'thought' 改为纯防御分支——
//   原实时收集 thought 入 executionSteps 为历史错逻辑(实时+DB 双通道重复根因), 现收到即丢弃仅打日志 — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复(归一化/数值化两项): normalizeIsReasoning/normalizeAutoConfirm同名同体合并为
//   normalizeBoolean(DRY); Number(rawData.step)||1 十处重复抽 toStepNumber helper(DRY, SLAP) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复(error分支归一化/终态补字段): ①error分支step.step改toStepNumber归一化(原直接赋string致终态seq守卫string/number比较失效);
//   ②action分支补赋tool_name(单工具=tools[0].tool, 多工具=join(' + ')), 原从未赋值致调试日志恒undefined — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复(usage帧taskLike单源): usage帧taskLike不再round fallback(taskAcc空时→{0,0,0}), usage字段写入删除(→types/sse.ts 同源) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复(action分支删死字段): action分支删step.code赋值(死字段, 原rawData.code无人消费; execution_status含同语义) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 问题1实施(北京老陈批准, 作废守卫退役): 删终态后作废守卫全部残留——
//   接口定义/解构/入口拦截块/ final·error分支终态seq记录 五处删除(第二套度量衡退役, event_log seq全局连续单调+TCP有序
//   +final后无业务帧 ⇒ 晚到高seq帧物理不存在, 守卫零拦截量, YAGNI纯删除)。useSSE侧S904 B2空流判定改用lastSeqRef
//   (见useSSE.ts编辑历史, done权威置位在后final先publish, 判定语义等价)。编辑历史注释保留可追溯 — 小欧-2026-09-12
// 编辑历史: 2026-09-13 小欧 - TDD(行154/311-315): lastUsageSeqRef 第二基线退役——①handlers 接口删除
//   lastUsageSeqRef 字段声明(仅保留 lastSeqRef 唯一条基线); ②usage 分支内 seq<=lastUsageSeqRef.current 守卫块整块删除
//   (入口 lastSeqRef 层已拦截全部重复帧, 该守卫拦截量 0, F2 与入口重复; 单基线纪律 3.2, YAGNI) — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 重连链路追踪补点(北京老陈指令): 入口 seq 守卫拦截 console.debug→console.warn——
//   重发正是本专项核心, 若未来引入物理重复帧(seq<=lastSeq)必须醒目可见(debug 级易被忽略且不落盘), 升 warn 保追踪 — 小欧-2026-09-13
// 编辑历史: 2026-09-17 小欧 - 统一拒绝事件 type="rejected": ①新增 onRejected 回调接口; ②新增 case 'rejected' 分支, 调用 onRejected + 兼容调用 onDenied; ③onRejected 接收 {step,message,tool_name,reject_type,from_backend} - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 - 实施: ①handlers 新增 onHeartbeat/onBiz 回调; ②入口识别 `: ping` 上报心跳(原被前缀判断静默丢弃); ③业务帧在 seq 守卫后上报 onBiz 刷新业务静默基线(校核: 过期帧不得掩盖真实静默) - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 会审V3更正: 上一版历史"②调用 onRejected + 兼容调用 onDenied"停用——onDenied 回调整链
//   同日会审V3已删除(YAGNI, 唯一调用方 useChatStreaming 曾传 undefined, 零消费者), 现仅 onRejected 单链(见 :135-137) - 小欧-2026-09-17
// 编辑历史: 2026-09-19 小欧: 心跳:ping 除调用 onHeartbeat 外, 新增创建 ExecutionStep({type:'heartbeat'}) 并 pushAndFlush 记录到事件列表 — 北京老陈驱动
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.15 HITL 单源化: 删 resumed 帧带 confirm_id 时的
//   window.dispatchEvent('authorization_resumed') 兜底派发(原 :180-186 小沈 2026-09-03 加的防御兜底)。
//   S1 超时放行现走 5.3 onResumed(emitEvent + 清 Store.pendingAuthorization) → useAuthorization
//   快照 effect 关弹窗(5.15 上块); window 派发端双删之一(另一处 useChatCallbacks
//   onAuthorizationRequired), 防双源复活 — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 14:30 小欧 - 解析/业务分层兜底；未知 type 不推进 seq 保留 onBiz；final 提前收尾；删零消费成员
// 编辑历史: 2026-10-04 小欧 - context_overview 摘要键修正 summary→content(帧的权威文本字段是 content,
//   从无 summary 键, 原读法致卡片恒显"–")＋补收 injected 两键 — 小欧 2026-10-04
// 编辑历史: 2026-10-04 小欧 - usage 帧新增解析 context_window → metaFrames.contextWindow(运行时上下文窗口),
//   供 taskinfo「占窗率 = 本轮P/窗口」; 窗口为常量, 无新值时沿用上一帧(prev.contextWindow)
import type { ExecutionStep } from '@/types/execution';
import type { SSEMetadata, SSEError, TaskMetaFrames } from '@/types/sse';
import { formatDebugTime } from '@/utils/time'; // 2026-09-14 小欧 DRY: 时间戳格式化复用 — 小欧-2026-09-14

// 2026-09-12 小欧 修复: normalizeIsReasoning/normalizeAutoConfirm同名同体, 合并为单一 normalizeBoolean(DRY) — 小欧-2026-09-12
const normalizeBoolean = (v: unknown): boolean =>
  v === true || v === 'true' || v === 1 || v === '1';

// 2026-09-12 小欧 修复: step 数值化 helper, 消原始十处 Number(rawData.step)||1 重复(DRY) — 小欧-2026-09-12
const toStepNumber = (v: unknown): number => Number(v) || 1;

// 2026-09-03 小欧 修复: 计时解析(与 useAuthorization.parseTimeout 同语义), 合法 0 保留, 仅 NaN/负数兜 60
const assignTimeout = (v: unknown): number => {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : 60;
};

// 2026-09-14 小欧 DRY: push+flush 模式提取, 消6处重复 — 小欧-2026-09-14
const pushAndFlush = (
  handlers: {
    pendingStepsRef?: React.MutableRefObject<ExecutionStep[]>;
    scheduleFlush?: () => void;
  },
  step: ExecutionStep
) => {
  handlers.pendingStepsRef?.current.push(step);
  handlers.scheduleFlush?.();
};

// 2026-09-14 小欧 debug: 各 SSE type 到达打点, 格式: [HH:MM:SS.mmm] 轮次=X type — 小欧-2026-09-14
/**
 * 2026-09-30 小欧 - 2-4：已消费事件类型白名单（**须与下方 processSSEData 内 switch 的
 *   case 标签保持一致**；新增 case 时必须同步登记，否则该帧会被前置拦截丢弃）。
 *
 * 病根：switch 原**无 `default` 分支**，而 `onSeq`（推进 lastSeq）与 `onBiz`（刷新业务静默基线）
 *   都发生在 switch **之前** —— 于是后端新增一个未同步的 type 时，三重静默失效：
 *   ① 帧被静默丢弃（无 default、无日志）；② seq 已推进 → 该帧**永不可能**在重连时按
 *   `after_seq` 补发 → **数据永久丢失**；③ 业务基线被刷新 → 一条"卡死"的后端流仅靠发未知 type
 *   就能永久骗过静默检测（不触发 60s 空闲恢复，用户界面永转）。
 *
 * 修法（在 switch **之前**前置判定，而非把 onSeq/onBiz 抄进每个 case —— 那会产生 18 处重复、
 * 违反 DRY）：未知 type → 打 warn + **直接 return**，"不推进 seq + 不刷基线 + 不消费帧"一次做到。
 */
const KNOWN_EVENT_TYPES: ReadonlySet<string> = new Set([
  'start',
  'thought-start',
  'usage',
  'stats',
  'final_stats',
  'history_context', // 2026-10-04 小欧: 原 context_overview, 改名(与后端 MetaStep.type 同步)
  'truncated',
  'thought',
  'chunk',
  'final',
  'error',
  'rejected',
  'action',
  'observation',
  'paused',
  'resumed',
  'retrying',
  'merged',
]);

const logTypeArrival = (type: string, round?: number) => {
  console.log(`${formatDebugTime()} 轮次=${round ?? '?'} ${type}`);
};

const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    getCurrentExecutionSteps: () => ExecutionStep[];
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>; // 【小新添加 2026-03-15】用于同步更新 ref
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, is_reasoning?: boolean) => void;
    onComplete?: (
      fullResponse: string,
      metadata?: string | SSEMetadata,
      executionSteps?: ExecutionStep[]
    ) => void;
    onError?: (error: string | SSEError) => void;
    // 2026-09-16 小欧: 统一拒绝事件 type="rejected" — 替代旧 error(blocked/timeout) + user_rejected;
    // 2026-09-17 小欧 会审V3: onDenied 回调整链删除(YAGNI, 唯一调用方 useChatStreaming 已传 undefined, 零消费者);
    //   from_backend 硬编码字段删除(YAGNI, 全链透传零消费) — 小欧-2026-09-17
    onRejected?: (data: {
      step: number;
      message: string;
      tool_name?: string;
      reject_type: string;
    }) => void;
    // 小欧 2026-09-10 S15: onPaused/onResumed 加 confirmId 参数（并发 HITL 区分）
    onPaused?: (confirmId?: string) => void;
    onResumed?: (confirmId?: string) => void;
    // 2026-09-28 小欧: 注入应答回调(merged_into_task_id 供前端高亮目标任务)
    onMerged?: (mergedIntoTaskId: string | null) => void;
    onRetry?: (message: string, waitTime?: number) => void;
    onAuthorizationRequired?: (data: {
      confirm_id: string;
      tool_name: string;
      params: Record<string, unknown>;
      content?: string;
      safety_level: string;
      trust_path?: string | null;
      auto_confirm?: boolean;
      confirm_timeout?: number;
      backend_timeout?: number;
    }) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    // 2026-09-30 小欧 - 删 setIsReceiving/setIsConnected：收尾两字段归 transport 的
    //   markDisconnected 单一入口，本文件 final/error 两处旧写入随之删除（同批还删 disconnect）
    setServerTaskId?: (taskId: string) => void;
    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，用于断线重连 after_seq 续传
    onSeq?: (seq: number) => void;
    // 小欧 2026-09-10 S3: seq 守卫 ref，sseParser 入口层拦截重复事件（seq <= lastSeqRef.current 即跳过）
    lastSeqRef?: React.MutableRefObject<number>;
    // 编辑历史: 2026-09-12 16:28 小欧 - 问题1: 原 terminalSeqRef 接口定义已删除(作废守卫退役,
    //   event_log seq 全局连续单调+TCP有序+final后无业务帧 ⇒ 晚到高seq帧物理不存在, YAGNI) — 小欧-2026-09-12
    // 小欧 2026-09-10 S12: 批量 commit — 传入 pendingStepsRef + scheduleFlush
    pendingStepsRef?: React.MutableRefObject<ExecutionStep[]>;
    scheduleFlush?: () => void;
    // 【小欧 2026-08-26 8.4.14】元信息帧状态注入（useSSE 闭包 state/ref 透传进模块级 processSSEData）
    setMetaFrames?: React.Dispatch<React.SetStateAction<TaskMetaFrames>>;
    usageAccumRef?: React.MutableRefObject<{
      prompt: number;
      completion: number;
      total: number;
    }>;
    // 2026-09-17 小欧 实施: 心跳/业务到达信号(钟面数据源) — 小欧-2026-09-17
    onHeartbeat?: () => void; // 收到后端 `: ping` 保活注释行
    onBiz?: () => void; // 收到任一业务 data 帧(含 chunk)
  }
) => {
  const {
    setExecutionSteps,
    onStep,
    onChunk,
    onComplete,
    onError,
    onRejected,
    onPaused,
    onResumed,
    onRetry,
    setCurrentResponse,
    responseBufferRef,
    // 2026-09-30 小欧 - setIsReceiving/setIsConnected 成员与解构一并退役：收尾归位 transport
    //   的 markDisconnected（见上方 handlers 类型注释）
    // 2026-09-30 小欧 - 原 `disconnect: _disconnect` 解构已删（成员与解构同时退役，见上方 handlers 类型注释）。
    setServerTaskId,
    onSeq,
    // 编辑历史: 2026-09-12 16:28 小欧 - 问题1: 原 terminalSeqRef 解构已删除(作废守卫退役) — 小欧-2026-09-12
  } = handlers;

  // 2026-08-27 小欧 修复: SSE数据行可能带前导空格, 先trim再判断前缀
  const trimmedLine = line.trim();
  // 2026-09-17 小欧 实施: 后端 `: ping`(stream_orchestrator.py:515, 周期 constants.HEARTBEAT_INTERVAL=25s)
  //   原被下行前缀判断静默丢弃(前端无任何 UI 可感知通路); 现上报心跳信号供钟面盘外圈微闪(存活确认, 不参与计时) — 小欧-2026-09-17
  if (trimmedLine === ': ping') {
    // 2026-09-30 小欧 - 心跳分支纳入业务兜底：它原在两个 try 之外，onHeartbeat/onStep/
    //   pushAndFlush 任一抛错都会冒泡进 pump 的逐行循环 → 单个组件 render 抛错升级为断流，
    //   与"消费方抛错不中断整条流"的口径不一致。
    try {
      handlers.onHeartbeat?.();
      // 2026-09-19 小欧: 心跳记录到事件列表 — 北京老陈驱动
      const hbStep: ExecutionStep = {
        type: 'heartbeat',
        timestamp: Date.now(),
      };
      pushAndFlush(handlers, hbStep);
      onStep?.(hbStep);
    } catch (error) {
      console.error('[SSE] 心跳处理失败（已跳过本次心跳，流继续）:', error);
    }
    return;
  }
  if (!trimmedLine || !trimmedLine.startsWith('data: ')) {
    return;
  }

  // 2026-09-30 小欧 - 2-2：解析与业务**分层兜底**。
  //   病根：原 try 从此处一直包到 switch 末尾（覆盖"解析 + 全部业务分支 + 全部消费方回调"），
  //   而 catch 只报 '[SSE] 解析数据失败' —— 于是**消费方回调抛错被误报成解析失败并吞掉**：
  //   以 final 分支为例，`onComplete?.()` 链中任一订阅者抛错 → 其后的
  //   `setIsReceiving(false)` 不执行 → 异常被吞 → 表现为"final 已消费、步骤已落，
  //   但既无 complete 事件、isReceiving 残留 true"，即**状态机被撕开**且对用户不可见。
  //   修法（三点，缺一不可）：
  //   ① 解析 try 收窄到**仅 JSON.parse** —— 解析失败本可容忍（丢该帧），语义与日志名相符；
  //   ② 业务 switch 独立 try-catch 兜底 —— 消费方抛错**不中断整条流**
  //      （若让异常冒泡到 pump 的逐行循环，一个组件 render 抛错会从"丢一帧"升级为"断流"，
  //        属功能退化，AGENTS 严禁），仅记录并继续；
  //   ③ final 分支调整顺序：**先做状态收尾（isReceiving/isConnected）再通知外部 onComplete**，
  //      使外部回调抛错也无法跳过收尾——这才是"状态机不被撕开"的真正保证。
  // 注：rawData 保持 any（与原 JSON.parse 返回值一致）——本条只改 try 的**范围**，
  //   不改既有类型语义（收窄为 Record<string, unknown> 会牵连 switch 内数十处字段赋值，
  //   属"重写"而非"修缺陷"，违 AGENTS 1.4 能复制就复制不重写）。
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let rawData: any;
  try {
    const jsonStr = trimmedLine.slice(6).trim();
    rawData = JSON.parse(jsonStr);
  } catch (error) {
    console.error('[SSE] 解析数据失败:', error);
    return;
  }

  try {
    // 2026-09-09 小欧 时序统一: frameTime=本条SSE帧到达时刻(processSSEData被逐行调用即帧到达),
    //   thought-start/thought/action/observation 等日志统一引用, 同帧内时间一致且准确 — 小欧-2026-09-09
    const frameTime = Date.now();

    // 小欧 2026-09-10 S3: seq 权威守卫 — 已处理最大 seq 语义(初始-1)
    // 守卫在 onSeq 之前、switch 之前：先拦截重复，再推进，再放行
    if (typeof rawData.seq === 'number' && handlers.lastSeqRef) {
      if (rawData.seq <= handlers.lastSeqRef.current) {
        console.warn(
          `[SSE] seq守卫拦截: seq=${rawData.seq} <= lastSeq=${handlers.lastSeqRef.current}`
        );
        return;
      }
    }

    // 编辑历史: 2026-09-12 16:28 小欧 - 问题1: 原「终态后作废守卫」拦截块已删除(作废守卫退役,
    //   本文件编辑历史板块 2026-09-12 条目同步) — 小欧-2026-09-12
    // 2026-09-30 小欧 - 未知 type 分档：seq 不推进（该帧未消费，推进则 after_seq 越过它、
    //   重连永无补发机会=真丢数据），但 onBiz 仍调（任何 data 帧到达即后端仍活跃产出）
    const isKnownEventType = KNOWN_EVENT_TYPES.has(rawData.type as string);
    if (!isKnownEventType) {
      console.warn(
        `[SSE] 未知 type="${String(rawData.type)}"（seq=${rawData.seq ?? '-'}）：` +
          '该帧内容未消费且未推进 seq（重连可按 after_seq 补发）；' +
          '若后端确为新增事件类型，请在 KNOWN_EVENT_TYPES 补登记'
      );
    }

    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，断线重连时用于 after_seq 续传避免重复
    // 2026-09-30 小欧 - 仅已知 type 才推进 seq（未知 type 见上方分档说明）
    if (isKnownEventType && typeof rawData.seq === 'number' && onSeq) {
      onSeq(rawData.seq);
    }

    // 小欧 2026-09-29: [63] P3 Journal 降级标记读取（后端 event payload 的 persistence_degraded）。
    //   该帧 Journal 写入失败，故降级事实由后续帧粘滞携带；此处仅 console 观测（UI 提示通路待接，
    //   不预埋无调用方的回调钩子——YAGNI）。
    if (
      (rawData as { persistence_degraded?: boolean }).persistence_degraded ===
      true
    ) {
      console.warn(
        `[SSE] 事件持久化已降级(seq=${rawData.seq ?? '-'}): 本任务部分过程刷新/重连后不可完整回放`
      );
    }

    // 2026-09-17 小欧 实施: 业务帧到达(=后端仍在活跃产出) → 刷新业务时间基线;
    //   长输出期间 chunk 不断, 保证不被误判"业务静默"而升档(与心跳/断连语义正交);
    //   按 6.6#1 校核置于 seq 守卫之后, 仅通过守卫的真正新帧才刷新基线(过期帧不得掩盖真实静默) — 小欧-2026-09-17
    handlers.onBiz?.();

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
      step: toStepNumber(rawData.step), // 2026-08-27 小欧 修复: 加Number()数值化; 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
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
      is_reasoning: normalizeBoolean(rawData.is_reasoning), // 2026-09-12 修复: 统用normalizeBoolean(原normalizeIsReasoning) — 小欧-2026-09-12
      // reasoning: rawData.reasoning || "",  // 【小强删除 2026-04-08】reasoning与content重复，后端已删除

      timestamp: timestampValue,
    };

    if (rawData.task_id && setServerTaskId) {
      setServerTaskId(rawData.task_id);
    }

    switch (rawData.type) {
      // 【小欧 2026-08-26 8.4.3】start/startinfo 拆双（4.9.2.7）；
      // 2026-09-07 小欧 4.4.3: startinfo 合并入 start——start 自带 ai_message_id,
      //  - start.content=context_summary -> 元信息帧 contextSummary（任务信息条上下文概况，三分归位③）+
      //    元信息帧 startInfo（驱动状态徽标），同样不入步骤列表；
      //    不进右侧查看区流水线（4.4.4）；user_message 对话界面已可见不重复渲染（4.9.1）；
      //    model/provider 由顶栏徽标承载（4.8.3-A）。
      case 'start': {
        // 2026-09-08 小欧 修复: 后端 StartStep.get_content() 返回 context_summary 对象(非字符串),
        //   原 typeof==='string' 三元把对象丢弃为 '' → contextSummary 空白(任务信息条上下文概况退化)。
        //   改: 对象 JSON 序列化承接(tooltip 消费 string), null/undefined 仍空 — 小欧-2026-09-08
        const summary =
          typeof rawData.content === 'string'
            ? rawData.content
            : rawData.content != null
              ? JSON.stringify(rawData.content)
              : '';
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          contextSummary: summary,
          startTimestamp: Date.now(),
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
          step: toStepNumber(rawData.step), // 2026-08-27 小欧 修复: 加Number(); 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
          timestamp: timestampValue,
        };
        // 小欧 2026-09-10 S12: 批量 append，零同步序列化
        pushAndFlush(handlers, ts);
        onStep?.(ts);
        logTypeArrival('thought-start', ts.step); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        break;
      }

      // usage：单任务 token 帧 —— 后端直发本轮+三累计(P/C/T)，前端直存直显不另算【13.14】
      case 'usage': {
        logTypeArrival('usage'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        const round = {
          prompt: rawData.prompt_tokens ?? 0,
          completion: rawData.completion_tokens ?? 0,
          total: rawData.total_tokens ?? 0,
        };
        const taskAcc = rawData.task_accumulated_tokens ?? null;
        const sessAcc = rawData.session_accumulated_tokens ?? null;
        const chainAcc = rawData.chain_accumulated_tokens ?? null;
        // 2026-09-12 小欧 修复: taskLike 由 round fallback 改 taskAcc 空时硬 {0,0,0}(不再复用 round, taskAccumulated 单一真源) — 小欧-2026-09-12
        const taskLike = taskAcc
          ? {
              prompt: taskAcc.prompt_tokens ?? 0,
              completion: taskAcc.completion_tokens ?? 0,
              total: taskAcc.total_tokens ?? 0,
            }
          : { prompt: 0, completion: 0, total: 0 };
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          roundUsage: round,
          // 2026-10-04 小欧: 保留最后一帧窗口值(窗口为常量, 无新值时沿用), 供"本轮 P / 窗口"占用率
          contextWindow: rawData.context_window ?? prev.contextWindow ?? null,
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
        logTypeArrival('stats'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
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

      // final_stats：终态统计独立步（duration/tool_stats/artifacts/step_count/llm_call_count）
      // 小欧 2026-09-11 M5b(finalStats补解析): 补解析 step_count/llm_call_count（后端 3.4 FinalStatsStep 新增 7 键, 折叠区步数/轮次来源） — 小欧-2026-09-11
      case 'final_stats': {
        logTypeArrival('final_stats'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          finalStats: {
            duration: rawData.duration,
            tool_stats: rawData.tool_stats,
            artifacts: rawData.artifacts,
            final_status: rawData.final_status,
            retry_count: rawData.retry_count,
            step_count: rawData.step_count,
            llm_call_count: rawData.llm_call_count,
          },
        }));
        break;
      }

      // history_context：装入历史对话水位帧
      // 2026-10-04 小欧: 帧类型改名 context_overview→history_context(与后端 MetaStep.type 同步) — 小欧 2026-10-04
      case 'history_context': {
        logTypeArrival('history_context'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          contextOverview: {
            summary: typeof rawData.content === 'string' ? rawData.content : '',
            message_count: rawData.message_count,
            estimated_tokens: rawData.estimated_tokens,
            truncated: rawData.truncated === true,
            injected_ratio: rawData.injected_ratio,
            injected_message_count: rawData.injected_message_count ?? null,
            injected_estimated_tokens:
              rawData.injected_estimated_tokens ?? null,
          },
        }));
        break;
      }

      // truncated：输出截断提示帧（severity=warn，字段=content）
      case 'truncated': {
        logTypeArrival('truncated'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
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
        // 2026-09-11 小欧 契约化(method2, 北京老陈 2026-09-11 定案): thought = 仅历史回显事件
        //   (DB executionSteps), 实时 SSE 永不发(后端 stream_reader 经 _SSE_EXCLUDE_TYPES 过滤)。
        //   纠正的历史错逻辑: 实时收到 thought 即收集入 executionSteps → 与 DB 回放 thought
        //   双通道重复(前端重复显示根因), 且 S12 批量 append 令思考草稿与正文并存。
        //   现改为纯防御分支: 后端异常误发时打日志并丢弃, 绝不污染实时 executionSteps — 小欧-2026-09-11
        const stepNum = toStepNumber(rawData.step); // 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
        console.warn(
          `%c[契约] [type=thought] 实时SSE不应出现 thought(仅历史回显), 已防御丢弃 step=${stepNum} 时间=${new Date(
            frameTime
          ).toLocaleTimeString()}`,
          'color: orange; font-weight: bold;'
        );
        break;
      }

      case 'chunk': {
        // 精简日志：chunk不打印，避免日志过多

        // 传递 is_reasoning 区分思考过程和最终答案
        const is_reasoning = normalizeBoolean(rawData.is_reasoning); // 2026-08-27 小欧 修复: 复用统一helper; 2026-09-12 修复: 统用normalizeBoolean — 小欧-2026-09-12
        const chunkContent = rawData.content || '';
        console.log(
          `${formatDebugTime()} ${is_reasoning ? 'T' : 'F'} =${chunkContent}`
        ); // 2026-09-14 小欧 cursor打点输出chunk独立片段 — 小欧-2026-09-14
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

        // 小欧 202G-09-10 S12: 批量 append，零同步序列化
        pushAndFlush(handlers, step);
        onStep?.(step);
        break;
      }

      case 'final': {
        logTypeArrival('final', step.step); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        // 2026-08-27 小欧 修复: 加Number(); 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12

        // 【小沈修改2026-04-16】添加step和timestamp字段
        step.step = toStepNumber(rawData.step); // 2026-08-27 小欧 修复: 加Number()数值化; 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
        step.timestamp = timestampValue; // 2026-08-27 小欧 修复base-1: 用已转换number

        // 【小强修复 2026-04-15】后端final类型没有content字段，直接使用response
        // 解析后端所有字段
        step.response = rawData.response || '';
        step.is_finished = rawData.is_finished;
        step.thought = rawData.thought || '';
        step.is_streaming = rawData.is_streaming;
        step.is_reasoning = normalizeBoolean(rawData.is_reasoning); // 2026-08-27 小欧 修复: 归一化避免存字符串; 2026-09-12 修复: 统用normalizeBoolean — 小欧-2026-09-12
        step.content = step.response; // content只用于前端显示，使用response的值
        // 2026-09-09 小欧 失败终态透传: 后端 FinalStep 已下发 outcome/error_type/error_message,
        //   前端原漏解析致 onComplete 无法识别失败终态(4333字思考草稿被当完整回复) — 小欧-2026-09-09
        step.outcome = rawData.outcome;
        step.error_type = rawData.error_type;
        step.error_message = rawData.error_message;
        // 2026-09-11 小欧 北京老陈定案: cancelled终态渲染第二行✕取消来源, final分支补解析(后端FinalStep.to_dict恒输出cancel_source) — 小欧-2026-09-11
        step.cancel_source = rawData.cancel_source;
        // 小欧 2026-09-11 M4(title段duration解析): final 分支补 duration 解析——title 段运行时长唯一实时源
        //   (后端 3.1 FinalStep._extra_fields 新增, 与 DB update_task duration 同源算式: now-_run_start_ts)
        //   不读 DB; ExecutionStep.duration 字段已存在(类型 L155: number?) — 小欧-2026-09-11
        step.duration = rawData.duration;

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

        // 小欧 2026-09-10 S12.2.1: final 分支同步 flush，防组件卸载前丢尾
        handlers.pendingStepsRef?.current.push(step);
        // v2.17 修复(小欧 2026-09-10): 与 useSSE flushPendingSteps 同款 ref 权威源等价值计算——
        //   原实现用函数式 updater（setExecutionSteps(prev => [...prev, ...batch])）且 updater 内含写 ref 副作用
        //   （T11 要求 updater 零副作用, StrictMode 下 updater 双执行即双写 ref）; 且原 ref 先行只补 step
        //   而 batch 含早前未 flush 的 pending, 此时 onComplete 读 ref 缺失早前步骤。改非函数式 set:
        //   batch 全量 + ref 权威源展开, ref 同步赋值后再 setState, StrictMode 幂等, updater 彻底消失
        const batch = handlers.pendingStepsRef?.current.splice(0) ?? [step];
        const newSteps = [...handlers.executionStepsRef.current, ...batch];
        handlers.executionStepsRef.current = newSteps;
        setExecutionSteps(newSteps);
        onStep?.(step);

        const finalStepsWithCurrent = handlers.executionStepsRef.current;

        // 2026-09-30 小欧 - 删此处 setIsReceiving/setIsConnected(false)：收尾归位 transport
        //   onComplete 的 markDisconnected（在 emitEvent 之前，故回调抛错也跳过不了收尾）
        onComplete?.(
          responseBufferRef.current,
          {
            model: rawData.model,
            provider: rawData.provider,
            display_name: displayName,
          } as SSEMetadata,
          finalStepsWithCurrent
        );
        // 编辑历史: 2026-09-12 16:28 小欧 - 问题1: 原「final 终态后作废」terminalSeqRef 赋值已删除(作废守卫退役) — 小欧-2026-09-12
        break;
      }

      case 'error': {
        const stepNum = toStepNumber(rawData.step); // 2026-08-27 小欧 修复: 加Number(); 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
        logTypeArrival('error', stepNum); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14

        // 【小强修复 2026-04-15】后端error类型只有以下字段，只解析后端存在的字段
        // 【小欧 2026-08-18 三堂会审】error 文本统一由 MetaStep.content 承载(新)，
        //   兼容读 content，再回退旧 ErrorStep 的 error_message，杜绝实时显示退化为'未知错误'
        const errorMsg = rawData.content || rawData.error_message || '未知错误';
        step.content = errorMsg;
        step.error_message = errorMsg;
        step.error_type = rawData.error_type || '';

        // 解析后端存在的字段
        // 2026-09-12 小欧 三堂会审修复: 原直接赋值rawData.step(string)致终态seq守卫string/number比较失效, 统一Number()归一化 — 小欧-2026-09-12
        if (rawData.step) {
          step.step = toStepNumber(rawData.step);
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
        // 文本读 content（已收敛），回退 error_message。
        // 【小沈修改2026-04-15】传递完整的错误对象，统一使用error_message，删除code字段
        onError?.({
          type: 'error',
          error_type: rawData.error_type || 'unknown_error',
          error_message: errorMsg,
          step: stepNum, // 2026-09-06 小欧 B2(方案C): 错误透传所属执行轮 step, 前端按 blocked/timeout 聚合 deniedStepSet — 小欧-2026-09-06
          tool_name: rawData.tool_name, // 2026-09-06 小欧 B2(6.4): 透传被拒工具名(blocked/timeout), 供被拒工具点名条 — 小欧-2026-09-06
          // 2026-09-08 小欧 落码: 后端 error 事件无条件打来源标 —— useChatCallbacks 据此分道只进第三类不弹窗 — 小欧-2026-09-08
          from_backend: true, // 判据=来源(事件由 SSE 解析而来)而非类型匹配
          // 2026-09-08 小欧 6.3.4: 层级标记读原始 rawData.step===0(禁 stepNum 归一, 恒≥1判不出请求级) — 小欧-2026-09-08
          request_level: rawData.step === 0,
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
        // 2026-09-30 小欧 - 删此处 setIsReceiving/setIsConnected(false)：终态收尾已由
        //   transport onError 的 markDisconnected 统一承担；非终态业务错误流仍在跑，误关即 Bug
        // 编辑历史: 2026-09-12 16:28 小欧 - 问题1: 原「error 终态后作废」terminalSeqRef 赋值已删除(作废守卫退役) — 小欧-2026-09-12
        break;
      }

      // 2026-09-06 小欧 B2(北京老陈裁定): 拒绝不是error事件, 后端独立 type="user_rejected" 单独发 —
      //   2026-09-17 小欧 会审V3: 该 case 已删除(后端 2026-09-16 起统一发 type="rejected", user_rejected 永不到达,
      //   禁止backward 残留死代码清理) — 小欧-2026-09-17

      // 2026-09-16 小欧: 统一拒绝事件 type="rejected" — 替代旧 error(blocked/timeout) + user_rejected
      //   统一回调 onRejected, 传递 reject_type 供下游区分具体拒绝原因(safety/sandbox/timeout/user)
      case 'rejected': {
        const rejectedStep = toStepNumber(rawData.step);
        logTypeArrival('rejected', rejectedStep);
        const rejectMsg =
          rawData.content || rawData.error_message || '执行被拒绝';
        const rejectType = rawData.reject_type || 'unknown';

        // 统一回调, 传递 reject_type 供下游区分具体拒绝原因
        onRejected?.({
          step: rejectedStep,
          message: rejectMsg,
          tool_name: rawData.tool_name,
          reject_type: rejectType,
        });
        break;
      }

      // 【小欧 2026-08-26 8.4】action 新结构：exec_type(single/multi) + tools 数组
      // 单工具也是一个元素不做特判（4.9.2.9）；禁止保留 旧动作类型名 兼容分支
      case 'action': {
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
        // 2026-09-12 小欧 三堂会审修复: 补赋值 tool_name(单工具=tools[0].tool, 多工具=join(' + ')), 与 step.content 同源 —
        //   原从未赋值致 debug 日志 [DBG-6] 恒打印 undefined; 下游 ToolCallLine 单工具场景读 tool_name 亦受益 — 小欧-2026-09-12
        step.tool_name =
          tools.length === 1
            ? tools[0].tool
            : tools.map((t) => t.tool).join(' + ');
        step.content = tools
          .map((t) => (t.target ? `${t.tool}(${t.target})` : t.tool))
          .join(' + ');
        // 【小欧 2026-09-06 方案C观察点1/2根治】preview 仅SSE预览行标记(后端 preview=True):
        //   刷新恢复时剔除, 与 DB 回放语义一致(拦截/拒绝 action 本就不落库) — 小欧-2026-09-06
        step.preview = rawData.preview === true;

        // 【小欧 2026-09-09 准确打点】每次 action 到达分别记录: preview/canonical 双发(list-back 时序),
        //   exec_type 直标 single/multi×N; 工具点名与 step.content 同源 join('+')
        const _multi = step.exec_type === 'multi';
        const _typeLabel = step.preview ? 'action_preview' : 'action_canonical';

        // 小欧 2026-09-10 S12: 批量 append，零同步序列化
        pushAndFlush(handlers, step);

        onStep?.(step);
        logTypeArrival('action', step.step); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14

        break;
      }

      // 【小沈修复 2026-04-11】新增：observation类型处理
      // 【小沈改造 2026-05-22】支持observation为JSON对象（设计方案）
      case 'observation': {
        const stepNum = toStepNumber(rawData.step); // 2026-08-27 小欧 修复: 加Number(); 2026-09-12 修复: 统用toStepNumber — 小欧-2026-09-12
        logTypeArrival('observation', stepNum); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        step.step = stepNum; // 2026-08-27 小欧 修复base-3: 加Number()数值化
        step.timestamp = timestampValue; // 2026-08-27 小欧 修复base-1: 用已转换number
        // 2026-09-12 小欧 修复: 删 step.code 赋值(死字段, 原 rawData.code 无人消费; execution_status 含同语义) — 小欧-2026-09-12

        // 【兼容层 2026-05-22 小资】支持两种格式，添加完整性验证
        // 先检查null（typeof null === 'object'是历史bug）
        // 2026-08-27 小欧 三堂会审: 适配后端08-18新契约 — observation步骤仅携带rawData.tool_result数组(顶层), 无observation字段
        if (Array.isArray(rawData.tool_result) && rawData.tool_result.length) {
          // 新契约: tool_result数组在rawData顶层, 每元素自包含{tool_name,llm_data,data_text,other_data}
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
        } else {
          // 2026-09-30 小欧 - 原先此处还有一层"兼容旧格式（observation 为对象）"分支（约 57 行），
          //   已删：后端 ObservationStep._extra_fields 只下发 tool_result，全仓无任何位置下发
          //   observation 字段（该字段在 SSE 里物理不可达），属禁止 backward 条款下的死代码。
          //   本 else 兜底**必须保留**：后端 `if self._tool_result:` 在结果为空时不下发该字段，
          //   前端会落到这里；删掉会使这类帧的 step 字段全空。
          // 兜底：无 tool_result 的观测帧（后端结果为空时不下发该字段）
          const obsStr =
            rawData.observation != null ? String(rawData.observation) : '';
          step.observation = obsStr;
          step.tool_name = rawData.tool_name ?? '';
          step.tool_params = rawData.tool_params ?? {};
          step.return_direct = rawData.return_direct ?? false;
          step.content = obsStr;
        }

        // 小欧 2026-09-10 S12: 批量 append，零同步序列化
        pushAndFlush(handlers, step);
        onStep?.(step);
        break;
      }

      // 【北京老陈 2026-07-12 小欧】直接处理 paused/resumed/retrying 类型
      // 2026-09-07 小欧 4.4.1: 删 cancelled——取消终态由 type=final+outcome=cancelled 承担, 前端不再消费 cancelled 事件
      case 'paused':
      case 'resumed':
      case 'retrying': {
        logTypeArrival(rawData.type, step.step); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
        // 小欧 2026-07-13: 后端 MetaStep 统一以 content 字段承载文本(与 ThoughtStep/FinalStep 契约一致),
        // 前端须读 content 而非旧 message 字段, 否则用户取消/重试提示显示为空(真实跨层缺陷, 已修)。
        const statusMessage = rawData.content || '';

        // 直接使用rawData.type作为step.type
        step.type = rawData.type as ExecutionStep['type'];
        step.content = statusMessage;

        // 小欧 2026-09-10 S12: 批量 append，零同步序列化
        pushAndFlush(handlers, step);
        onStep?.(step);

        // 根据type调用对应的回调
        switch (rawData.type) {
          case 'paused':
            onPaused?.(rawData.confirm_id as string | undefined); // 小欧 2026-09-10 S15: 传 confirmId
            if (rawData.confirm_id) {
              handlers.onAuthorizationRequired?.({
                confirm_id: rawData.confirm_id,
                tool_name: rawData.tool_name,
                params: rawData.params,
                content: rawData.content ?? '', // 7.4.1: 后端 ConfirmSpec.content 弹窗原因 — 小欧-2026-09-18
                safety_level: rawData.safety_level,
                trust_path: rawData.trust_path ?? null,
                // 2026-09-03 小欧 落码: 改用normalizeAutoConfirm四态归一; 2026-09-12 修复: 函数更名normalizeBoolean — 小欧-2026-09-12
                auto_confirm: normalizeBoolean(rawData.auto_confirm),
                // 2026-09-03 小欧 镜像修复: 合法 0 不被 || 兜成 60(与 useAuthorization 的 parseTimeout 同语义)
                confirm_timeout: assignTimeout(rawData.confirm_timeout),
                backend_timeout: assignTimeout(rawData.backend_timeout),
              });
            }
            break;
          case 'resumed':
            // [63] 5.15 v1.29：authorization_resumed window 兜底派发删除（HITL 单源化）——
            //   S1 超时放行链路走 5.3 onResumed（emitEvent + 清 Store.pendingAuthorization）
            //   → useAuthorization 快照 effect 关弹窗
            onResumed?.(rawData.confirm_id as string | undefined); // 小欧 2026-09-10 S15: 传 confirmId
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

      // 2026-09-28 小欧: 注入应答 — 回调通知消费方(遵循本文件 onPaused/onXxx 回调分层,
      //   解析层不直接操作 UI 状态), 展示提示条 + 高亮左侧目标任务, 不进 liveMeta 错误位
      case 'merged': {
        logTypeArrival(rawData.type, step.step);
        step.type = rawData.type as ExecutionStep['type'];
        step.content = rawData.content || '';
        pushAndFlush(handlers, step);
        onStep?.(step);
        handlers.onMerged?.((rawData.merged_into_task_id as string) ?? null);
        step.timestamp = timestampValue;
        break;
      }
    }
  } catch (error) {
    // 2026-09-30 小欧 - 业务分支兜底：消费方回调抛错在此收口，不再误报"解析数据失败"，
    //   且不中断整条流（冒泡会把单个组件 render 抛错升级为断流 = 功能退化）。
    console.error('[SSE] 事件处理失败（已跳过该帧的后续处理，流继续）:', error);
  }
};

export { processSSEData };
