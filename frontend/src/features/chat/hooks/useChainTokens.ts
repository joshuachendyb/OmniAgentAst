// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离链累计token逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.8 v1.103: 结束沿锚点加 latestTaskId 兜底(排序一义后 tasks[0]≈最旧, 原 DESC 首行=最新语义失效, 改显式最新锚点防 ASC 回归取错任务)
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): 返回 { sessionTokens, chainTokens } 两组3字段结构, 前面会话累计(session)后面链累计(chain); 取数字段由 r.total_tokens 改为对应层 3 字段
// 编辑历史: 2026-09-01 小欧 - 实时/静态双源合并(北京老陈"三思三省"): 运行中读 SSE metaFrames 实时值(每轮LLM调用推), 静止/历史/重进读 DB 拉取值; 实时优先覆盖静态
import { useEffect, useRef, useState } from 'react';
import { tokenUsageApi } from '../../../services/api/task.api';
import type { TaskMetaFrames } from '../../../types/sse';

// 2026-09-01 小欧: token 3 字段口径（后端 ChainTokenLayer {prompt_tokens,completion_tokens,total_tokens}）
interface TokenTriple {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/**
 * 顶栏 token hook：实时/静态双源合并（北京老陈 2026-09-01 三思三省定案）
 * - 运行中(isReceiving)：读 SSE metaFrames.sessionAccumulated/chainAccumulated 实时帧（每轮 LLM 调用后端下发, 见 react_cycle usage 帧）
 * - 静止/历史/重进会话：阅读加载补拉 + 任务结束沿拉取 的 DB 落库值
 * - 优先级：实时 metaFrames > 静态拉取。返回 { sessionTokens, chainTokens } 两组 3 字段。
 */

export function useChainTokens(
  sessionId: string | null,
  serverTaskId: string | null,
  isReceiving: boolean,
  latestTaskId: string | null, // 2026-08-30 小欧 diff⑤ v1.103: 最新任务显式锚点
  tasks: { task_id: string }[],
  refreshTasks: () => void,
  metaFrames: TaskMetaFrames // 2026-09-01 小欧: SSE 实时 token 帧源
) {
  const [sessionTokens, setSessionTokens] = useState<TokenTriple | null>(null); // 2026-09-01 小欧: 会话累计 token
  const [chainTokens, setChainTokens] = useState<TokenTriple | null>(null); // 2026-09-01 小欧: 链累计 token(原 number 改 3字段)
  // 2026-09-01 小欧 修复: 会话切重置锚点去重标记（随 token 一同复位，防残留跨会话 key）
  const fetchedAnchorRef = useRef<string | null>(null);

  // 2026-09-01 小欧 实时源: 运行中 SSE usage 帧有值 → 实时覆盖顶栏(会话/链累计每轮随 LLM 调用跳动)
  useEffect(() => {
    if (metaFrames.sessionAccumulated)
      setSessionTokens(metaFrames.sessionAccumulated);
    if (metaFrames.chainAccumulated)
      setChainTokens(metaFrames.chainAccumulated);
  }, [metaFrames.sessionAccumulated, metaFrames.chainAccumulated]);

  // 2026-08-27 修复#42: 切换会话时重置跨会话泄漏状态
  useEffect(() => {
    setSessionTokens(null); // 2026-09-01 小欧: 会话累计同步复位
    setChainTokens(null);
    fetchedAnchorRef.current = null; // 2026-09-01 小欧: 同步复位去重标记
  }, [sessionId]);

  // 2026-09-01 小欧 修复: 顶部累计token历史/重进会话恒为'-'根因——原仅任务结束沿拉取一次, 会话加载不拉。
  //   补一段: 会话切+任务就绪+非接收中 → 主动拉取一次(anchorRef去重防重复), 与任务结束沿并存不退化。
  useEffect(() => {
    const anchorTaskId = serverTaskId ?? latestTaskId ?? tasks[0]?.task_id;
    if (!sessionId || !anchorTaskId || isReceiving) return;
    const key = `${sessionId}|${anchorTaskId}`;
    if (fetchedAnchorRef.current === key) return;
    fetchedAnchorRef.current = key;
    tokenUsageApi
      .getChainTokens({ sessionId, taskId: anchorTaskId })
      .then((r) => {
        // 2026-09-01 小欧: 会话累计在前, 链累计在后(北京老陈定案), 均为3字段; 无值时置null
        setSessionTokens(r.session_accumulated_tokens ?? null);
        setChainTokens(r.chain_accumulated_tokens ?? null);
      })
      .catch(() => undefined);
  }, [sessionId, serverTaskId, latestTaskId, tasks, isReceiving]);

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
          .then((r) => {
            // 2026-09-01 小欧: 会话累计在前, 链累计在后(北京老陈定案), 均为3字段; 无值时置null
            setSessionTokens(r.session_accumulated_tokens ?? null);
            setChainTokens(r.chain_accumulated_tokens ?? null);
          })
          .catch(() => undefined);
      }
    }
    prevReceivingRef.current = isReceiving;
  }, [isReceiving, refreshTasks, sessionId, tasks]);

  return { sessionTokens, chainTokens };
}
