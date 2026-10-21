// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.3 新建：文件页→对话页一次性引用通道（useSyncExternalStore 契约） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§9.4(O4/O3)：push 去重（同 path+lineRange 替换而非追加）+ pending 字段 — 小杨-2026-10-21
/**
 * composerRefStore —— 跨页一次性引用投递通道
 *
 * 存在理由（M21）：对话页 ChatInput 常驻不卸载，同路由仅 query 变化时 React 不重挂载，
 *   挂载时取一次会**静默丢引用**。故必须做成"外部 store + 订阅"（useSyncExternalStore 契约），
 *   与 features/chat/streams/chatStreamStore.ts 同范式。
 *
 * 语义：
 * - push 原样入队，不做体积降级、不限条数、不截断（v3.4 裁定：引用多少发多少）
 * - takeAll 取出并清空（一次性消费）
 * - 快照 = 队列长度（变化即触发消费 effect）
 */
import type { ChatRefPayload } from '../../../types/chat';

export type ComposerRef = ChatRefPayload & {
  id: string;
  /**
   * O3：`@` 补全在途占位（正文尚未读到位，content 为空）。
   * 发送闸门据此阻断（防发出 content:''），token 渲染据此显示"载入中"。
   * ⚠ 该字段**只在前端内存态**，上行前一律剥离（见 chatStreamTransport.buildStreamBody）。
   */
  pending?: boolean;
};

/**
 * 引用 id：调用方生成（后端不认此 id，仅前端去重用）。
 * 2026-10-21 小杨 - 文档[28] v5.12：改用仓库既有约定 crypto.randomUUID()
 *   （先例 chatStreamStore.ts:715 clientMessageId），不自造 Date+Math.random 拼接。
 *   jsdom 缺 crypto.randomUUID 时按仓库先例补桩（见 tests/stage1_s8.test.ts）。
 */
export const newRefId = (): string => crypto.randomUUID();

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
   * 原样入队；同 path + 同 lineRange 视为**同一引用** → 替换而非追加（O4）。
   * 替换而非追加的原因：用户重复引用同一文件时，token 不应出现两个，
   * 且后一次的内容（更接近当前盘面）应覆盖前一次。
   */
  push(ref: ComposerRef): void {
    const keyOf = (r: ComposerRef) =>
      `${r.path ?? ''}|${r.lineRange ? `${r.lineRange.start}-${r.lineRange.end}` : ''}`;
    const k = keyOf(ref);
    const i = queue.findIndex((r) => keyOf(r) === k);
    if (i >= 0) queue.splice(i, 1, ref);
    else queue.push(ref);
    emit();
  },
};
