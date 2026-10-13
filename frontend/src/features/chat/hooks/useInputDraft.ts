// 编辑历史: 2026-10-13 13:45 小欧 - 新建: 输入草稿单一真源(内存 state + sessionStorage 持久化)
//   存在理由(非过度抽象): ChatInput 的 draft 有 4 个写入点(onChange / 指令追加 / 发送清空 / 失败回填),
//   手工在各处补一句 saveDraft 必漏一处, 产生"内存与存储不一致"。
//   本仓已因此出过事故(linkEnabled、sessionModel 漏字段), 故抽 hook 收口。
//   复用 chatStreamPersistence 的 saveDraft/loadDraft(自 2026-09-29 起已写好但长期零调用方)
import { useCallback, useEffect, useRef, useState } from 'react';
import { loadDraft, saveDraft } from '../streams/chatStreamPersistence';

/** 新会话(sessionId 尚未生成)时的哨兵 key: 防 null 拼进键名变成 sse_draft_v1_null 导致跨会话串草稿 */
const NEW_SESSION_KEY = '__new__';

const draftKeyOf = (sessionId: string | null): string =>
  sessionId ?? NEW_SESSION_KEY;

export interface InputDraftApi {
  draft: string;
  /** 与原生 useState 的 setState 同签名, 既有调用点(含函数式更新)零改动 */
  setDraft: React.Dispatch<React.SetStateAction<string>>;
}

/**
 * @param sessionId 当前会话 id; null/空表示"新会话尚未创建"
 */
export const useInputDraft = (sessionId?: string | null): InputDraftApi => {
  const [draft, setDraftState] = useState('');
  /** 镜像 draft, 供 setDraft 计算函数式更新时读到最新值(避免闭包过期) */
  const draftRef = useRef('');
  const sidRef = useRef<string | null>(sessionId ?? null);
  const initedRef = useRef(false);

  const applyDraft = useCallback((text: string) => {
    draftRef.current = text;
    setDraftState(text);
  }, []);

  /**
   * 载入时机(关键, 错则会吞掉用户刚打的字):
   *   ①首次挂载 → 载入, 用于刷新页面后恢复草稿;
   *   ②之后仅当「上一次是非 null 的会话」且变成了别的会话 → 载入目标会话草稿(即真正的会话切换)。
   *   刻意不在 null → 具体 id 时载入: 那是 useChatSend.ts:176 建会话后的回填(同一发送流程内),
   *   用户很可能已接着打下一条, 此时载入新会话的空草稿会把刚打的字覆盖掉。
   */
  useEffect(() => {
    const next = sessionId ?? null;
    const prev = sidRef.current;
    sidRef.current = next;
    if (!initedRef.current) {
      initedRef.current = true;
      applyDraft(loadDraft(draftKeyOf(next)));
      return;
    }
    if (prev && prev !== next) applyDraft(loadDraft(draftKeyOf(next)));
  }, [sessionId, applyDraft]);

  const setDraft = useCallback<InputDraftApi['setDraft']>(
    (v) => {
      const next = typeof v === 'function' ? v(draftRef.current) : v;
      applyDraft(next);
      saveDraft(draftKeyOf(sidRef.current), next);
    },
    [applyDraft]
  );

  return { draft, setDraft };
};
