// 编辑历史: 2026-10-21 小杨 - 新建：文件页→对话页一次性引用通道（useSyncExternalStore 契约）；
//   push 去重（同 path+lineRange 替换而非追加）+ pending 字段 — 小杨-2026-10-21
// 编辑历史: 2026-10-21 小杨 - 抽出 refKeyOf/mergeRefs，供跨页消费与 @ 选中共用去重 — 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 自 features/chat/streams/composerRefStore.ts 迁入（内容零改动，仅改 import 路径）— 小欧-2026-10-22
//   迁移理由：文件页（pages/Files）需要引用能力，而 composerRefStore 藏在 chat 的私有
//   internals（streams/）里 → 形成 pages/Files → features/chat/streams 的反向依赖；
//   再加"工作区反链"会让它变成双向依赖（环）。上提到共享域 features/refs/ 后，
//   chat 与 files 各自向下依赖，依赖图单向无环。
//   迁移按 AGENTS「能复制就复制，不重写」执行：代码逐字搬运，仅改 import 路径。

// 编辑历史: 2026-10-29 小欧 - 引用条数上限与预检时间戳: 新增 MAX_REFS=20(与 services/refs/limits.py
//   同值, 单一真源双保险); ComposerRef 增 mtime/updated(预检本地留存, 上行前剥离, 供"内容已更新"比对);
//   push 改返回 boolean(入队成功/超上限被拒, 调用方据此点名) — 小欧-2026-10-29
// 编辑历史: 2026-10-30 小欧 - 取消链路批量格式化顺带换行(按项目 prettier 重排 push 长条件), 零逻辑改动 — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 三堂会审整改(A11/A12/A18): ①refKeyOf 先归一 path(盘符小写 + \→/),
//   同文件不同写法不再各占一条; ②删死字段 updated(实际用预检返回的独立数组); ③push 只算一次
//   refKeyOf(原 20 条约 41 次); ④新增 refLimitText() 供三处"超上限"提示复用 — 小欧-2026-10-30

/**
 * composerRefStore —— 跨页一次性引用投递通道
 *
 * 存在理由：对话页 ChatInput 常驻不卸载，同路由仅 query 变化时 React 不重挂载，
 *   挂载时取一次会**静默丢引用**。故必须做成"外部 store + 订阅"（useSyncExternalStore 契约），
 *   与 features/chat/streams/chatStreamStore.ts 同范式。
 *
 * 语义：
 * - push 按同 key 原位替换入队，上限 MAX_REFS，不做体积降级、不截断（引用多少发多少）
 * - takeAll 取出并清空（一次性消费）
 * - 快照 = 队列长度（变化即触发消费 effect）
 */
import type { ChatRefPayload } from '../../types/chat';

// 2026-10-29 小欧 - 引用条数上限: 与 services/refs/limits.py:MAX_REFS 同值(单一真源, 双保险 L1)
export const MAX_REFS = 20;

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
  /**
   * 2026-10-29 小欧 - 预检取到的时间戳（probeRef/precheckRefs 本地留存，仅供「内容已更新」比对）。
   *   ⚠ 前端内存态（同 pending/invalid），上行前剥离（不进 wire）。
   */
  mtime?: string;
};

/** 超上限的统一提示文案（@补全 / 文件页 / 引用按钮三处共用，避免各写一份）— 小欧-2026-10-30 */
export const refLimitText = (): string => `一次最多引用 ${MAX_REFS} 项`;

/**
 * 引用 id：调用方生成（后端不认此 id，仅前端去重用）。
 * 2026-10-21 小杨 - 改用仓库既有约定 crypto.randomUUID()
 *   （先例 chatStreamStore.ts:715 clientMessageId），不自造 Date+Math.random 拼接。
 *   jsdom 缺 crypto.randomUUID 时按仓库先例补桩（见 tests/stage1_s8.test.ts）。
 */
export const newRefId = (): string => crypto.randomUUID();

/**
 * 同 key 归一口径：盘符统一小写 + 反斜杠转正斜杠（设计 4.5/5.4.2）。
 * 不归一的话 `C:\a\b.txt` 与 `c:/a/b.txt` 会被当成两条引用，分别占用 MAX_REFS 配额、
 * 后端也会按不同 path 各读一次。
 */
const normalizeRefPath = (path?: string): string => {
  if (!path) return '';
  const s = path.replace(/\\/g, '/');
  return /^[a-zA-Z]:/.test(s) ? s[0].toLowerCase() + s.slice(1) : s;
};

/** 同一文件 + 同一行区间视为同一引用（整文件 lineRange 为空）— 小杨-2026-10-21 */
export const refKeyOf = (r: Pick<ComposerRef, 'path' | 'lineRange'>): string =>
  `${normalizeRefPath(r.path)}|${
    r.lineRange ? `${r.lineRange.start}-${r.lineRange.end}` : ''
  }`;

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
   * 入队；同 path + 同 lineRange 视为**同一引用** → 替换而非追加。
   * 2026-10-29 小欧 - 限 MAX_REFS：超限返回 false 不 throw（调用方判真值提示"一次最多引用 20 项"，
   *   quote.ts / @补全 / Files 三调用方同批消费返回值）。
   */
  push(ref: ComposerRef): boolean {
    // 2026-10-30 小欧 A18: 只算一次 key —— 原实现上限判定/查找/替换各算一次,
    //   20 条待发时一次 push 要做约 41 次 key 拼接。
    const k = refKeyOf(ref);
    if (queue.length >= MAX_REFS && !queue.some((r) => refKeyOf(r) === k)) {
      return false;
    }
    const i = queue.findIndex((r) => refKeyOf(r) === k);
    if (i >= 0) queue.splice(i, 1, ref);
    else queue.push(ref);
    emit();
    return true;
  },
};
