// 编辑历史: 2026-11-09 小欧 - 新建：③区 Provider 草稿写入（签名去重防上报 effect 循环），原 useSettings 逻辑原样搬迁 — 小欧-2026-11-09
import { useCallback, type Dispatch, type SetStateAction } from 'react';
import type { SettingsState } from '../types';

interface ProviderDraftDeps {
  setState: Dispatch<SetStateAction<SettingsState>>;
}

export function useProviderDraft({ setState }: ProviderDraftDeps) {
  // ③区草稿写入：JSON 签名等价去重是防 ProviderConfig 上报 effect（每渲染无条件通知）造成
  //   setState→渲染→effect 循环的唯一防线——同一 diff 重报时返回原 state 引用、不触发渲染，组件侧不再去重 - 小欧-2026-09-27
  const setProviderDraft = useCallback(
    (draft: Record<string, unknown>) => {
      setState((s) => {
        if (JSON.stringify(s.model.providerDraft) === JSON.stringify(draft))
          return s;
        return { ...s, model: { ...s.model, providerDraft: draft } };
      });
    },
    [setState]
  );

  return { setProviderDraft };
}
