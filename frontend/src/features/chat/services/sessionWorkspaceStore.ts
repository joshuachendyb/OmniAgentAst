/**
 * sessionWorkspaceStore — 会话事务空间（会话使用目录）的前端单一真源 + 唯一提交出口
 *
 * 创建: 2026-10-30 18:36:36 小欧
 *
 * 【为什么要有这个 store —— 三条路彻底分开】
 *   A 编辑器 SessionWorkspacePanel：只管"编辑意图"。点「确定」= 本地立即关闭，
 *     把列表交给本 store 提交，**自己绝不持有网络、绝不等待往返**。
 *   B 提交器 workspaceStore.commit：唯一写口。脱离组件生命周期跑完 PATCH 并裁决结果
 *     （成功=权威列表落位；422=整单拒绝，逐条点名 + 留痕；其他=全局错误通道 + 失败对账）。
 *   C 渲染 ChatInput 徽标：subscribe 本 store，只取数量。
 *
 * 【原来错在哪（对应线上现象）】
 *   ① 关闭被网络绑定：原 confirm() `await patchWorkspaces()` 成功才 onClose()。
 *      一次请求排队 / 后端被在跑任务占满，弹窗就一直转圈不消失；axios 默认 60s 超时后
 *      还停在原地 → 用户看到的就是"弹窗迟迟不消失，甚至一直不消失"。
 *      界面的进度绝不能由一次网络往返决定。
 *   ② 目录数据挂在 useChatPanels 那个 50+ 依赖的巨型面板 memo 上（只为算一个徽标数字），
 *      一次保存就把 7 条面板 entry（含 RightViewer 全量管道）全部重新 render，
 *      偏偏这一刻正是流式出帧最密的时候。目录是低频元数据，不该寄生在高频渲染链上。
 *   ③ 被拒留痕原本存在弹框组件内部，弹框一关就没了 —— 而现在提交与关闭解耦，
 *      留痕必须能跨关闭存活到下一次打开（notice 字段）。
 *
 * 【写入者只有三处，全部收敛在本文件】
 *   loadSession(sessionId) 切会话取数 / commit() 保存结果与失败对账 / 无会话时 loadSession('') 清场
 * 读取者：ChatInput 徽标（数量）、SessionWorkspacePanel（notice 留痕）。
 *
 * @author 小欧
 * @date 2026-10-30
 */
import { sessionApi } from '@/services/api/session.api';
import { handleError, showMessage, ErrorType } from '@/services/error/handler';
import type { WorkspaceEntry } from '@/types/chat';

/** 被整单拒绝的条目（后端 422 的 workspace_rejected 逐条原因） */
export interface WorkspaceRejection {
  path: string;
  reason: string;
}

interface WorkspaceState {
  /** 当前所属会话；异步结果回来时与它比对，不同即丢弃（切会话竞态） */
  sessionId: string;
  list: WorkspaceEntry[];
  /** 上次保存被拒的条目：提交与关闭解耦后留痕必须活在组件之外，下次打开面板回看 */
  notice: WorkspaceRejection[];
}

const EMPTY: WorkspaceState = { sessionId: '', list: [], notice: [] };

let state: WorkspaceState = EMPTY;
const listeners = new Set<() => void>();

/** 取数代际：切会话/重复触发时只认最后一次，旧代结果一律丢弃 */
let loadSeq = 0;
/** 提交代际：并发提交只认最后一次，避免旧结果覆盖新列表 */
let commitSeq = 0;

const setState = (next: WorkspaceState) => {
  state = next;
  listeners.forEach((l) => l());
};

/** 取当前快照：同一状态期内引用稳定（useSyncExternalStore 的硬要求） */
const getSnapshot = (): WorkspaceState => state;

const subscribe = (listener: () => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

/** 422 信封：后端 detail 经全局异常处理器包装成 error.workspace_rejected */
const rejectionsOf = (e: unknown): WorkspaceRejection[] => {
  const raw = (
    e as {
      response?: { data?: { error?: { workspace_rejected?: unknown } } };
    }
  )?.response?.data?.error?.workspace_rejected;
  return Array.isArray(raw) ? (raw as WorkspaceRejection[]) : [];
};

/** 失败对账：把徽标拉回库里的真值。
 *  为什么必须对账而不是"失败就当没发生"：超时/连接中断时后端可能已经写成功，
 *  前端无从分辨，只能以库为准（唯一权威），否则徽标会与真实配置长期分叉。 */
const reconcile = async (sessionId: string) => {
  try {
    const r = await sessionApi.getWorkspaces(sessionId);
    if (state.sessionId !== sessionId) return;
    setState({ ...state, list: r.workspaces });
  } catch {
    // 对账本身失败：保持旧值即可，不做二次提示（用户刚看过主错误）
  }
};

/** 切会话取数：无会话=清场；有会话=向库真源拉一次 */
const loadSession = async (sessionId: string): Promise<void> => {
  const seq = ++loadSeq;
  if (!sessionId) {
    setState(EMPTY);
    return;
  }
  if (state.sessionId !== sessionId) {
    // 切会话立即换主，避免旧会话的目录数字挂在新区徽标上
    setState({ sessionId, list: [], notice: [] });
  }
  try {
    const r = await sessionApi.getWorkspaces(sessionId);
    if (seq !== loadSeq || state.sessionId !== sessionId) return;
    setState({ ...state, list: r.workspaces });
  } catch {
    if (seq !== loadSeq || state.sessionId !== sessionId) return;
    setState({ ...state, list: [] }); // 会话本身照常可用，目录未知即空
  }
};

/** 保存提交：**不再有返回值可等** —— 调用方（编辑器）点完就关，结果走 store 与 toast。
 *  成功：以请求列表为权威落位（后端 422 是整单拒绝，200 即库中全部有效行）；
 *  422：逐条点名 + 留痕入 store + 对账；
 *  其他：全局错误通道 + 对账。 */
const commit = async (sessionId: string, paths: string[]): Promise<void> => {
  const seq = ++commitSeq;
  try {
    await sessionApi.patchWorkspaces(sessionId, paths);
    if (seq !== commitSeq || state.sessionId !== sessionId) return;
    setState({
      sessionId,
      list: paths.map((p) => ({ path: p })),
      notice: [],
    });
  } catch (e: unknown) {
    if (seq !== commitSeq) return;
    const items = rejectionsOf(e);
    if (items.length) {
      if (state.sessionId === sessionId) {
        setState({ ...state, notice: items });
      }
      // 统一错误通道：走 showMessage（查表+去重+分级），禁自造 notify/裸调 message
      items.forEach((x) =>
        showMessage(ErrorType.WORKSPACE_REJECTED, `${x.path}：${x.reason}`)
      );
    } else {
      handleError(e);
    }
    await reconcile(sessionId);
  }
};

export const workspaceStore = {
  subscribe,
  getSnapshot,
  loadSession,
  commit,
};
