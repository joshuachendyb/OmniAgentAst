// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D —— 会话级路由模式(suggest/auto/strict)唯一读写 hook。
//   读: GET /sessions/{id}(后端缺省归一 suggest); 写: updateSessionRoutingMode(乐观锁 409 回读) — 小欧-2026-11-16

// 2026-11-16 小欧 修正: setMode 乐观更新即时反馈, 失败回滚到切换前(409 回读失败也回滚)

// 2026-11-18 opencode 修正: setMode 增会话在途判据 —— 原 await 之后无条件 setVersion/
//   setModeState, 请求在途时切会话会把旧会话的版本号与模式写到新会话上(且新会话的选择器
//   会显示旧会话的模式) — opencode-2026-11-18


/**
 * useRoutingMode —— 会话级能力路由模式。
 *
 * 无会话时为 suggest 且不可写(选择器置灰); 切会话重新拉取; 写库走唯一薄出口。
 * isCurrentSession: 由调用方注入的"当前会话仍是我"判据(通常读 currentSessionIdRef),
 *   在途期间切会话即丢弃回写 —— 副作用只对发起请求的那个会话有效。
 */
import { useCallback, useEffect, useState } from 'react';
import { sessionApi } from '@/services/api/session.api';
import { showSaveError } from '@/utils/chatMessages';
import type { RoutingMode } from '@/types/chat';

export type { RoutingMode };

const normalize = (v: unknown): RoutingMode =>
  v === 'auto' || v === 'strict' ? v : 'suggest';

export function useRoutingMode(
  sessionId: string | null,
  version: number,
  setVersion: (v: number) => void,
  isCurrentSession?: () => boolean
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
      const alive = () => !isCurrentSession || isCurrentSession();
      const prev = mode;
      setModeState(next); // 乐观更新即时反馈, 失败回滚
      setSaving(true);
      try {
        const res = await sessionApi.updateSessionRoutingMode(
          sessionId,
          next,
          version
        );
        if (res.version && alive()) setVersion(res.version);
      } catch (err: unknown) {
        const status = (err as { response?: { status: number } })?.response
          ?.status;
        if (status === 409) {
          try {
            const s = await sessionApi.getSession(sessionId);
            if (!alive()) return;
            if (s.version) setVersion(s.version);
            setModeState(normalize(s.routingMode));
          } catch {
            if (alive()) setModeState(prev); // 回读失败回滚到切换前
          }
        } else if (alive()) {
          setModeState(prev);
          showSaveError('切换路由模式失败，请重试');
        }
      } finally {
        setSaving(false);
      }
    },
    [sessionId, version, setVersion, isCurrentSession, mode]
  );

  return { mode, setMode, saving };
}
