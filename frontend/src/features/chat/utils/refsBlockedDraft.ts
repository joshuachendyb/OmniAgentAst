// 编辑历史: 2026-10-30 小欧 - 新建: refs_blocked 草稿回填的一次性信号通道 — 小欧-2026-10-30
//   归属 utils/ 而非 streams/: streams/ 的审计口径是"会话流态一律挂 ChatStreamSession",
//   本通道是全局一次性 UI 指令(与 recentInputs 同类), 不承载任何会话态 — 小欧-2026-10-30
/**
 * refsBlockedDraft —— 引用阻断后的草稿回填信号(useSyncExternalStore 契约)
 *
 * 存在理由(4.8「阻断时草稿保留」)：refs_blocked 是 SSE 错误帧, onSend/sendMessage
 *   **正常 resolve**, ChatInput 的 catch 回填永不触发 → 发送时乐观清空的草稿再也回不来,
 *   而提示又要求用户"移除后重发", 只能重打正文。
 * 通道语义：transport 侧在阻断时写入待回填正文(一次性), 输入框消费后立即清空;
 *   输入框已有新输入时不覆盖(以用户当前输入为准)。
 */

let _draft: string | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((cb) => cb());

export const refsBlockedDraftStore = {
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  },
  getSnapshot(): string | null {
    return _draft;
  },
  /** 阻断时投递待回填草稿(空正文不投递) */
  signal(text: string): void {
    if (!text) return;
    _draft = text;
    emit();
  },
  /** 一次性取出并清空 */
  consume(): string | null {
    const v = _draft;
    if (v === null) return null;
    _draft = null;
    emit();
    return v;
  },
};
