// 编辑历史: 2026-10-21 小杨 - 新建：文件页→对话页一次性引用通道（useSyncExternalStore 契约）；
//   push 去重（同 path+lineRange 替换而非追加）+ pending 字段 — 小杨-2026-10-21
// 编辑历史: 2026-10-21 小杨 - 抽出 refKeyOf/mergeRefs，供跨页消费与 @ 选中共用去重 — 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 自 features/chat/streams/composerRefStore.ts 迁入（内容零改动，仅改 import 路径）— 小欧-2026-10-22
//   迁移理由：文件页（pages/Files）需要引用能力，而 composerRefStore 藏在 chat 的私有
//   internals（streams/）里 → 形成 pages/Files → features/chat/streams 的反向依赖；
//   文档[42] 再加"工作区反链"会让它变成双向依赖（环）。上提到共享域 features/refs/ 后，
//   chat 与 files 各自向下依赖，依赖图单向无环。
//   迁移按 AGENTS「能复制就复制，不重写」执行：代码逐字搬运，仅改 import 路径。
/**
 * composerRefStore —— 跨页一次性引用投递通道
 *
 * 存在理由：对话页 ChatInput 常驻不卸载，同路由仅 query 变化时 React 不重挂载，
 *   挂载时取一次会**静默丢引用**。故必须做成"外部 store + 订阅"（useSyncExternalStore 契约），
 *   与 features/chat/streams/chatStreamStore.ts 同范式。
 *
 * 语义：
 * - push 原样入队，不做体积降级、不限条数、不截断（引用多少发多少）
 * - takeAll 取出并清空（一次性消费）
 * - 快照 = 队列长度（变化即触发消费 effect）
 */
import type { ChatRefPayload } from '../../types/chat';

export type ComposerRef = ChatRefPayload & {
  id: string;
  /**
   * `@` 补全在途占位（正文尚未读到位，content 为空）。
   * 发送闸门据此阻断（防发出 content:''），token 渲染据此显示"载入中"。
   * ⚠ 该字段**只在前端内存态**，上行前一律剥离（见 chatStreamTransport.buildStreamBody）。
   */
  pending?: boolean;
  /**
   * 2026-10-21 小杨 - 引用失效可见：发送前校验失败的标记。
   *   文件被删/不可读 → 引用项标失效（chip 红底、阻断发送并点名），不再让模型收到废内容。
   *   ⚠ 前端内存态（同 pending），上行前剥离。
   */
  invalid?: boolean;
};

/**
 * 引用 id：调用方生成（后端不认此 id，仅前端去重用）。
 * 2026-10-21 小杨 - 改用仓库既有约定 crypto.randomUUID()
 *   （先例 chatStreamStore.ts:715 clientMessageId），不自造 Date+Math.random 拼接。
 *   jsdom 缺 crypto.randomUUID 时按仓库先例补桩（见 tests/stage1_s8.test.ts）。
 */
export const newRefId = (): string => crypto.randomUUID();

/** 同一文件 + 同一行区间视为同一引用（整文件 lineRange 为空）— 小杨-2026-10-21 */
export const refKeyOf = (r: Pick<ComposerRef, 'path' | 'lineRange'>): string =>
  `${r.path ?? ''}|${r.lineRange ? `${r.lineRange.start}-${r.lineRange.end}` : ''}`;

/** 合并引用：同 key 原位替换（后一次内容覆盖前一次），新 key 追加 — 小杨-2026-10-21 */
export const mergeRefs = (
  prev: ComposerRef[],
  incoming: ComposerRef[]
): ComposerRef[] => {
  const out = prev.slice();
  for (const ref of incoming) {
    const k = refKeyOf(ref);
    const i = out.findIndex((r) => refKeyOf(r) === k);
    if (i >= 0) out[i] = ref;
    else out.push(ref);
  }
  return out;
};

const queue: ComposerRef[] = [];
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((cb) => cb());

export const composerRefStore = {
  /** useSyncExternalStore 订阅入口 */
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  },
  /** 快照 = 待消费数量（变化即触发消费 effect） */
  getSnapshot(): number {
    return queue.length;
  },
  /** 取出全部并清空（一次性消费） */
  takeAll(): ComposerRef[] {
    const out = queue.slice();
    queue.length = 0;
    emit();
    return out;
  },
  /** 清空（测试/异常路径用） */
  clear(): void {
    queue.length = 0;
    emit();
  },
  /**
   * 原样入队；同 path + 同 lineRange 视为**同一引用** → 替换而非追加。
   * 替换而非追加的原因：用户重复引用同一文件时，token 不应出现两个，
   * 且后一次的内容（更接近当前盘面）应覆盖前一次。
   */
  push(ref: ComposerRef): void {
    const k = refKeyOf(ref);
    const i = queue.findIndex((r) => refKeyOf(r) === k);
    if (i >= 0) queue.splice(i, 1, ref);
    else queue.push(ref);
    emit();
  },
};

/**
 * enqueueRef —— 域内私有入队口（只有 quote.ts 的 quote* 调它；不 export）
 *
 * 2026-10-22 小欧 - 文档[43] R3/R4 v1.4（修 D5）：
 *   v1.3 曾 export enqueueRef 作为"第二入口"，但那样 INV-1（引用只有一个入口）
 *   名不副实——任何域外 import { enqueueRef } 都能绕过 quote* 投畸形 ref，
 *   而 G2 守卫查不到（enqueueRef 内部调 push，满足"push 只在 features/refs"）。
 *   v1.4 处置：不 export（TS 天然禁止域外调用），quoteFile/quoteSelection/
 *   quotePack 直接调 composerRefStore.push（都在 features/refs 域内，G2 通过）。
 *   域外（含 pages/Files 选区已有正文）一律经 quote* 的 content/size 覆盖项
 *   （见 R2），不再需要第二个入口。
 */
const enqueueRef = (ref: ComposerRef): void => {
  composerRefStore.push(ref);
};
