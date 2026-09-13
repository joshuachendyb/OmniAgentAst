// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离任务选择与详情逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.9 v1.103: 拆两effect修G2/G3(①serverTaskId变化强制锚定当前任务, 去activeTaskId门闩; ②纯历史会话默认选中latestTaskId, ASC后tasks[0]≈最旧失效); 签名插入latestTaskId
// 编辑历史: 2026-09-13 小欧 - 新建会话右栏残留根治(北京老陈三思三省定位): 会话切换重置由useEffect滞后执行改渲染期复位
//   (React官方"prop变化时调整state"范式)——子组件RightViewer的effect先于父级本hook的effect执行, 原滞后重置致切换首帧
//   旧activeTaskId存活, 触发RightViewer历史REST effect跨会话拉旧任务步骤回填historySteps→右栏残留旧执行记录;
//   渲染期同步复位后子组件首帧即见null, 封死陈旧拉取窗口 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 根治2(北京老陈复测: 展开/折叠仍显旧信息): effect②纯历史默认选中最新任务在切会话当帧
//   仍持旧tasks/latestTaskId, 会setActiveTaskId(旧latest)→右栏跨会话拉旧步骤残留"复活"; 渲染期复位置justSwitchedRef,
//   effect②首跑消费该标记跳过旧数据自动选中窗口 — 小欧-2026-09-13
import { useCallback, useEffect, useRef, useState } from 'react';
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
  // 2026-09-13 小欧 根治(北京老陈三思三省定位): useEffect滞后重置改渲染期复位(React官方"prop变化调state"范式,
  //   prevSessionId 哨兵)——子组件(RightViewer)effect先于父级执行, 原滞后重置致切换首帧旧activeTaskId存活,
  //   触发RightViewer历史REST跨会话拉旧任务步骤回填, 右栏残留旧执行记录; 渲染期复位后子组件首帧即见null — 小欧-2026-09-13
  const [prevSessionId, setPrevSessionId] = useState<string | null>(sessionId);
  // 2026-09-13 小欧 新建会话右栏残留根治(复测定位·北京老陈): effect②(纯历史默认选中最新)切会话当帧仍持旧tasks/
  //   latestTaskId, 把activeTaskId拉回旧任务→RightViewer跨会话拉旧步骤, 右栏残留"复活"(展开折叠仍显旧信息);
  //   本ref标记"会话已切换", effect②消费后即跳过旧数据自动选中窗口 — 小欧-2026-09-13
  const justSwitchedRef = useRef(false);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setActiveTaskId(null);
    setSelectedDetail(null);
    justSwitchedRef.current = true;
  }

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
  // 2026-09-13 小欧 根治2(北京老陈复测驱动): 切会话当帧渲染期复位已置justSwitchedRef, 本effect首跑仍见旧会话
  //   tasks/latestTaskId, 若直接选中会把activeTaskId拉回旧任务→右栏跨会话拉旧步骤残留复活;
  //   先消费justSwitchedRef跳过该旧数据自动选中窗口, 新会话数据到齐(next tasks/latestTaskId更新触发)后再正常选中 — 小欧-2026-09-13
  useEffect(() => {
    if (justSwitchedRef.current) {
      justSwitchedRef.current = false;
      return;
    }
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
