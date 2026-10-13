// 编辑历史: 2026-10-13 13:45 小欧 - 新建: 输入草稿单一真源(内存 state + sessionStorage 持久化)
//   复用 chatStreamPersistence 的 saveDraft/loadDraft(自 2026-09-29 起已写好但长期零调用方)
// 编辑历史: 2026-10-13 13:55 小欧 - 载入判据二轮修正+新增两个提交标记接口: 首版"上次非空才载入"有草稿泄漏与
//   无法区分回填两洞; 改为"变了就载入", 仅「标记在+上次无会话+提交后又打字」三条件才跳过(不吞连打的字)。
//   markSubmitted 在 setDraft('') 后 await onSend 前调, cancelSubmitted 在 catch 调(否则残留标记致下次漏载入)
// 编辑历史: 2026-10-13 14:50 小欧 - 撤回落盘防抖(自纠): 300ms 防抖致刷新丢字(刷新不执行 React 卸载清理),
//   4 条用例当场变红; 草稿体量小, 拿正确性换性能属退化, 退回同步落盘
/**
 * useInputDraft - 输入草稿单一真源
 *
 * 存在理由(非过度抽象): ChatInput 的 draft 有 4 个写入点(onChange / 指令追加 / 发送清空 / 失败回填),
 * 手工在各处补一句 saveDraft 必漏一处, 产生"内存与存储不一致"。本仓已因此出过事故
 * (linkEnabled、sessionModel 漏字段), 故抽 hook 收口。
 *
 * @author 小欧
 * @date 2026-10-13
 */
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
  /**
   * 标记"正在提交"。必须在 setDraft('') 之后、await onSend 之前调用。
   * 用途: 让本 hook 能把「发送建会话后的 sessionId 回填」与「用户真的切了会话」区分开。
   */
  markSubmitted: () => void;
  /** 提交失败时撤销标记(否则残留标记会让下次切会话漏载入) */
  cancelSubmitted: () => void;
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
  /** 提交标记: 有提交正在飞 */
  const submittedRef = useRef(false);
  /** 提交之后用户是否又打过字(飞回填窗口内) */
  const typedAfterSubmitRef = useRef(false);

  const applyDraft = useCallback((text: string) => {
    draftRef.current = text;
    setDraftState(text);
  }, []);

  /**
   * 载入时机(关键, 两处都错则会出事):
   *   ①首次挂载 → 载入, 用于刷新页面后恢复草稿;
   *   ②之后 sessionId 真的变了 → 载入目标会话草稿。这是**防草稿泄漏**的关键:
   *      用户在「新会话」打了草稿后点别的会话, 必须载入目标会话草稿, 不能留着旧草稿。
   *   ③唯一例外 —— 「发送建会话后的 null→sid 回填」: 同一发送流程内用户很可能已接着打下一条,
   *      此时载入新会话的空草稿会把刚打的字覆盖掉。
   *      判据 = 「提交标记在」且「上一次是无会话(null)」+「提交后又打过字」三条件同时成立。
   *      该判据无歧义: 无会话时提交必然创建会话(useChatSend 建会话分支), 故 null→sid 只可能是回填;
   *      而从会话列表点进已有会话时, 若 prev 已是具体 id, prev!==null 直接走正常载入。
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
    if (prev === next) return;
    const isSendBackfill =
      submittedRef.current && prev === null && typedAfterSubmitRef.current;
    submittedRef.current = false;
    if (!isSendBackfill) applyDraft(loadDraft(draftKeyOf(next)));
  }, [sessionId, applyDraft]);

  const setDraft = useCallback<InputDraftApi['setDraft']>(
    (v) => {
      if (submittedRef.current) typedAfterSubmitRef.current = true;
      const next = typeof v === 'function' ? v(draftRef.current) : v;
      applyDraft(next);
      // 2026-10-13 14:50 小欧 - 同步落盘, 不做防抖。
      //   曾改 300ms 防抖以减少同步 IO, 实测引入数据丢失回归: 刷新页面不会执行 React 卸载清理,
      //   防抖窗口内的输入全丢(C1/C5/C6/E13 四条用例当场变红)。草稿体量小(输入框可见 5 行),
      //   同步写的开销可接受 —— 拿正确性换微小性能属功能退化, 撤回。
      saveDraft(draftKeyOf(sidRef.current), next);
    },
    [applyDraft]
  );

  const markSubmitted = useCallback(() => {
    submittedRef.current = true;
    typedAfterSubmitRef.current = false;
  }, []);

  const cancelSubmitted = useCallback(() => {
    submittedRef.current = false;
    typedAfterSubmitRef.current = false;
  }, []);

  return { draft, setDraft, markSubmitted, cancelSubmitted };
};
