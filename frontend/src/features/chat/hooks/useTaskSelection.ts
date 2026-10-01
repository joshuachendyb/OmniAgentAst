// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离任务选择与详情逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 设计文档 v1.103: 拆两effect修锚定问题(①serverTaskId变化强制锚定当前任务, 去activeTaskId门闩; ②纯历史会话默认选中latestTaskId, ASC后tasks[0]≈最旧失效); 签名插入latestTaskId
// 编辑历史: 2026-09-13 小欧 - 新建会话右栏残留根治(北京老陈三思三省定位): 会话切换重置由useEffect滞后执行改渲染期复位
//   (React官方"prop变化时调整state"范式)——子组件RightViewer的effect先于父级本hook的effect执行, 原滞后重置致切换首帧
//   旧activeTaskId存活, 触发RightViewer历史REST effect跨会话拉旧任务步骤回填historySteps→右栏残留旧执行记录;
//   渲染期同步复位后子组件首帧即见null, 封死陈旧拉取窗口 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 根治2(北京老陈复测: 展开/折叠仍显旧信息): effect②纯历史默认选中最新任务在切会话当帧
//   仍持旧tasks/latestTaskId, 会setActiveTaskId(旧latest)→右栏跨会话拉旧步骤残留"复活"; 渲染期复位置justSwitchedRef,
//   effect②首跑消费该标记跳过旧数据自动选中窗口 — 小欧-2026-09-13
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计[76] 5.4④/6.14 实施回填): 加 task_merged 事件监听,
//   注入应答时高亮左侧目标任务(activeTaskId 属主在本 hook) — 小欧-2026-09-28
// 编辑历史: 2026-10-01 小欧 - [1] B1 双写竞态根治: effect①(锚 serverTaskId)与 effect②(兜底 latestTaskId)
//   在同一次提交内互不知情 —— ②的 if(activeTaskId) return 读的是本次渲染旧值, 看不到①的 pending
//   更新, 故两者都能通过守卫, 最终 activeTaskId=latestTaskId 而 serverTaskId 为 null/陈旧, 右栏
//   因此把「正在执行的任务」当「历史任务」处理(本次缺陷直接成因)。修: effect② 显式让位, 两者互斥。
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

  // 2026-09-30 小欧 - 单一真源(解 [1] B1 双写竞态): 原 effect① 无条件 setActiveTaskId(serverTaskId)
  //   与 effect② 的 "if (activeTaskId) return" 守卫互不知情 —— ②读的是本次渲染的旧值, 看不到①的
  //   pending 更新, 故同一次提交里两者都能通过守卫, 最终值取决于 React 批处理顺序, 产生
  //   "activeTaskId 正确(=latestTaskId) 而 serverTaskId 陈旧/为 null" 的自相矛盾组合
  //   (本次缺陷的直接成因)。现由②显式让位给①: 有当前任务锚点时②不再兜底, 两 effect 互斥。
  useEffect(() => {
    if (serverTaskId) setActiveTaskId(serverTaskId);
  }, [serverTaskId]);

  // 2026-09-30 小欧 - 纯历史会话默认选中最新任务(原 effect②)。serverTaskId 非空即让位给上面锚点,
  //   保证"有在飞/最近任务必锚当前、无则锚最新", 不再两个 effect 争同一状态。
  useEffect(() => {
    if (justSwitchedRef.current) {
      justSwitchedRef.current = false;
      return;
    }
    if (serverTaskId) return; // ★单一真源: 当前任务锚点优先, 本 effect 不参与(解 B1)
    if (activeTaskId) return;
    if (tasks.length === 0) return;
    if (!isReceiving && latestTaskId) {
      setActiveTaskId(latestTaskId);
    }
  }, [serverTaskId, latestTaskId, activeTaskId, isReceiving, tasks]);

  const handleSelectTask = useCallback((id: string) => {
    setActiveTaskId(id);
  }, []);

  // 2026-09-28 小欧: 注入应答高亮左侧目标任务(设计[76] 5.4④) — activeTaskId 是左栏高亮唯一真源,
  //   其属主是本 hook, 故在此消费 useChatCallbacks 发来的 task_merged 事件(与 authorization_resumed
  //   同款 window 事件桥, 复用既有跨层通道); taskId 为空(后端未带)时不改选中态, 不猜 — 小欧-2026-09-28
  useEffect(() => {
    const onTaskMerged = (e: Event) => {
      const taskId = (e as CustomEvent<{ taskId: string | null }>).detail
        ?.taskId;
      if (taskId) handleSelectTask(taskId);
    };
    window.addEventListener('task_merged', onTaskMerged);
    return () => window.removeEventListener('task_merged', onTaskMerged);
  }, [handleSelectTask]);

  return { activeTaskId, selectedDetail, handleSelectTask };
}
