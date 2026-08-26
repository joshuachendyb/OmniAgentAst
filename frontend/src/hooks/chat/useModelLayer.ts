/**
 * useModelLayer - 模型三层继承前端 selector（L1 全局 / L2 会话级 / L3 暂缓）
 *
 * 【小欧 2026-08-26 8.13】5.1/5.2：生效模型 = L2(sessionModelOverride) ?? L1(current_model_ref)；
 * 来源徽标 source 标注层级。L2 写库走既有 sessionApi.updateSession(..., sessionModel)
 * （api.ts 已支持，见 2026-08-22 归一更新），ModelPicker 弹框确认后调用 saveL2()。
 * L3 任务级覆盖按 5.4 定案暂缓，本 hook 预留 overrideL3 入参位但不实现。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { configApi, sessionApi } from '../../services/api';
import type { SessionModelOverride } from '../../types/chat';

export interface EffectiveModel {
  provider: string;
  model: string;
  api_base?: string;
  display_name?: string;
  source: 'global' | 'session'; // 来源徽标
}

export const useModelLayer = (options: {
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  setSessionVersion: (v: number) => void;
}) => {
  const { sessionId, sessionTitle, sessionVersion, setSessionVersion } =
    options;
  const [l1, setL1] = useState<SessionModelOverride | null>(null);
  const [l2, setL2] = useState<SessionModelOverride | null>(null);

  useEffect(() => {
    configApi
      .getFullConfig()
      .then((cfg) => setL1(cfg.current_model_ref))
      .catch(() => setL1(null));
  }, []);

  const effective: EffectiveModel | null = useMemo(() => {
    const pick = (
      m: SessionModelOverride | null | undefined,
      source: EffectiveModel['source']
    ): EffectiveModel | null =>
      m && m.provider && m.model ? { ...m, source } : null;
    return pick(l2, 'session') ?? pick(l1, 'global');
  }, [l1, l2]);

  const saveL2 = useCallback(
    async (next: SessionModelOverride | null) => {
      if (!sessionId) return;
      // 显式传 null = 清除覆盖 = 跟随全局（api.ts updateSession 既有契约）
      const resp = await sessionApi.updateSession(
        sessionId,
        sessionTitle,
        sessionVersion,
        next
      );
      setL2(next);
      if (resp.version) setSessionVersion(resp.version);
    },
    [sessionId, sessionTitle, sessionVersion, setSessionVersion]
  );

  return { effective, l1, l2, saveL2, setL2 };
};
