// 编辑历史: 2026-08-26 小欧 - 8.1/8.2 实施: 会话任务清单Hook, 顶栏任务数/左列共用, final/error后refresh(6.1.9 B1)
/**
 * useSessionTasks - 会话任务清单 Hook（消费 6.1.9 B1 接口）
 *
 * 【小欧 2026-08-26 8.1/8.2】顶栏任务数与左侧任务列表共用同一份数据；
 * 每任务结束后由调用方触发 refresh()（SSE final/error 后调用）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import { useCallback, useEffect, useState } from 'react';
import {
  sessionTaskApi,
  type SessionTaskItem,
} from '../../../services/api/task.api';

export const useSessionTasks = (sessionId: string | null) => {
  const [tasks, setTasks] = useState<SessionTaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setTasks([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const res = await sessionTaskApi.listTasks(sessionId);
      setTasks(res.tasks);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { tasks, total, loading, refresh };
};
