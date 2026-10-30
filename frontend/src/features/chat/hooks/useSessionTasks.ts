// 编辑历史: 2026-08-26 小欧 - 8.1/8.2 实施: 会话任务清单Hook, 顶栏任务数/左列共用, final/error后refresh(6.1.9 B1)
// 编辑历史: 2026-08-30 小欧 - 设计文档 v1.103: 新增 latestTaskId(最新任务锚点透传, 顶栏/默认选中/链token锚点消费, 排序一义后不用 tasks[0])
// 编辑历史: 2026-09-11 小欧 - 即时写入final.response修复: 新增updateTaskResponse方法(SSE final帧到达时即时更新task response, 不等DB refresh), 返回值补updateTaskResponse — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - X2终态短信号(北京老陈铁命令): 左侧任务 response 只允许由 updateTaskResponse(final.response) 写入, 严禁任何其他数据源/兜底顶替 — 小欧-2026-09-12
// 编辑历史: 2026-09-13 小欧 - 新建会话右栏残留根治(北京老陈复测定位, 首修被effect②覆盖): refresh为异步, 切会话瞬间
//   旧会话tasks/latestTaskId仍存活, useTaskSelection effect②(纯历史默认选中最新)持旧latestTaskId把activeTaskId拉回旧任务,
//   RightViewer跨会话拉旧步骤→右栏残留"复活"; 根治点: sessionId一变立即同步清空任务清单/锚点, 封死旧数据窗口 — 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
//   refresh() 从 DB 拉取 tasks 后 response 字段一律清空(undefined), 禁止 chat_tasks.response(chunk累积)显示;
//   左侧只由 updateTaskResponse(final.step.response) 写入(R3实时/RightViewer历史) — 小欧-2026-09-15
// 编辑历史: 2026-09-29 小欧 - 任务列表陈旧根治: 补 visibilitychange 兜底(切回可见即 refresh), 修任务由别处发起时列表永久冻结在旧快照 — 小欧-2026-09-29
// 编辑历史: 2026-10-28 小欧 - 左侧终态回复消失根治: refresh() 原无条件清空 response, 而任务结束沿
//   onSuccess(10-28 新增) + useChainTokens 的 final_stats 信号两次触发 refresh 均在 updateTaskResponse 之后
//   → 刚写入的 final.response 被抹掉; 改按 taskId 保留已写入值(finalResponsesRef), DB 内容仍不显示 — 小欧-2026-10-28
// 编辑历史: 2026-10-28 小欧 - completed 任务左栏仍无回复区(北京老陈报障)的第二处根因: 后端 X2 终态短信号
//   把 final 裁成五键, response 随之剥离(实测 final.response 长度 0), 而写入唯一入口只认 final.response
//   → 实时任务无正文可写。补一路同源兜底: 本会话当前任务终态时取它在 SSE 里流过来的正文 chunk(排除推理),
//   写进 updateTaskResponse 的缓存/state——与 useChatCallbacks 既有「finalResponse || streamingContentRef」
//   同一口径; 数据源是内存实时流, 不读 DB, DB 的 chat_tasks.response 依旧永不显示 — 小欧-2026-10-28
// 编辑历史: 2026-10-30 小欧 - refresh 的 listTasks 已置静默(后台轮询不弹全局 toast), 故本处补 catch 收口:
//   原实现只有 finally, 失败冒成 unhandledrejection(调用方全是 void refresh()/事件回调, 无人接 reject);
//   现只 console.warn 并保留上一次列表, 下次触发自然自愈 — 小欧-2026-10-30
/**
 * useSessionTasks - 会话任务清单 Hook（消费 6.1.9 B1 接口）
 *
 * 【小欧 2026-08-26 8.1/8.2】顶栏任务数与左侧任务列表共用同一份数据；
 * 每任务结束后由调用方触发 refresh()（SSE final/error 后调用）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  sessionTaskApi,
  type SessionTaskItem,
} from '../../../services/api/task.api';
import { chatStreamStore, isTerminalStatus } from '../streams/chatStreamStore';

// 2026-10-28 小欧 - 实时终态正文兜底取值(见文件头编辑历史第 2 条):
//   只认"本会话当前任务 + 已终态"这一条, 取 SSE 流过来的正文 chunk 拼接(排除 is_reasoning 思考分块,
//   思考内容不属于回复正文)。取不到返回 undefined, 保持原行为(该任务无回复区)。
const liveTaskAnswer = (
  live: ReturnType<typeof chatStreamStore.getSnapshot>,
  task: SessionTaskItem
): string | undefined => {
  if (task.task_id !== live.serverTaskId) return undefined;
  if (!isTerminalStatus(task.status)) return undefined;
  const text = live.executionSteps
    .filter((s) => s.type === 'chunk' && !s.is_reasoning)
    .map((s) => s.content ?? '')
    .join('');
  return text.trim() ? text : undefined;
};

export const useSessionTasks = (sessionId: string | null) => {
  const [tasks, setTasks] = useState<SessionTaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [latestTaskId, setLatestTaskId] = useState<string | null>(null); // 2026-08-30 小欧 v1.103: B1 最新任务锚点
  const [loading, setLoading] = useState(false);

  // 2026-10-28 小欧 - 修复左侧终态回复被 refresh() 抹掉: 原 refresh 无条件把 response 置 undefined,
  //   而任务结束沿至少两次调用 refresh(onSuccess 兜底 + useChainTokens 的 final_stats 信号), 都在
  //   updateTaskResponse(final.response) 之后 → 刚写入的正文立刻被清空(实测左栏无回复区)。
  //   改为按 taskId 保留已由 final.response 写入的值: DB 的 chat_tasks.response 仍一律不显示(铁命令不变),
  //   只是不再丢弃内存里已有的终态正文 — 小欧-2026-10-28
  const finalResponsesRef = useRef<Map<string, string>>(new Map());

  // 铁命令(北京老陈 2026-09-12): refresh 从 DB 拉任务列表(入列/链token/历史加载);
  //   但 response 字段一律清空——左侧只用 final.step.response 显示, 禁止 chat_tasks.response 显示。 — 小欧-2026-09-15
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
      // 2026-09-15 小欧(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
      //   refresh() 从 DB 拉取的 chat_tasks.response(chunk累积内容) 不允许显示在左侧;
      //   2026-10-28 小欧 - 保留已由 updateTaskResponse(final.response) 写入的值(原写法会把它们一并清空,
      //   导致终态回复在 onSuccess/final_stats 两次 refresh 后消失); DB 内容仍不进 response — 小欧-2026-10-28
      //   2026-10-28 小欧 - 再加实时流兜底: final.response 为空(后端短条)时取本会话当前任务的实时正文,
      //   取到即写进同一份缓存, 后续 refresh 与 updateTaskResponse 写入值同等保留 — 小欧-2026-10-28
      const live = chatStreamStore.getSnapshot(sessionId);
      setTasks(
        res.tasks.map((t) => {
          let response = finalResponsesRef.current.get(t.task_id);
          if (response === undefined) {
            response = liveTaskAnswer(live, t);
            if (response !== undefined) {
              finalResponsesRef.current.set(t.task_id, response);
            }
          }
          return { ...t, response };
        })
      );
      setTotal(res.total);
      setLatestTaskId(res.latest_task_id ?? null); // 2026-08-30 小欧 v1.103: 后端 null 兜底
    } catch (e) {
      // 2026-10-30 小欧 - 后台轮询端点已置 _silent(不弹全局 toast),
      //   这里必须收口 —— 原实现只有 finally, 失败会冒成 unhandledrejection(控制台红字),
      //   且调用方全是 void refresh()/事件回调, 没人接这个 reject。列表保持上一次结果, 下次 refresh 自愈。
      console.warn('[useSessionTasks] refresh 失败(保留上次列表):', e);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // 2026-09-13 小欧 新建会话右栏残留根治(北京老陈复测定位·展开折叠仍显旧信息): refresh为异步, 切会话瞬间
  //   旧会话tasks/latestTaskId仍存活, useTaskSelection effect②持旧latestTaskId把activeTaskId拉回旧任务,
  //   RightViewer跨会话拉旧步骤→右栏残留复活; 改"同步清空→再refresh"封死旧数据窗口; refresh依赖[sessionId],
  //   手动refreshTasks调用不重跑本effect, 无扰 — 小欧 2026-09-13
  useEffect(() => {
    setTasks([]);
    setTotal(0);
    setLatestTaskId(null);
    finalResponsesRef.current.clear(); // 2026-10-28 小欧 - 会话切换同步清空终态正文缓存(任务ID不跨会话) — 小欧-2026-10-28
    void refresh();
  }, [refresh]);

  // 2026-09-29 小欧 任务列表陈旧根治: refresh 原本只被本标签页的 SSE 派生信号驱动, 任务由别处发起
  //   (E2E/后台批处理/另一标签页)时收不到任何信号, 列表永久冻结在打开那刻的快照(实测 INJ-02 两条注入
  //   只显示"追加 1 条")。补可见性兜底: 切回可见即重取。 — 小欧-2026-09-29
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        void refresh();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refresh]);

  // ── useSessionTasks 文件职责: 任务列表状态管理Hook ──
  // ── 左侧任务回复区: 本文件负责"怎么写"(提供 updateTaskResponse 和 refresh 方法) ──
  // updateTaskResponse: 唯一写入点——从 SSE/REST steps 中取 final.step.response 写入左侧(实时+历史)
  // refresh: 从 DB 拉任务列表(入列/链token/历史加载), response 只取 finalResponsesRef(=updateTaskResponse 写过的值,
  //   或本会话当前任务终态的实时正文兜底), chat_tasks.response 永不进 response 字段
  //
  // 铁命令(北京老陈 2026-09-12/2026-09-15): 左侧任务 response 只允许由 updateTaskResponse(final.step.response) 写入,
  //   严禁使用 chat_tasks.response(chunk累积内容)/refreshTasks 兜底/任何其他数据源 — 小欧-2026-09-15
  // 2026-10-28 小欧 - completed 的 final 帧已被后端短信号剥掉正文(实测长度 0), 唯一入口拿不到可写内容;
  //   故在本会话当前任务终态时, 用它在 SSE 流过来的正文 chunk 补一次写入(与 useChatCallbacks 的
  //   「finalResponse || streamingContentRef」同口径, 数据源是内存实时流而非 DB) — 小欧-2026-10-28
  const updateTaskResponse = useCallback((taskId: string, response: string) => {
    // 2026-10-28 小欧 - 同时写入缓存, 供后续 refresh() 保留(否则刷新即被清空) — 小欧-2026-10-28
    finalResponsesRef.current.set(taskId, response);
    setTasks((prev) =>
      prev.map((t) => (t.task_id === taskId ? { ...t, response } : t))
    );
  }, []);

  return { tasks, total, loading, refresh, latestTaskId, updateTaskResponse };
};
