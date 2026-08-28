// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离任务选择与详情逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
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

  // 2026-08-27 修复#6 + 2026-08-28 v1.3: 新会话首个任务自动激活/纯历史会话默认选中首项
  useEffect(() => {
    if (activeTaskId) return;
    if (serverTaskId) {
      setActiveTaskId(serverTaskId);
      return;
    }
    if (!isReceiving && tasks.length > 0) {
      setActiveTaskId(tasks[0].task_id);
    }
  }, [serverTaskId, activeTaskId, isReceiving, tasks]);

  const handleSelectTask = useCallback((id: string) => {
    setActiveTaskId(id);
  }, []);

  return { activeTaskId, selectedDetail, handleSelectTask };
}
