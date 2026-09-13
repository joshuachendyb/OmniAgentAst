// 编辑历史: 2026-08-26 小欧 - 8.1/8.2 实施: 会话任务清单Hook, 顶栏任务数/左列共用, final/error后refresh(6.1.9 B1)
// 编辑历史: 2026-08-30 小欧 - 设计文档[2]12.7 v1.103: 新增 latestTaskId(B1 最新任务锚点透传, 顶栏/默认选中/链token锚点消费, 排序一义后不用 tasks[0])
// 编辑历史: 2026-09-11 小欧 - R3修复: 新增updateTaskResponse方法(SSE final帧到达时即时更新task response, 不等DB refresh), 返回值补updateTaskResponse — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - X2终态短信号(北京老陈铁命令): 左侧任务 response 只允许由 updateTaskResponse(final.response) 写入, 严禁任何其他数据源/兜底顶替 — 小欧-2026-09-12
// 编辑历史: 2026-09-13 小欧 - 新建会话右栏残留根治(北京老陈复测定位, 首修被effect②覆盖): refresh为异步, 切会话瞬间
//   旧会话tasks/latestTaskId仍存活, useTaskSelection effect②(纯历史默认选中最新)持旧latestTaskId把activeTaskId拉回旧任务,
//   RightViewer跨会话拉旧步骤→右栏残留"复活"; 根治点: sessionId一变立即同步清空任务清单/锚点, 封死旧数据窗口 — 小欧-2026-09-13
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
  const [latestTaskId, setLatestTaskId] = useState<string | null>(null); // 2026-08-30 小欧 v1.103: B1 最新任务锚点
  const [loading, setLoading] = useState(false);

  // 铁命令(北京老陈 2026-09-12): refresh 从 DB 全量刷新任务列表(含 response), 仅供任务列表入列/链token/历史回放加载;
  //   严禁用作"实时补左侧 response"的兜底——实时左侧 response 唯一写入点是 updateTaskResponse(final.response)。 — 小欧-2026-09-12
  const refresh = useCallback(async () => {
    if (!sessionId) {
      setTasks([]);
      setTotal(0);
      setLatestTaskId(null); // 2026-08-30 小欧 v1.103: 空会话同步清零锚点
      return;
    }
    setLoading(true);
    try {
      const res = await sessionTaskApi.listTasks(sessionId);
      setTasks(res.tasks);
      setTotal(res.total);
      setLatestTaskId(res.latest_task_id ?? null); // 2026-08-30 小欧 v1.103: 后端 null 兜底
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // 2026-09-13 小欧 新建会话右栏残留根治(北京老陈复测定位·展开折叠仍显旧信息): refresh为异步, 切会话瞬间
  //   旧会话tasks/latestTaskId仍存活, useTaskSelection effect②持旧latestTaskId把activeTaskId拉回旧任务,
  //   RightViewer跨会话拉旧步骤→右栏残留复活; 改"同步清空→再refresh"封死旧数据窗口; refresh依赖[sessionId],
  //   手动refreshTasks调用不重跑本effect, 无扰 — 小欧-2026-09-13
  useEffect(() => {
    setTasks([]);
    setTotal(0);
    setLatestTaskId(null);
    void refresh();
  }, [refresh]);

  // 铁命令(北京老陈 2026-09-12): 左侧任务的 response 只允许由本方法写入, 且调用方必须传
  //   SSE final 帧的 final.response——严禁用 DB 查询、消息正文、refreshTasks 全量刷新或其他任何
  //   数据源/兜底来顶替补写左侧 response。历史回放的 response 由 DB 落库的完整长条经 refresh() 加载,
  //   与本方法(实时 final 即时写)互不干扰。 — 小欧-2026-09-12
  const updateTaskResponse = useCallback((taskId: string, response: string) => {
    setTasks((prev) =>
      prev.map((t) => (t.task_id === taskId ? { ...t, response } : t))
    );
  }, []);

  return { tasks, total, loading, refresh, latestTaskId, updateTaskResponse };
};
