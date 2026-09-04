// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离任务选择与详情逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.9 v1.103: 拆两effect修G2/G3(①serverTaskId变化强制锚定当前任务, 去activeTaskId门闩; ②纯历史会话默认选中latestTaskId, ASC后tasks[0]≈最旧失效); 签名插入latestTaskId
import { useCallback, useEffect, useState } from 'react';
import { executionApi } from '../../../services/api/task.api';
import type { TaskDetail } from '../../../services/api/task.api';

/**
 * 任务选择 hook：切换会话重置跨会话泄漏状态、点击历史任务拉取详情、新会话首个任务自动激活
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useTaskSelection(
  sessionId: string | null,
  serverTaskId: string | null,
  isReceiving: boolean,
  latestTaskId: string | null, // 2026-08-30 小欧 diff⑥ v1.103: 最新任务显式锚点
  tasks: { task_id: string }[]
) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<TaskDetail | null>(null);

  // 2026-08-27 小欧 修复#42: 切换会话时重置跨会话泄漏状态
  useEffect(() => {
    setActiveTaskId(null);
    setSelectedDetail(null);
  }, [sessionId]);

  // 2026-08-26 修复 A3: 任务信息条随左列点击切换拉取详情
  useEffect(() => {
    if (activeTaskId && activeTaskId !== serverTaskId) {
      let cancelled = false;
      executionApi
        .getTaskDetail(activeTaskId)
        .then((d) => {
          if (!cancelled) setSelectedDetail(d);
        })
        .catch(() => {
          if (!cancelled) setSelectedDetail(null);
        });
      return () => {
        cancelled = true;
      };
    } else {
      setSelectedDetail(null);
    }
  }, [activeTaskId, serverTaskId]);

  // 2026-08-30 小欧 diff⑥ effect①: serverTaskId 变化即锚定当前任务(G3修复, 4.5.1 有正在执行任务=当前任务; 用户点历史不改serverTaskId不受影响)
  useEffect(() => {
    if (serverTaskId) {
      setActiveTaskId(serverTaskId);
    }
  }, [serverTaskId]);

  // 2026-08-30 小欧 diff⑥ effect②: 纯历史会话默认选中最新任务(ASC后tasks[0]≈最旧, 改显式latestTaskId)
  useEffect(() => {
    if (activeTaskId) return;
    if (tasks.length === 0) return;
    if (!isReceiving && latestTaskId) {
      setActiveTaskId(latestTaskId);
    }
  }, [latestTaskId, activeTaskId, isReceiving, tasks]);

  const handleSelectTask = useCallback((id: string) => {
    setActiveTaskId(id);
  }, []);

  return { activeTaskId, selectedDetail, handleSelectTask };
}
