// [63] 5.5：组件↔Store 订阅桥接（useSyncExternalStore）。页面只订阅：卸载仅 unsubscribe，
//   不会 abort、不会清 Store、不会删 sessionStorage（停止任务必须走显式 stop()）。
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import type { ExecutionStep } from '@/types/execution';
import type { StreamEvent } from './backupTypes';
import { chatStreamStore } from './chatStreamStore';

/** 2026-09-29 小欧：空 sessionId 时的只读空 ref 视图（render 期不得 ensureSession 造 '' 假会话） */
const EMPTY_STEPS_REF: { current: ExecutionStep[] } = { current: [] };

/**
 * 订阅某会话的流快照与事件。**本 hook 是纯订阅桥接，只出数据与视图，不出动作。**
 * @param sessionId 会话 id（null 时只读冻结空快照，不订阅不创建）
 * @param onEvent 真实帧事件回调（须由调用方 useCallback 保持稳定引用）
 * @returns 快照字段 + 推导视图（waitClock/executionStepsRef）
 */
export function useChatStreamSession(
  sessionId: string | null,
  onEvent?: (event: StreamEvent) => void
) {
  const id = sessionId ?? '';
  // 2026-09-30 08:44:31 小欧 - [79] D2：**删除**本文件的 render 期 `if (id) ensureSession(id)`。
  //   该行是 2026-09-29 22:47:10 为治"零钟面锁死"加的防退化补丁，但它违反 [63] 5.4
  //   「render 期绝不创建会话」：组件首渲染即在 Store 建条目，render 被丢弃时纯属泄漏，
  //   且会挤占 D3 的 MAX_SESSIONS 容量；getExecutionStepsRef 自身也无条件 ensureSession（同病）。
  //   根治：那两个取视图函数改为"缺会话返回按 id 缓存的**活**视图"（见 chatStreamStore
  //   makeClockView / makeStepsView / missingViewsOf）——引用稳定满足 useMemo，而 getter 现取真值，
  //   会话一出现即自动报真值，故零钟面不再被钉死，无需在 render 期抢跑建会话。
  const snapshot = useSyncExternalStore(
    (callback) => (sessionId ? chatStreamStore.subscribe(sessionId, callback) : () => undefined),
    () => chatStreamStore.getSnapshot(id),
    () => chatStreamStore.getSnapshot(id)
  );
  useEffect(() => {
    if (!sessionId) return undefined; // 空 id 不订阅（只有真实 id 才有会话）
    return onEvent ? chatStreamStore.subscribeEvents(sessionId, onEvent) : undefined;
  }, [sessionId, onEvent]);
  return {
    ...snapshot,
    // 2026-09-30 小欧 - [79] F①：**删除** 4 个纯透传成员（sendMessage/resume/stop/clearSteps），
    //   **北京老陈 2026-09-30 以可靠性为唯一裁决标准裁定删除**（推翻 09:02:06 的"保留+记忆化"方案）。
    //   裁定逐条依据（三堂会审）：
    //   ① 透传层即双真源拷贝：4 成员逐字转发 chatStreamStore.*，违反 [63] 6.5「无透传函数」，
    //      Store 改签名时此处是漏改点（DRY 违规 = 可靠性风险源）；
    //   ② 生产消费面精确：sendMessage/clearSteps 唯一生产消费者是 useChatStreaming:361/:405，
    //      已改直连 chatStreamStore（与 useChatInit:81、useChatTaskControl:162、useChatSession:568-569
    //      既有直连惯例同构）；resume/stop 全仓零生产消费者；
    //   ③ 调用链由「useChatStreaming→透传层→store」收敛为「useChatStreaming→store」直线；
    //   ④ 本 hook 头注释自述"只出数据与视图，不出动作"，删成员后实现与契约语义自洽。
    //   测试消费面（之前"33 断言=契约"的顾虑已判为非障碍）：6 个测试文件 31 处断言改为直连
    //   chatStreamStore（真源在 Store，测试直连真源更贴真值，不削弱验证力度）。
    waitClock: useMemo(
      () => chatStreamStore.getClockSignals(id),
      // 2026-09-29 22:47:10 小欧（[63] 5.5 防退化修复）：原稿每次 render 现调 getClockSignals
      //   必得新对象，而 useChatPanels.tsx:159 的 useMemo 把 waitClock 列入依赖（心跳微闪驱动
      //   RightViewer 重渲）——引用每次都变会让该 useMemo 永久失效、面板逐帧重算。
      //   口径与被删的 useSSE 一致：waitClock 仅依赖 heartbeatTs 变化才换引用。
      // 2026-09-30 08:44:31 小欧 - [79] D2：getClockSignals 改为返回**活视图**后，此依赖被 ESLint
      //   判为"多余"（函数体内已不读 snapshot.heartbeatTs）。但它**不可删**：值的鲜度已由活 getter
      //   保证，此依赖的唯一作用是让心跳时换新 waitClock 引用，从而让 useChatPanels 的下游 useMemo
      //   重渲（心跳微闪）。删之即丢失该重渲路径——属功能退化，非清理冗余。故显式豁免并留证。
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [id, snapshot.heartbeatTs]
    ),
    // 推导 ref 视图——5.3 parser 与组件层同一对象（非第二真源）；空 id 走只读空视图
    executionStepsRef: sessionId ? chatStreamStore.getExecutionStepsRef(id) : EMPTY_STEPS_REF,
  };
}

// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.5 Store 订阅桥接(useSyncExternalStore 快照 +
//   事件双通道；组件卸载只 unsubscribe，流不销毁) — 小欧-2026-09-29 21:37:55
//   相对 [63] 5.5 原稿的 1 处修正 — 小欧-2026-09-29 21:37:55：
//   executionStepsRef 原稿无条件 chatStreamStore.getExecutionStepsRef(id)，id 为 ''（sessionId=null）时
//   会在 render 期 ensureSession('') 造出假会话条目并泄漏（与 5.4「getSnapshot 路径绝不创建」相悖）；
//   改为空 id 返回模块级只读空视图。
//
// 编辑历史: 2026-09-29 22:47:10 小欧 - [63] 5.5 防退化修复 2 处 — 小欧-2026-09-29 22:47:10：
//   ① waitClock 原每次 render 新建对象 → useChatPanels useMemo 永久失效，改 useMemo([id, heartbeatTs])；
//   ② heartbeatTs 未列入 5.4 快照 → 心跳不触发 bump 通知、等待期 ClockStopwatch 冻结，
//      已在 backupTypes.SessionSnapshot + chatStreamStore.SNAPSHOT_KEYS/bump 补齐。
//
// 编辑历史: 2026-09-29 23:22:19 小欧 - [63] 5.5 防退化修复：零钟面锁死 — 小欧-2026-09-29 23:22:19：
//   症状：首帧迟到/空流的会话，waitClock.lastBizTsRef 恒 0，等待动画与静默升档全失效
//   （A5 单测"新任务 send 重置业务基线"红：expected 0 to be greater than 0）。
//   成因：会话原先只由返回对象里 executionStepsRef 的 ensureSession 副作用创建，而它排在
//   waitClock 的 useMemo **之后**——首渲染 waitClock 先算，session 尚未创建，
//   getClockSignals 只能返回 ZERO_CLOCK（恒 0）；空流场景 heartbeatTs 恒 0，memo 依赖永不
//   变化 → 组件永久持有零钟面。
    //   修复：render 期显式 if (id) ensureSession(id)（幂等 Map 命中即返回；空 id 不建，防造
    //   '' 假会话），effect 退化为纯订阅。heartbeatTs 仍留在 memo 依赖里——心跳微闪要靠它触发
    //   useChatPanels 的 useMemo 重渲。
//
// 编辑历史: 2026-09-30 08:44:31 小欧 - [79] D2：撤销上一条的 render 期 ensureSession，改为根治 — 小欧-2026-09-30 08:44:31：
//   上一条（22:47:10）用 render 期 ensureSession 治"零钟面锁死"，代价是违反 [63] 5.4「render 期绝不创建」
//   （且 getExecutionStepsRef 自身也无条件 ensureSession，同病），render 被丢弃时条目纯属泄漏。
//   现改为：getClockSignals / getExecutionStepsRef 缺会话时返回**按 id 缓存的活视图**——
//   引用稳定（满足本文件 waitClock 的 useMemo 与 useChatPanels 的下游 useMemo），
//   getter 经 sessions.get(id) 现取，会话一出现同一对象即报真值 → 零钟面不再被钉死，
//   故无需 render 期抢跑建会话。活视图表在 ensureSession / evictSession / destroySession 三处同步回收，
//   生命周期与 sessions 同形。空 id 仍走 EMPTY_STEPS_REF / ZERO_CLOCK 哨兵（无 id 可言，不建缓存条目）。
//
// 编辑历史: 2026-09-30 08:56:35 小欧 - [79] F①：删除 4 个纯透传箭头，本 hook 收敛为纯订阅桥接 — 小欧-2026-09-30 08:56:35：
//   删 sendMessage/resume/stop/clearSteps 四个透传成员。查证结论：resume/stop 全仓零消费者（死代码）；
//   clearSteps/sendMessage 各仅 1 个调用点（useChatStreaming :405/:361），已改直连 chatStreamStore——
//   与 useChatInit.ts:81、useChatTaskControl.ts:162、useChatSession.ts:568-569 的既有惯例一致。
//   实际危害不止违反 [63] 6.5「无透传函数」：四个箭头每次 render 重建，而 useChatStreaming 把其中
//   两个塞进 useCallback 依赖数组（:368/:507/:520），致那两个 useCallback 每次 render 必然失效——
//   删除后依赖数组不再含不稳定身份，memo 稳定性**提升**（功能增强，非仅清理）。
//   保留项说明：useChatStreaming 对外返回的 sendMessage/clearSteps **签名不变**（矛盾 D 已裁定
//   "消费面签名不变"，改动它需连带翻转 D5 判定，超出 F① 范围），故其 clearSteps 改为
//   useCallback 记忆化的绑定动作（引用稳定），而非桥接透传。
//
// 编辑历史: 2026-09-30 09:02:06 小欧 - [79] F① 修正：4 个成员改为 useCallback 记忆化（**撤回同日删除方案**） — 小欧-2026-09-30 09:02:06：
//   撤回上一条的"删除 4 个透传箭头"方案。推翻依据（两条反证，非主观改口）：
//   ① 消费者不止生产代码——`src/tests/` 下 6 个文件 33 条断言把本桥接当 [63] 5.5 契约验证，
//      直接调 `result.current.sendMessage(...)`；删成员实测 33 红（6 文件），属功能退化。
//      首轮核查我只 grep 生产代码、漏查测试目录，误判"零消费者"，该疏漏已如实记录。
//   ② resume/stop 虽无生产调用点，仍是 5.5 蓝图对外成员；删成员=改公开契约，与矛盾 D 已裁定的
//      "消费面签名不变"冲突，超出实施方权限，留待北京老陈裁定。
//   本条改为只治可确认的真实危害：4 个成员用 useCallback([id]) 记忆化。改前每次 render 重建，
//   而 useChatStreaming 把 sendMessage/clearSteps 放进 useCallback 依赖数组（:368/:507/:520），
//   致那两个 useCallback 每次 render 必然失效；改后引用随会话 id 稳定，memo 稳定性提升。
//   5.5 蓝图要求的 4 成员签名与语义逐字未变，33 条契约断言不受影响。
//
// 编辑历史: 2026-09-30 10:44:56 小欧 - [79] F① 定稿：删除 4 个纯透传成员（北京老陈授权，
//   以「是否增强系统可靠性和稳定性」为唯一裁决标准裁定删除）— 小欧-2026-09-30 10:44:56：
//   推翻 09:02:06「保留+useCallback 记忆化」与 08:56:35 首轮删除的共同疑虑——当时以「6 个测试
//   文件 33 断言=契约、resume/stop=蓝图对外成员、矛盾 D 消费面签名不变」为由主张保留删不得。
//   现裁定事实更正：①测试断言验证的是透传层而非真源，改直连 chatStreamStore 后验证力度不减弱
//   （真源唯一，测试直连真源）；②矛盾 D「消费面签名不变」约束的是 useChatStreaming 对外返回的
//   sendMessage/clearSteps 签名，该两成员由 useChatStreaming 自身 useCallback 包装后返回，
//   签名与语义不变即可，桥接删成员不触碰该公开面；③resume/stop 零生产消费者，
//   是 5.5 蓝图残留死成员，删后无任何功能路径受影响。
//   收益（增强的证据链）：call 链少一层、双真源汇一、Store 演化只改一处、本 hook 与自身
//   头注释"只出数据与视图，不出动作"语义自洽；useChatStreaming 的 useCallback 依赖数组
//   不再含桥接透传身份，memo 稳定性保持（依赖改 module 级稳定引用与 sessionId，更简）。
