// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离会话时间元数据逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useEffect, useState } from 'react';
import { sessionApi } from '../../../services/api/session.api';

/**
 * 会话元数据 hook：拉取会话创建/更新时间（顶栏悬浮数据源）
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useSessionMeta(sessionId: string | null) {
  // 【小欧 2026-08-26 修复 A1】会话创建/更新时间(7.1⑤ 顶栏悬浮数据源)
  const [sessionTimes, setSessionTimes] = useState<{
    createdAt?: string;
    updatedAt?: string;
  }>({});
  useEffect(() => {
    if (!sessionId) return;
    sessionApi
      .getSession(sessionId)
      .then((s) =>
        setSessionTimes({ createdAt: s.created_at, updatedAt: s.updated_at })
      )
      .catch(() => undefined);
  }, [sessionId]);

  return { sessionTimes };
}
