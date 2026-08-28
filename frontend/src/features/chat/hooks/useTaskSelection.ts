// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离任务选择与详情逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useCallback, useEffect, useState } from 'react';
import { executionApi } from '../../../services/api/task.api';
import type { TaskDetail } from '../../../services/api/task.api';

interface UseTaskSelectionOptions {
  sessionId: string | null;
  serverTaskId: string | null;
  isReceiving: boolean;
  tasks: { task_id: string }[];
}

/**
 * 任务选择 hook：切换会话重置跨会话泄漏状态、点击历史任务拉取详情、新会话首个任务自动激活
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useTaskSelection(opts: UseTaskSelectionOptions) {
  const { sessionId, serverTaskId, isReceiving, tasks } = opts;
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<TaskDetail | null>(null);

  // 【小欧 2026-08-27 修复#42】切换会话时重置跨会话泄漏状态, 避免RightViewer向旧会话任务发REST/残留统计
  useEffect(() => {
    setActiveTaskId(null);
    setSelectedDetail(null);
  }, [sessionId]);

  // 【小欧 2026-08-26 修复 A3】任务信息条随左列点击切换：选中历史任务时拉取其详情，
  // 注入 TaskInfoBar 作为动态信息来源(7.6 目标"当前任务=点击查看的历史任务")
  useEffect(() => {
    if (activeTaskId && activeTaskId !== serverTaskId) {
      // 2026-08-27 小欧 修复#43: 增加cancelled守卫, 避免快速连点任务时旧响应覆盖新数据
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

  // 【小欧 2026-08-27 修复#6】新会话首个任务自动激活: serverTaskId 就绪但 activeTaskId 尚空时跟随,
  // 避免右侧执行详情/任务信息条不随首个实时任务联动(历史点击手动选择时不覆盖)
  // 2026-08-28 小欧 v1.3: 纯历史会话(serverTaskId为空)加载后默认选中列表首项, 任务信息框显第一个任务(用户三态需求②)
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
