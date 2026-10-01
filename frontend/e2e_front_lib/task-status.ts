/**
 * 后端任务状态读取(DB 权威) —— 小欧 2026-10-01
 *
 * 【为什么抽到 lib】
 *   fre2e_15 / 16 / 17 三个 case 都要读 `chat_tasks.status` 来判"任务还在不在跑"。
 *   原先各抄一份, 且 **15 那份用的是 latest_task_id 语义(取会话里"最新的那个任务")**,
 *   16/17 那份是按 task_id 精确查。同一个项目里两种语义并存, 是假通过的温床:
 *   一旦系统挑错了任务(正是 17 要抓的 bug), 用 latest 的 helper 会跟着挑错,
 *   断言跟着一起绿 —— 恰好把要抓的缺陷放过去。
 *   故统一收进公用库, **只有"按 task_id 精确查"一种语义**, 15 那份 latest 版就此废掉。
 *
 * 【权威来源】
 *   后端 `GET /sessions/{session_id}/tasks` 返回的 `tasks[].status`, 即
 *   `chat_tasks.status` 字段本身(经原生 fetch 读, 不直连 sqlite, 避免绕过后端封装)。
 *   对应后端 storage.py `list_session_tasks`(按 id ASC)。
 */

/** 全部 E2E 共用的后端 API 根(仅本模块需要 HTTP 直读时用) */
export const API_BASE = 'http://127.0.0.1:8000/api/v1';

/** 任务不在列表 / 会话为空 —— 交调用方显式判红, 不静默回落成"最新任务" */
export const STATUS_NOT_FOUND = '__not_found__';

/** 参数无效(sessionId 或 taskId 为空) */
export const STATUS_INVALID_INPUT = '__invalid_input__';

/**
 * 读**指定 task_id** 的权威 status。
 *
 * 找不到 → 返回 `__not_found__`(或 `__http_<码>`), **绝不**回落到"最新任务" ——
 * 回落就等于把"挑错任务"这件事藏起来, 断言会跟着一起错。
 */
export const statusOfTask = async (
  sessionId: string,
  taskId: string
): Promise<string> => {
  if (!sessionId || !taskId) return STATUS_INVALID_INPUT;
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return `__http_${res.status}`;
  const d = (await res.json()) as {
    tasks?: { task_id: string; status: string }[];
  };
  const hit = (d.tasks ?? []).find((t) => t.task_id === taskId);
  return hit?.status ?? STATUS_NOT_FOUND;
};

/**
 * 轮询直到该 task 离开 `executing`(或超时), 返回**最后一次实测值** —— 不猜、不伪造。
 *
 * 用途: 判"任务最终跑完没有"。只读 REST status, 不替代 SSE 层判据
 * (续传/帧连续性另由 stream-diag 判), 也不用于掩盖流没推的情况。
 */
export const pollTaskStatus = async (
  sessionId: string,
  taskId: string,
  timeoutMs: number
): Promise<string> => {
  const deadline = Date.now() + timeoutMs;
  let s = await statusOfTask(sessionId, taskId);
  while (Date.now() < deadline && s === 'executing') {
    await new Promise((r) => setTimeout(r, 1000));
    s = await statusOfTask(sessionId, taskId);
  }
  return s;
};

/**
 * 该会话的**全部** task_id(后端权威, 按 id ASC)。
 *
 * 与 page-anchors 的 `allTaskIdsInList`(UI 左侧列表, 可能截断)是两个不同用途:
 * 本函数走 REST, 是"这个会话到底有哪些任务"的权威答案, 可用于硬断言。
 */
export const allTaskIdsOfApi = async (sessionId: string): Promise<string[]> => {
  if (!sessionId) return [];
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return [];
  const d = (await res.json()) as { tasks?: { task_id: string }[] };
  return (d.tasks ?? []).map((t) => t.task_id);
};

/**
 * 按 **task_id 反查 session_id**(DB 权威) —— 小欧 2026-10-01
 *
 * 【为什么必须走这个, 不能靠标题反查】
 *   fre2e_15 原用「取 title 含 PROMPT 片段的第一个会话」反查 session_id, 其注释断言
 *   "不会串到别的会话" —— **已被实测证伪**: 反复跑 case 会在库里堆出 20+ 个同名会话,
 *   `find` 取第一个必然命中**旧**会话, 于是 `statusOfTask(旧session, 新task)` → `__not_found__`。
 *   本函数按 `GET /chat/execution/task/{task_id}` → `task.session_id` 取, task_id 唯一,
 *   **结构上不存在串台可能**。
 *
 * 取不到(含 404 / 字段缺失) → 返回空串, 交调用方显式判红, **不返回任何猜测值**。
 */
export const sessionIdOfTask = async (taskId: string): Promise<string> => {
  if (!taskId) return '';
  const res = await fetch(`${API_BASE}/chat/execution/task/${taskId}`);
  if (!res.ok) return '';
  const d = (await res.json()) as { task?: { session_id?: string } };
  return d.task?.session_id ?? '';
};

/**
 * 该任务的"已运行时长"(ms), 取 `chat_tasks.created_at` 算 —— 小欧 2026-10-01
 *
 * 【为什么需要】
 *   前端 `findLiveTask` 有一条 300s 活跃窗口(按 created_at 过滤), 所以 E2E 必须
 *   自己掌握"任务现在多大了": 若关页面重开时任务已超窗, 恢复失败是**预期行为**而非缺陷,
 *   此时判红是假红。调用方据此在窗口耗尽前收尾, 并把边界情况显式报错而非静默通过。
 *
 * 读不到/格式异常 → 返回 -1, 交调用方显式判红, 不返回 0 假装"刚刚创建"。
 */
export const taskAgeMsOf = async (
  sessionId: string,
  taskId: string
): Promise<number> => {
  if (!sessionId || !taskId) return -1;
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/tasks`);
  if (!res.ok) return -1;
  const d = (await res.json()) as {
    tasks?: { task_id: string; created_at?: string }[];
  };
  const created = (d.tasks ?? []).find((t) => t.task_id === taskId)?.created_at;
  if (!created) return -1;
  const born = Date.parse(created);
  if (Number.isNaN(born)) return -1;
  return Date.now() - born;
};

/**
 * 任务失败(cancelled 同理)时, 从后端当日日志里捞该 task 的 ERROR 行作证据。
 * 铁规: 失败就是问题, 必须把根因线索打出来, 不当正常收尾放过。
 */
export const errorLinesOfTask = (
  logText: string,
  taskId: string,
  limit = 25
): string[] =>
  logText
    .split('\n')
    .filter(
      (l) =>
        l.includes(taskId) && /ERROR|失败|error|Traceback|Exception/i.test(l)
    )
    .slice(-limit);
