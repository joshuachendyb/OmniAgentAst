/**
 * sessionWorkspaceStore — 会话使用目录的前端单一真源 + 唯一提交出口
 *
 * 创建: 2026-10-30 18:36:36 小欧
 * 更新: 2026-11-02 小欧 — 422 草稿可恢复（rejected 快照 + clearRejected）
 *
 * 【三条路】
 *   A 编辑器 SessionWorkspacePanel：只管编辑意图。点「确定」= 本地立即关闭 +
 *     把列表交给本 store 提交，自己绝不持有网络、绝不等待往返。
 *   B 提交器 commit：唯一写口。成功=权威列表落位；422=草稿存快照 + 逐条
 *     toast 点名；其他=全局错误通道 + 失败对账。
 *   C 渲染 ChatInput 徽标：subscribe 本 store，只取数量。
 *
 * 【为什么 422 必须留草稿】
 *   提交与关闭解耦后组件随 destroyOnHidden 销毁，草稿只活在这一帧 ——
 *   一次整单 422 就会让用户粘的 20 条目录全部蒸发。
 *   快照只存内存、不落 localStorage：脱离本次打开即无意义。
 *
 * 【写入者三处，全部收敛在本文件】
 *   loadSession / commit / clearRejected
 * 读取者：ChatInput 徽标（数量）、SessionWorkspacePanel（打开时取 rejected 恢复草稿）
 *
 * @author 小欧
 * @date 2026-10-30
 *
 * 编辑历史: 2026-10-30 小欧 - 全链路重构: commit 入参升级为 WorkspacePatchItem[]
 *   ({path, workspace_property, memo}), 不再收 string[]; 属性/备注随行上行。 — 小欧-2026-10-30
 * 编辑历史: 2026-11-02 小欧 - 新增 rejected 快照与 clearRejected, 422 保留草稿;
 *   代际守卫/提交与关闭解耦/失败对账 逻辑零改动 — 小欧-2026-11-02
 */

import { sessionApi } from '@/services/api/session.api';
import { handleError, showMessage, ErrorType } from '@/services/error/handler';
import type { WorkspaceEntry } from '@/types/chat';

/** 提交载荷：只有三个可写字段；is_default 由后端 reconcile / _ws_apply 维护 */
export type WorkspacePatchItem = Pick<
  WorkspaceEntry,
  'path' | 'workspace_property' | 'memo'
>;

/** 422 恢复快照：整单被拒时把用户这次提交原样留住，下次打开面板据此恢复草稿 */
export interface RejectedDraft {
  items: WorkspacePatchItem[];
  bad: { path: string; reason: string }[];
}

interface WorkspaceState {
  /** 当前所属会话；异步结果回来时与它比对，不同即丢弃（切会话竞态） */
  sessionId: string;
  list: WorkspaceEntry[];
  /** 未被用户处置的 422 草稿快照（内存态，不落盘） */
  rejected: RejectedDraft | null;
}

const EMPTY: WorkspaceState = { sessionId: '', list: [], rejected: null };

let state: WorkspaceState = EMPTY;
const listeners = new Set<() => void>();

/** 取数代际：切会话/重复触发时只认最后一次 */
let loadSeq = 0;
/** 提交代际：并发提交只认最后一次 */
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
const rejectionsOf = (e: unknown): { path: string; reason: string }[] => {
  const raw = (
    e as {
      response?: { data?: { error?: { workspace_rejected?: unknown } } };
    }
  )?.response?.data?.error?.workspace_rejected;
  return Array.isArray(raw) ? (raw as { path: string; reason: string }[]) : [];
};

/** 失败对账：把徽标拉回库里的真值。
 *  超时/连接中断时后端可能已写成功，前端无从分辨，只能以库为准。 */
const reconcile = async (sessionId: string) => {
  try {
    const r = await sessionApi.getWorkspaces(sessionId);
    if (state.sessionId !== sessionId) return;
    setState({ ...state, list: r.workspaces }); // rejected 保留：草稿还没处置
  } catch {
    // 对账本身失败：保持旧值，不做二次提示（用户刚看过主错误）
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
    setState({ sessionId, list: [], rejected: null }); // 换会话即弃旧草稿
  }
  try {
    const r = await sessionApi.getWorkspaces(sessionId);
    if (seq !== loadSeq || state.sessionId !== sessionId) return;
    setState({ ...state, list: r.workspaces });
  } catch {
    if (seq !== loadSeq || state.sessionId !== sessionId) return;
    setState({ ...state, list: [] });
  }
};

/** 提交：点完即关。成功=权威列表落位清快照；422=快照留存+逐条点名；其他=错误通道+对账。 */
const commit = async (
  sessionId: string,
  items: WorkspacePatchItem[]
): Promise<void> => {
  const seq = ++commitSeq;
  try {
    await sessionApi.patchWorkspaces(sessionId, items);
    if (seq !== commitSeq || state.sessionId !== sessionId) return;
    setState({
      sessionId,
      // 三字段原样保留，禁止退化成 { path }
      list: items.map((i) => ({ ...i })),
      rejected: null,
    });
  } catch (e: unknown) {
    if (seq !== commitSeq) return;
    const bad = rejectionsOf(e);
    if (bad.length) {
      if (state.sessionId === sessionId) {
        // 草稿原样留住：被拒的是"整单"，用户改完一条不该重打另外 19 条
        setState({
          ...state,
          rejected: { items: items.map((i) => ({ ...i })), bad },
        });
      }
      // 统一错误通道：toast 逐条点名（查表+去重+分级），禁自造 notify/裸调 message
      bad.forEach((x) =>
        showMessage(ErrorType.WORKSPACE_REJECTED, `${x.path}：${x.reason}`)
      );
    } else {
      handleError(e);
    }
    await reconcile(sessionId);
  }
};

/** 用户放弃被拒草稿：清快照，面板据库真值重载 */
const clearRejected = (sessionId: string): void => {
  if (state.sessionId !== sessionId || !state.rejected) return;
  setState({ ...state, rejected: null });
};

export const workspaceStore = {
  subscribe,
  getSnapshot,
  loadSession,
  commit,
  clearRejected,
};
