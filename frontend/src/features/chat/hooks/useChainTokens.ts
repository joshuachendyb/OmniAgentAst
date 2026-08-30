// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离链累计token逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.8 v1.103: 结束沿锚点加 latestTaskId 兜底(排序一义后 tasks[0]≈最旧, 原 DESC 首行=最新语义失效, 改显式最新锚点防 ASC 回归取错任务)
import { useEffect, useRef, useState } from 'react';
import { tokenUsageApi } from '../../../services/api/task.api';

/**
 * 链累计 token hook：切换会话重置、任务结束沿（isReceiving true→false）统一刷新任务列表与顶栏链累计 token
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChainTokens(
  sessionId: string | null,
  serverTaskId: string | null,
  isReceiving: boolean,
  latestTaskId: string | null, // 2026-08-30 小欧 diff⑤ v1.103: 最新任务显式锚点
  tasks: { task_id: string }[],
  refreshTasks: () => void
) {
  const [chainTokens, setChainTokens] = useState<number | null>(null); // 顶栏会话累计 token（A6 链口径）

  // 2026-08-27 修复#42: 切换会话时重置跨会话泄漏状态
  useEffect(() => {
    setChainTokens(null);
  }, [sessionId]);

  // 任务结束沿统一刷新：任务列表 / 顶栏链累计 token
  const prevReceivingRef = useRef(false);
  useEffect(() => {
    if (prevReceivingRef.current && !isReceiving) {
      void refreshTasks();
      if (sessionId) {
        const anchorTaskId = serverTaskId ?? latestTaskId ?? tasks[0]?.task_id; // 2026-08-30 小欧 diff⑤: 显式最新锚点防 ASC 回归
        // 2026-08-27 小欧 三堂会审: 空值守卫
        if (!anchorTaskId) {
          prevReceivingRef.current = isReceiving;
          return;
        }
        tokenUsageApi
          .getChainTokens({ sessionId, taskId: anchorTaskId })
          .then((r) =>
            setChainTokens(
              r.chain_accumulated_tokens?.total_tokens ?? r.total_tokens
            )
          )
          .catch(() => undefined);
      }
    }
    prevReceivingRef.current = isReceiving;
  }, [isReceiving, refreshTasks, sessionId, tasks]);

  return { chainTokens };
}
