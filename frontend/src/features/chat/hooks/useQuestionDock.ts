// 2026-11-18 商量 - 新建 question dock 状态管理(对齐 useAuthorization: 读 store 快照→归一→fire-and-forget 调 API→清快照)
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';

import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import { useChatStreamSession } from '@/features/chat/streams/useChatStreamSession';
import { ErrorType, handleError } from '@/services/error/handler';
import { taskControlApi } from '@/services/api/task.api';
import type { QuestionItem } from '@/types/chat';

export interface QuestionRequest {
  questionId: string;
  questions: QuestionItem[];
  content?: string;
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

  // 快照 → 请求态(同 id 去重, 新问询重置分页/答案/自定义)
  useEffect(() => {
    if (!pendingQuestion?.question_id) {
      setRequest(null);
      return;
    }
    setRequest((prev) => {
      if (prev?.questionId === pendingQuestion.question_id) return prev;
      setState(EMPTY_STATE);
      return {
        questionId: pendingQuestion.question_id,
        questions: pendingQuestion.questions || [],
        content: pendingQuestion.content,
      };
    });
  }, [pendingQuestion]);

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

  const submit = useCallback(() => {
    if (!request || submittingRef.current) return;
    submittingRef.current = true;
    const answers = request.questions.map((_, i) => {
      const values = [...(state.answers[i] ?? [])];
      const c = state.customs[i];
      const text = c?.text?.trim();
      if (c?.on && text) values.push(text);
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
  }, [request, state.answers, state.customs, close]);

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
    ]
  );
}

export type QuestionDockController = ReturnType<typeof useQuestionDock>;
