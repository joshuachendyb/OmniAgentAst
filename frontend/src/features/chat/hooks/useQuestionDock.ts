// 2026-11-18 商量 - 新建 question dock 状态管理(对齐 useAuthorization: 读 store 快照→归一→fire-and-forget 调 API→清快照)
// 2026-11-18 商量 - 三堂会审整改: 自定义输入框内按键不再触发面板快捷键; 自定义答案单选替换多选追加(防 radio 双值歧义); 新增 canSubmit 空答案守卫
// 2026-11-18 商量 - 新增倒计时: 读快照 backendTimeout 每秒递减纯展示(到点清窗由后端 question_resolved 收口, 单一权威源)
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';

import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import { useChatStreamSession } from '@/features/chat/streams/useChatStreamSession';
import { useCountdown } from '@/hooks/useCountdown';
import { ErrorType, handleError } from '@/services/error/handler';
import { taskControlApi } from '@/services/api/task.api';
import type { QuestionItem } from '@/types/chat';

export interface QuestionRequest {
  questionId: string;
  questions: QuestionItem[];
  backendTimeout?: number; // 2026-11-18 商量: 后端问询窗口秒数(已由 sseParser assignTimeout 归一), dock 倒计时
}

interface CustomState {
  on: boolean;
  text: string;
}

interface DockState {
  tab: number;
  answers: Record<number, string[]>;
  customs: Record<number, CustomState>;
  minimized: boolean;
}

const EMPTY_STATE: DockState = {
  tab: 0,
  answers: {},
  customs: {},
  minimized: false,
};

/** question 阻塞问答面板控制器 — 与 useAuthorization 同构的数据流 */
export function useQuestionDock(sessionId: string | null) {
  const { pendingQuestion } = useChatStreamSession(sessionId);
  const [request, setRequest] = useState<QuestionRequest | null>(null);
  const [state, setState] = useState<DockState>(EMPTY_STATE);
  const submittingRef = useRef(false);
  // 2026-11-18 商量 - 换题重置改为 ref 门控: 原写法在 setRequest 的更新函数内调 setState,
  //   更新函数须为纯函数(严格模式下会被调用两次 → 重置执行两次); 用 ref 记录已见 id 后同一处只做一件事
  const lastQuestionIdRef = useRef<string | null>(null);

  // 快照 → 请求态(同 id 去重, 新问询重置分页/答案/自定义)
  useEffect(() => {
    const id = pendingQuestion?.question_id ?? null;
    if (!id) {
      lastQuestionIdRef.current = null;
      setRequest(null);
      return;
    }
    if (lastQuestionIdRef.current === id) return;
    lastQuestionIdRef.current = id;
    setState(EMPTY_STATE);
    setRequest({
      questionId: id,
      questions: pendingQuestion?.questions || [],
      backendTimeout:
        typeof pendingQuestion?.backend_timeout === 'number'
          ? pendingQuestion.backend_timeout
          : undefined,
    });
  }, [pendingQuestion]);

  // 2026-11-18 商量 - 倒计时纯展示: 到点动作不在前端做 —— 后端窗口收口发 question_resolved(expired) 清窗, 单一权威源
  const countdown = useCountdown(
    request?.backendTimeout ?? 0,
    request?.questionId
  );

  const questions = request?.questions ?? [];
  const total = questions.length;
  const tab = Math.min(state.tab, Math.max(total - 1, 0));
  const current = questions[tab];
  const selected = useMemo(
    () => state.answers[tab] ?? [],
    [state.answers, tab]
  );
  const custom = useMemo(
    () => state.customs[tab] ?? { on: false, text: '' },
    [state.customs, tab]
  );

  const close = useCallback(() => {
    setRequest(null);
    setState(EMPTY_STATE);
    submittingRef.current = false;
    if (sessionId) chatStreamStore.acknowledgeQuestion(sessionId);
  }, [sessionId]);

  // 2026-11-18 商量 - 可提交判据: 任一题已有选中项或已填自定义答案(空提交无合法含义, "取消"才是放弃)
  const canSubmit = useMemo(() => {
    if (!request) return false;
    return request.questions.some((_, i) => {
      if ((state.answers[i]?.length ?? 0) > 0) return true;
      const c = state.customs[i];
      return Boolean(c?.on && c.text.trim());
    });
  }, [request, state.answers, state.customs]);

  const submit = useCallback(() => {
    if (!request || submittingRef.current || !canSubmit) return;
    submittingRef.current = true;
    const answers = request.questions.map((q, i) => {
      const values = [...(state.answers[i] ?? [])];
      const c = state.customs[i];
      const text = c?.text?.trim();
      if (c?.on && text) {
        // 2026-11-18 商量 - 自定义答案: 多选追加为额外项, 单选替换(与 opencode radio 语义一致, 防双值歧义)
        if (q.multiple) values.push(text);
        else return [text];
      }
      return values;
    });
    void taskControlApi
      .answerQuestion(request.questionId, answers)
      .then((res) => {
        if (
          !res?.success &&
          (res as { code?: string })?.code !== 'question_stale'
        ) {
          handleError({
            message: res?.message || '提交回答失败',
            error_type: ErrorType.WARNING,
          });
        }
        close();
      })
      .catch((e) => {
        handleError({
          message: e?.message || '提交回答失败',
          error_type: ErrorType.WARNING,
        });
        submittingRef.current = false;
      });
  }, [request, state.answers, state.customs, canSubmit, close]);

  const cancel = useCallback(() => {
    if (!request || submittingRef.current) return;
    submittingRef.current = true;
    void taskControlApi
      .answerQuestion(request.questionId, [], true)
      .catch((e) => {
        handleError({
          message: e?.message || '取消回答失败',
          error_type: ErrorType.WARNING,
        });
      })
      .finally(() => {
        close();
      });
  }, [request, close]);

  const selectOption = useCallback(
    (label: string) => {
      setState((prev) => {
        const old = prev.answers[tab] ?? [];
        const multiple = Boolean(current?.multiple);
        const next = multiple
          ? old.includes(label)
            ? old.filter((x) => x !== label)
            : [...old, label]
          : [label];
        return { ...prev, answers: { ...prev.answers, [tab]: next } };
      });
    },
    [tab, current]
  );

  const toggleCustom = useCallback(() => {
    setState((prev) => {
      const c = prev.customs[tab] ?? { on: false, text: '' };
      return {
        ...prev,
        customs: { ...prev.customs, [tab]: { ...c, on: !c.on } },
      };
    });
  }, [tab]);

  const setCustomText = useCallback(
    (text: string) => {
      setState((prev) => {
        const c = prev.customs[tab] ?? { on: false, text: '' };
        return {
          ...prev,
          customs: { ...prev.customs, [tab]: { ...c, text } },
        };
      });
    },
    [tab]
  );

  const goTab = useCallback(
    (index: number) => {
      if (index >= 0 && index < total)
        setState((prev) => ({ ...prev, tab: index }));
    },
    [total]
  );

  const next = useCallback(() => {
    if (tab < total - 1) goTab(tab + 1);
    else submit();
  }, [tab, total, goTab, submit]);

  const prev = useCallback(() => {
    if (tab > 0) goTab(tab - 1);
  }, [tab, goTab]);

  const toggleMinimize = useCallback(() => {
    setState((s) => ({ ...s, minimized: !s.minimized }));
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (!current) return;
      // 2026-11-18 商量 - 自定义输入框内的按键不触发面板快捷键(防数字选中/方向键切题/Escape误取消)
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'TEXTAREA' || tag === 'INPUT') return;
      if (e.key === 'Escape') {
        e.preventDefault();
        cancel();
        return;
      }
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        submit();
        return;
      }
      if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault();
        prev();
        return;
      }
      if (/^[1-9]$/.test(e.key)) {
        const idx = Number(e.key) - 1;
        const opt = current.options?.[idx];
        if (opt) {
          e.preventDefault();
          selectOption(opt.label);
        }
        return;
      }
      if (e.key === 'ArrowRight' && tab < total - 1) {
        e.preventDefault();
        goTab(tab + 1);
      } else if (e.key === 'ArrowLeft' && tab > 0) {
        e.preventDefault();
        goTab(tab - 1);
      }
    },
    [current, cancel, submit, prev, goTab, tab, total, selectOption]
  );

  return useMemo(
    () => ({
      request,
      total,
      tab,
      current,
      selected,
      custom,
      minimized: state.minimized,
      selectOption,
      toggleCustom,
      setCustomText,
      goTab,
      next,
      prev,
      submit,
      cancel,
      toggleMinimize,
      handleKeyDown,
      canSubmit,
      countdown,
    }),
    [
      request,
      total,
      tab,
      current,
      selected,
      custom,
      state.minimized,
      selectOption,
      toggleCustom,
      setCustomText,
      goTab,
      next,
      prev,
      submit,
      cancel,
      toggleMinimize,
      handleKeyDown,
      canSubmit,
      countdown,
    ]
  );
}

export type QuestionDockController = ReturnType<typeof useQuestionDock>;
