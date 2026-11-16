// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级路由模式(suggest/auto/strict)唯一读写 hook。
//   读: GET /sessions/{id}(后端缺省归一 suggest); 写: updateSessionRoutingMode(乐观锁 409 回读) — 小欧-2026-11-16

/**
 * useRoutingMode —— 会话级能力路由模式。
 *
 * 无会话时为 suggest 且不可写(选择器置灰); 切会话重新拉取; 写库走唯一薄出口。
 */
import { useCallback, useEffect, useState } from 'react';
import { sessionApi } from '@/services/api/session.api';
import { showSaveError } from '@/utils/chatMessages';

export type RoutingMode = 'suggest' | 'auto' | 'strict';

const normalize = (v: unknown): RoutingMode =>
  v === 'auto' || v === 'strict' ? v : 'suggest';

export function useRoutingMode(
  sessionId: string | null,
  version: number,
  setVersion: (v: number) => void
) {
  const [mode, setModeState] = useState<RoutingMode>('suggest');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    if (!sessionId) {
      setModeState('suggest');
      return;
    }
    void sessionApi
      .getSession(sessionId)
      .then((s) => {
        if (alive) setModeState(normalize(s.routingMode));
      })
      .catch(() => {
        if (alive) setModeState('suggest');
      });
    return () => {
      alive = false;
    };
  }, [sessionId]);

  const setMode = useCallback(
    async (next: RoutingMode) => {
      if (!sessionId) return;
      setSaving(true);
      try {
        const res = await sessionApi.updateSessionRoutingMode(
          sessionId,
          next,
          version
        );
        if (res.version) setVersion(res.version);
        setModeState(next);
      } catch (err: unknown) {
        const status = (err as { response?: { status: number } })?.response
          ?.status;
        if (status === 409) {
          try {
            const s = await sessionApi.getSession(sessionId);
            if (s.version) setVersion(s.version);
            setModeState(normalize(s.routingMode));
          } catch {
            // 回读失败保持当前值
          }
        } else {
          showSaveError('切换路由模式失败，请重试');
        }
      } finally {
        setSaving(false);
      }
    },
    [sessionId, version, setVersion]
  );

  return { mode, setMode, saving };
}
