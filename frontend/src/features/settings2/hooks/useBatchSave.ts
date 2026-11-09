// 编辑历史: 2026-11-09 小欧 - 新建：按组保存与保存全部的三路串行编排，原 useSettings 逻辑原样搬迁 — 小欧-2026-11-09
import { useCallback } from 'react';
import type { SaveResult, SettingsState, TabKey } from '../types';

interface BatchSaveDeps {
  state: SettingsState;
  groupOfKey: (key: string) => string | null;
  saveKeys: (
    keys: string[],
    opts?: { skipMtimeCheck?: boolean }
  ) => Promise<SaveResult>;
  saveModelGroup: (opts?: { skipMtimeCheck?: boolean }) => Promise<SaveResult>;
  saveProviderDraft: (patch?: Record<string, unknown>) => Promise<SaveResult>;
}

export function useBatchSave({
  state,
  groupOfKey,
  saveKeys,
  saveModelGroup,
  saveProviderDraft,
}: BatchSaveDeps) {
  const saveGroup = useCallback(
    async (tab: TabKey): Promise<SaveResult> => {
      // 2026-09-27 小欧 - 模型组 = 参数/能力/删键 落库后串行 flush ③区草稿（参数保存失败时
      //   load(reset) 可能已清草稿，此时直接返回不重复提交，对齐"已丢失"提示语义）- 小欧-2026-09-27
      if (tab === 'model') {
        const a = await saveModelGroup();
        if (!a.ok) return a;
        return saveProviderDraft();
      }
      const keys = Object.keys(state.dirtyKeys).filter(
        (k) => groupOfKey(k) === tab
      );
      return saveKeys(keys);
    },
    [groupOfKey, state.dirtyKeys, saveKeys, saveModelGroup, saveProviderDraft]
  );

  // ---- 保存全部：设置项/模型参数/③区草稿三路串行落盘 ----
  const saveAll = useCallback(async (): Promise<{ ok: boolean }> => {
    // 2026-11-09 小欧 - 撤 `!k.startsWith('model.')` 过滤：dirtyKeys 只由设置项 setValue 写入，
    //   注册表无 model.* 键，该过滤恒真为死条件 — 小欧-2026-11-09
    const keys = Object.keys(state.dirtyKeys);
    const hasDraft = Object.keys(state.model.providerDraft).length > 0;
    if (!keys.length && !state.model.isDirty && !hasDraft) return { ok: true };

    // 改串行：原 Promise.all 并发时两路拿同一个旧 mtime 做守卫，先落盘的一路 bump 服务端 mtime，
    //   后一路必然误判「外部更新」→ load(reset) 清空全部未保存改动；且共享单个 saving 布尔会提前解锁按钮。
    if (keys.length) {
      const r = await saveKeys(keys);
      if (!r.ok) return { ok: false };
    }
    if (state.model.isDirty) {
      const r = await saveModelGroup({ skipMtimeCheck: true });
      if (!r.ok) return { ok: false };
    }
    const d = await saveProviderDraft();
    return { ok: d.ok };
  }, [
    state.dirtyKeys,
    state.model.isDirty,
    state.model.providerDraft,
    saveKeys,
    saveModelGroup,
    saveProviderDraft,
  ]);

  return { saveGroup, saveAll };
}
