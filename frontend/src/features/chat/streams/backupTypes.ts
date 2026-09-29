// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.1 StreamBackup / SessionSnapshot / StreamEvent 类型单一来源(5.4 内存态与 5.2 备份态同源) — 小欧-2026-09-29 21:37:55
//   增补1: 2026-09-29 21:37:55 小欧 - StreamEvent 增 'merged' kind(sseParser.ts:153/:947 onMerged 真实回调，
//   设计[76] 6.14 活跃任务注入应答)：[63] 5.1 原稿 8 项缺此项，5.3 接线将无载荷可投、注入提示条永不触发 — 小欧-2026-09-29 21:37:55
//   增补2: 2026-09-29 21:37:55 小欧 - complete 载荷 meta 由 unknown 改 string|SSEMetadata，
//   对齐 useChatCallbacks.ts:97-101 真实 onComplete 签名，消除分发侧断言 — 小欧-2026-09-29 21:37:55
// [63] 5.1：StreamBackup / SessionSnapshot / StreamEvent 唯一定义处（5.4 内存态与 5.2 备份态同源）
import type { ExecutionStep } from '@/types/execution';
// 2026-09-29 小欧: 原稿此 import 有两处笔误，本实现按 TS 编译事实修正——
//   ① TaskMetaFrames 重复 import 两次（文档 v1.29 修订时追加未删旧行）；② SSEError 使用却未 import。
//   组件层 AuthorizationRequest 类型刻意不入类型源（归一化留在 useAuthorization 消费侧，见 5.15）。
import type { SSEError, SSEMetadata, TaskMetaFrames } from '@/types/sse';

/** HITL 授权请求原始载荷：sseParser handlers.onAuthorizationRequired 的 detail 原样入 Store；
 *  归一化（auto_confirm 四态/parseTimeout）与 camel 映射留在 useAuthorization 消费侧（复用既有 helper，5.15） */
export interface PendingAuthorizationPayload {
  confirm_id: string;
  tool_name: string;
  params?: Record<string, unknown>;
  content?: string;
  safety_level?: string;
  trust_path?: string | null;
  auto_confirm?: boolean | string | number;
  confirm_timeout?: number | string;
  backend_timeout?: number | string;
}

export type StreamStatus =
  | 'idle'
  | 'active'
  | 'paused'
  | 'retrying'
  | 'recovering'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type ResumeResult =
  | 'terminal'
  | 'pending_draft'
  | 'recovering'
  | 'not_found'
  | 'polling'
  | 'aborted'
  | 'failed'
  | 'idle'
  | 'task_interrupted'
  | 'task_state_incomplete'
  | 'gap'
  | 'degraded';

export interface SessionSnapshot {
  serverTaskId: string | null;
  lastSeq: number; // event_log 已处理偏移，初始 -1
  executionSteps: ExecutionStep[];
  currentResponse: string;
  metaFrames: TaskMetaFrames;
  usageAccum: { prompt: number; completion: number; total: number };
  isReceiving: boolean;
  isConnected: boolean;
  status: StreamStatus;
  /** v1.29：raw 形态（见上方类型定义），归一化在消费侧 */
  pendingAuthorization: PendingAuthorizationPayload | null;
  reconnectStatus: 'idle' | 'connecting' | 'reconnecting' | 'failed';
  /**
   * 2026-09-29 22:47:10 小欧（[63] 5.4 防退化修复）：最近一次心跳时间戳。
   * 5.4 原稿未把它列入快照，bump() 因 11 个快照键全等而早退不通知 → useSyncExternalStore
   * 不重渲 → 等待期 ClockStopwatch 永不刷新（[46] 第五章 5.4.3 心跳微闪驱动源失效）。
   * 心跳是"UI 需要跟着动"的状态，故入快照：心跳到达即 bump revision + 通知订阅者。
   */
  heartbeatTs: number;
}

// v1.29 修：原 payload 为 ExecutionStep|string|Record 宽联合——消费方（5.8 分发）按 kind 读 payload
//   立即类型断裂，只能 as 断言（违类型安全）。改判别联合：kind → payload 联动窄化。
interface StreamEventBase {
  seq: number;
  taskId: string | null;
  sessionId: string;
  revision: number;
  occurredAt: number;
}
export type StreamEvent =
  | (StreamEventBase & { kind: 'step'; payload: { step: ExecutionStep; isReasoning?: boolean } })
  | (StreamEventBase & { kind: 'chunk'; payload: { chunk: string; isReasoning?: boolean } })
  | (StreamEventBase & {
      kind: 'complete';
      // 2026-09-29 小欧：meta 对齐真实 onComplete 签名（useChatCallbacks.ts:97-101
      //   `metadata?: string | SSEMetadata`）；原稿写 unknown 会迫使分发侧断言，违类型安全
      payload: { full: string; meta?: string | SSEMetadata; steps?: ExecutionStep[] };
    })
  | (StreamEventBase & { kind: 'error'; payload: SSEError | string })
  | (StreamEventBase & { kind: 'paused'; payload: { confirmId?: string } })
  | (StreamEventBase & { kind: 'resumed'; payload: { confirmId?: string } })
  | (StreamEventBase & {
      kind: 'retry';
      payload: { message: string; waitTime?: number };
    })
  | (StreamEventBase & {
      kind: 'rejected';
      payload: {
        step: number;
        message: string;
        tool_name?: string;
        reject_type: string;
      };
    })
  // 2026-09-29 小欧：[63] 5.1 原稿缺 'merged' kind，但 sseParser.ts:153/:947 已有 onMerged 回调
  //   （设计[76] 6.14 活跃任务注入应答 2026-09-28 落地）。缺则 5.3 接线无载荷可投，
  //   注入提示条/目标高亮永不触发（功能退化）——按真实回调签名补齐。
  | (StreamEventBase & { kind: 'merged'; payload: { mergedIntoTaskId: string | null } });

export interface StreamBackup
  extends Omit<SessionSnapshot, 'serverTaskId' | 'executionSteps' | 'reconnectStatus'> {
  version: 2;
  revision: number;
  sessionId: string;
  taskId: string | null;
  steps: ExecutionStep[];
  hitlWaitingKeys: string[];
  pendingMessage: {
    clientMessageId: string;
    content: string;
    state: 'queued' | 'sent';
  } | null;
  lastContextLinkMode: 'linked' | 'independent';
  updatedAt: number;
}
