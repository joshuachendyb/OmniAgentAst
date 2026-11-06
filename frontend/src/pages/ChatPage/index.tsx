// 编辑历史: 2026-08-28 小欧 - NewChatContainer瘦身: 抽9 hook(useAuthorization/useChatScroll/useSessionMeta/useTaskSelection/useChainTokens/useChatInit/useChatLifecycle/useChatTitle/useChatPanels), 本文件<100行(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - v1.100实施: 点击任务联动右栏展开, 新增handleSelectTaskOpenRight包装(useChatPanels入参handleSelectTask→handleSelectTaskOpenRight, 4.5.1联动锚定) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复输入框悬空: 根div高度由写死calc(100vh-120px)改为height:100%填满Content(Content为flex:auto有确定高度, 原公式比实际可用高度矮61px导致底部空白) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 设计文档 v1.103: 修复(serverTaskId变化即refreshTasks, SSE start帧任务产生即入列) + latestTaskId透传useTaskSelection/useChainTokens(签名同步) - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被隐藏修复。创建latestTaskRef常驻ref并透传useChatPanels→TaskListPanel(左列滚动定位到最新任务) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): useChainTokens入参加metaFrames(SSE实时token帧源), 解构新增sessionTokens并透传useChatPanels - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: CP-01 serverTaskId监听补sessionId防切会话残留旧列表 - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 同类DB滞后修复: 直播失败即刷新左列(消executing残留) - 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - 修复修正: handleSendWithMode改async+await, 原void吞Promise致ChatInput catch永不触发回填无效 - 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 简化重构: AuthorizationModal加key={confirmId}强制重建, 新请求=新组件实例, 彻底消除countdown/autoHandledRef等跨请求残留 - 小欧-2026-09-03
// 编辑历史: 2026-09-06 小欧 - B1「已放行」短时高亮: useAuthorization 解构 recentConfirmedTool 并透传 useChatPanels —— 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈定案): liveErrorText✗ string 改 liveError(LiveError|null 对象形态,
//   onError 升为 (liveError: LiveError)=>void 接收 位置2/类型分层字段) + setter/一处消费(if(liveError)refreshTasks,
//   暂用对象真值判空)与 useChatPanels 透传同步 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-A类: 去chatSession/chatPersistence解构(死解构, eslint@typescript-eslint/no-unused-vars) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 透传rightOpen状态给useChatPanels, 控制TaskListPanel模型标签provider前缀条件显示 - 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - thought重复根治(三堂会审定案): 病根=useChatInit effect依赖searchParams对象引用
//   (React Router useSearchParams每次渲染返回新对象)致流式期间反复重跑initializeSession, 直接赋值
//   setMessages(result.messages)覆盖流式assistant消息; 根治=只传稳定urlSessionId字符串(非全局searchParams对象),
//   effect依赖它(session_id不变即不重跑)。曾用useMemo稳定引用(堵截)与isReceiving守卫(边界退化)两案, 复查后撤销 — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 即时写入final.response+DB刷新覆盖修复: 新增isReceiving翻false时写入final.response effect(isReceiving翻false时从executionSteps取final.response即时写入task, 不读DB);
//   删旧prevReceivingRef effect改DB落库信号触发刷新(final_stats到达=DB已落库才触发refreshTasks); 解构补updateTaskResponse — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复: L54 searchParams.get('session_id') 复用已有 urlSessionId(L47), 消重复取参(DRY) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 左卡草稿根治: 数据源修正(lastMsg.content→executionSteps中type=final的step.response, 无兜底) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - X2终态短信号(北京老陈定案): 删除DB刷新覆盖(hasFinalStats→refreshTasks DB兜底补左侧response), 铁命令: 左侧只用final.response, 实时短条留空、历史回放从DB读; useChainTokens 的 final_stats→refreshTasks(token刷新)保持不变 — 小欧-2026-09-12
// 编辑历史: 2026-09-13 小欧 - 北京老陈定案: 新建会话时右侧面板整体折叠(rightOpen=false)——右栏残留信息已根治清空,
//   但新会话仍展开空态右栏不符预期; handleNewSession 包装置折叠, 点任务经 handleSelectTaskOpenRight 再展开 — 小欧-2026-09-13
// 编辑历史: 2026-09-14 小欧 - 布局底部被推出视口修复(北京老陈令): 根div高度由calc(100vh-59px)改height:'100%'+overflow:'hidden',
//   外层Layout已锁height:100vh, 本层填满Content即可, 输入条/整体窗口底部始终钉视口内(Edge/Chrome缩放实测通过) — 小欧-2026-09-14
// 编辑历史: 2026-09-15 小欧 - 新任务开始执行自动展开右栏(北京老陈反馈修复): 2026-09-13 折叠改动后 rightOpen 只靠初始
//   true 兜底, 新建会话折叠后直接发新任务无任何 setRightOpen(true), 右侧step面板一直折叠不显示; 在 serverTaskId
//   变化(SSE start帧=任务开始执行)的既有effect守卫内补 setRightOpen(true), 一处覆盖所有产任务路径(新消息/重试),
//   不误伤"新建会话默认折叠"定案(切会话serverTaskId清空为null不进守卫) — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 三堂会审(北京老陈质疑"什么鬼控件/有无不当重复/10大规范")方案A退回改方案B:
//   方案A用 prevServerTaskIdRef+useEffect 绕到"serverTaskId变化"才展开, 违KISS-DIRECT(发送入口唯一却绕远路)/
//   SRP(污染「任务列表刷新」effect)/YAGNI(为不存在的"重试"产任务路径通用化)+冗余依赖setRightOpen; 已撤销effect内改动;
//   改为在唯一发送入口 handleSendWithMode 直线 setRightOpen(true)(发送即展开右侧step面板, 请求级失败右栏展开亦无副作用);
//   "点击任务展开"与"发送任务展开"两触发源调同一setter非重复实现(DRY合规),「任务列表刷新」effect恢复单一职责 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
//   useChatPanels 调用新增 updateTaskResponse 透传(供 RightViewer 历史任务加载 steps 后写 final.response 到左侧) — 小欧-2026-09-15
// 编辑历史: 2026-09-19 小欧: useChatFacade加onSuccess: () => setLiveError(null), 任务成功完成时清LiveMeta — 北京老陈驱动
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.16 页面只订阅不拥有流: ①补注流状态已常驻 Store,
//   本组件仅订阅, 不再承担流的生命周期; ②useChatInit 入参 sessionId 由 urlSessionId 改
//   `urlSessionId ?? undefined` —— 5.4 约束: 未解析出真实 sessionId 时不得 ensureSession
//   (建空会话会污染 Store 注册表与历史列表) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 14:30 小欧 - 新增 onUrlSessionChange，用 setSearchParams 作 URL 唯一写入口（原直接改地址栏致前进后退不同步）
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.9 + 5.8.20: handleSendWithMode 改名 handleSend, 第二参由 mode
//   改 linkEnabled: boolean; 新增 handleToggleLink 为纯本地态(setLinkEnabled, 不发请求) — 小欧 2026-10-03
// 编辑历史: 2026-10-08 小欧 - 文档[11]: 注入 onTasksChanged(ref 中转 refreshTasks, 插话并入后左栏「追加N条」才刷新)
// 编辑历史: 2026-10-20 07:42:12 小欧 - 底部留白压缩(北京老陈令): 容器padding底8→2px, 与Layout Content底距(10→4)合计18→6px — 小欧-2026-10-20
// 编辑历史: 2026-10-24 小欧 - SRP拆分: useModelLayer调用删sessionTitle(不再需要) - 小欧-2026-10-24
// 编辑历史: 2026-10-28 小欧 - onSuccess 补 refreshTasks 兜底: 任务完成(final帧)刷新左栏 status(executing→completed),
//   根治 final_stats 帧丢失竞态致 refresh 不触发→左栏永久卡 executing; 经 refreshTasksRef 调用(解闭包陈旧), 见 L97 区块 — 小欧-2026-10-28
// 编辑历史: 2026-10-31 小欧 - 注释订正(北京老陈指正): 第一行动态状态位是位置2, 原注释序号写错(2026-09-17 重排前是第4位), 全文统一为"位置2" — 小欧-2026-10-31
// 编辑历史: 2026-11-02 小欧 - 注释整改(逻辑零变更): 删过期存疑条目(原 L157-170 "RightViewer L424 仍调 refreshTasks" 与代码不符,
//   RightViewer 已删该覆盖, 左侧写入仅 updateTaskResponse) - 小欧-2026-11-02
// 编辑历史: 2026-11-03 小欧 - 顶栏主语由本页发布(foregroundSessionStore): useLayoutEffect 发布当前会话、卸载即交还
//   LATEST_RUNNING 口径(URL 无 session_id 时曾与画面不一致) - 小欧-2026-11-03

// 编辑历史: 2026-11-06 小欧 - 附件建会话 ensureSessionForUpload: 先选文件、选中后才建(取消选择不建空会话);
//   解构到组件作用域供 useCallback 引用(避免闭包访问 chatState 触发 deps warning) — 小欧-2026-11-06

import React, {
  useState,
  useEffect,
  useLayoutEffect,
  useCallback,
  useRef,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import type { LiveError } from '@/types/sse'; // 2026-09-08 小欧 - 位置2 数据源对象形态
import { API_BASE_URL } from '../../services/api/client';
// 2026-11-06 小欧 - 附件先选文件、选中后才建会话(取消选择不建空会话) — 小欧-2026-11-06
import { sessionApi } from '../../services/api/session.api';
import { useChatFacade } from '../../features/chat/hooks/useChatFacade';
import { useSessionTasks } from '../../features/chat/hooks/useSessionTasks';
import { useModelLayer } from '../../features/chat/hooks/useModelLayer';
import { useAuthorization } from '../../features/chat/hooks/useAuthorization';
import { useChatScroll } from '../../features/chat/hooks/useChatScroll';
import { useSessionMeta } from '../../features/chat/hooks/useSessionMeta';
import { useTaskSelection } from '../../features/chat/hooks/useTaskSelection';
import { useChainTokens } from '../../features/chat/hooks/useChainTokens';
import { useChatInit } from '../../features/chat/hooks/useChatInit';
import { useChatLifecycle } from '../../features/chat/hooks/useChatLifecycle';
import { useChatTitle } from '../../features/chat/hooks/useChatTitle';
import { useChatPanels } from '../../features/chat/hooks/useChatPanels';
import {
  publishForegroundSession,
  clearForegroundSession,
} from '../../features/chat/services/foregroundSessionStore';
import type { SendOpts } from '../../types/chat'; // 2026-10-07 小欧 - 对象参数
import { SessionLayout } from '../../features/chat/components/layout/SessionLayout';
import AuthorizationModal from '../../components/AuthorizationModal';
import { Colors } from '@/utils/stepStyles';

const ChatPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  // 2026-11-02 小欧 - 稳定 urlSessionId 字符串：useChatInit 的 effect 依赖它而非 searchParams 对象引用，
  // 流式期间 session_id 不变即不重跑 initializeSession。
  const urlSessionId = searchParams.get('session_id');
  const [liveError, setLiveError] = useState<LiveError | null>(null); // 2026-09-08 小欧 - 对象形态(位置2 类型+分层字段)
  const [rightOpen, setRightOpen] = useState(true);
  // 2026-11-02 小欧 - 左列最新任务锚点 ref（传入 useChatPanels → TaskListPanel 滚动定位）
  const latestTaskRef = useRef<HTMLDivElement | null>(null);
  // 2026-10-08 小欧 - refreshTasks 在本组件下方(useSessionTasks)才声明, 而 onTasksChanged
  //   要在 useChatFacade 入参里给 → 用 ref 中转(同 useChatCallbacks 的 onSuccessRef 模式, 解闭包陈旧)
  const refreshTasksRef = useRef<() => void>(() => undefined);
  // 2026-11-02 小欧 - 流状态常驻 Store，本组件只订阅，不拥有流的生命周期
  const chatFacade = useChatFacade({
    baseURL: API_BASE_URL,
    sessionId: urlSessionId ?? undefined, // 未解析出真实 sessionId 时不 ensureSession
    onError: (liveError: LiveError) => setLiveError(liveError),
    // 2026-09-19 小欧: 任务成功完成(终态非failed)清liveError, 避免error后恢复完成仍残留错误指示 — 北京老陈驱动
    // 2026-10-28 小欧 - 补 refreshTasks 兜底: 任务完成后刷新左栏任务状态(executing→completed)。
    //   根因: refresh 原只靠 useChainTokens 的 hasFinalStats(final_stats 帧)信号触发, 但 final_stats 帧
    //   在前端存在丢失竞态(final 先到 onComplete 触发、final_stats 后到可能已断流)→ hasFinalStats 恒 false
    //   → refresh 不触发 → 左栏状态永久卡 executing。onSuccess 是流结束的可靠信号(final 帧在后端 DB
    //   落库后补发, onComplete 时 DB 已落 status), 此处兜底 refresh 拉最新 status。refresh 幂等, 与
    //   finalStats 路径重复无害。经 ref 调用避免闭包陈旧。
    onSuccess: () => {
      setLiveError(null);
      void refreshTasksRef.current();
    },
    // 2026-10-08 小欧 - 文档[11]: 插话被后端并入后重取左栏, 否则「追加N条」停在旧快照不出现
    onTasksChanged: () => refreshTasksRef.current(),
    // 2026-09-30 小欧 - URL 写入唯一出口：本页是唯一与 Router 接触处。原生 pushState 不派发
    //   popstate、Router v7 只监听 popstate → urlSessionId 陈旧 → 写错会话
    onUrlSessionChange: (id: string | null) => {
      setSearchParams(id ? { session_id: id } : {});
    },
  });
  const { chatState, chatStreaming, chatSend, chatTaskControl } = chatFacade;
  const { sessionId } = chatState;
  // 2026-11-06 小欧 - 附件建会话写入(解构到组件作用域, 供 ensureSessionForUpload 依赖,
  //   避免 useCallback 内访问 chatState 触发 react-hooks/exhaustive-deps warning) — 小欧-2026-11-06
  const { setSessionId } = chatState;
  // 2026-11-03 小欧 - 顶栏主语发布(会话页口径): URL 不是权威(`/` 无 session_id 时顶栏报"无任务"), 本页显示哪个就报哪个。
  //   用 useLayoutEffect 而非 useEffect: 后者绘制后跑, 首帧会闪一次"别的会话/后台任务"的状态。
  useLayoutEffect(() => {
    publishForegroundSession(sessionId || null);
  }, [sessionId]);
  // 卸载即交还「开跑最晚且仍在跑」口径(非会话页); 与发布分开, 避免切换会话时 clear→publish 抖动
  useLayoutEffect(() => clearForegroundSession, []);
  const {
    tasks,
    total,
    loading: tasksLoading,
    refresh: refreshTasks,
    latestTaskId,
    updateTaskResponse, // 小欧 2026-09-11 SSE final 帧到达时即时更新 task response — 小欧-2026-09-11
  } = useSessionTasks(sessionId);
  // 2026-11-02 小欧 - ref 中转是顺序依赖所必需(useChatFacade 的 sessionId 来自其返回值,
  //   useSessionTasks 只能声明在其后), 回调经 ref 取最新 refresh; 改为 effect 同步, 避免渲染期写 ref。
  useEffect(() => {
    refreshTasksRef.current = refreshTasks;
  }, [refreshTasks]);
  const { effective } = useModelLayer({
    sessionId,
    sessionVersion: chatState.sessionVersion,
    setSessionVersion: chatState.setSessionVersion,
    sessionModelOverride: chatState.sessionModelOverride,
  });

  const {
    authorizationPending,
    handleAuthorizationConfirm,
    recentConfirmedTool,
  } = useAuthorization(sessionId);
  useChatScroll(chatState, chatStreaming);
  const { sessionTimes } = useSessionMeta(sessionId);
  const { activeTaskId, selectedDetail, handleSelectTask } = useTaskSelection(
    sessionId,
    chatStreaming.serverTaskId,
    chatStreaming.isReceiving,
    latestTaskId,
    tasks
  );

  // 2026-11-02 小欧 - serverTaskId 变化即刷新任务列表：SSE start 帧产生任务即入列，左列实时可见
  const prevServerTaskIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (prevServerTaskIdRef.current !== chatStreaming.serverTaskId) {
      prevServerTaskIdRef.current = chatStreaming.serverTaskId;
      if (chatStreaming.serverTaskId) {
        void refreshTasks();
      }
    }
  }, [chatStreaming.serverTaskId, sessionId, refreshTasks]);

  // 2026-11-02 小欧 - 左侧回复区写入：isReceiving 翻 false 时取 executionSteps 中 type=final 的 response 写入，
  // 仅非空才写（completed 正常完成的 final.response 为空，左侧留空，历史回放从 DB 读）。
  const prevReceivingForR3Ref = useRef(false);
  useEffect(() => {
    if (
      prevReceivingForR3Ref.current &&
      !chatStreaming.isReceiving &&
      chatStreaming.serverTaskId
    ) {
      const finalStep = chatStreaming.executionSteps.find(
        (s) => s.type === 'final'
      );
      const finalResponse = (finalStep?.response as string) || '';
      if (finalResponse) {
        updateTaskResponse(chatStreaming.serverTaskId, finalResponse);
      }
    }
    prevReceivingForR3Ref.current = chatStreaming.isReceiving;
  }, [
    chatStreaming.isReceiving,
    chatStreaming.serverTaskId,
    chatStreaming.executionSteps,
    updateTaskResponse,
  ]);

  // 2026-11-02 小欧 - 点击任务 → 右栏展开（点击查看即展开）
  const handleSelectTaskOpenRight = useCallback(
    (taskId: string) => {
      setRightOpen(true);
      handleSelectTask(taskId);
    },
    [handleSelectTask]
  );
  const { sessionTokens, chainTokens } = useChainTokens(
    sessionId,
    chatStreaming.serverTaskId,
    chatStreaming.isReceiving,
    latestTaskId,
    tasks,
    refreshTasks,
    chatStreaming.metaFrames // 2026-09-01 小欧: SSE实时token帧源
  );
  const handleSend = useCallback(
    async (content: string, opts: SendOpts) => {
      setLiveError(null);
      setRightOpen(true); // 2026-11-02 小欧 - 发送即展开右侧 step 面板（唯一发送入口，直线调用）
      await chatSend.handleSend(content, opts);
    },
    [chatSend, setLiveError, setRightOpen]
  );

  // 会话级 link 开关 — 纯本地态。值随消息落库, 勾选无需请求; 无 sessionId 也能勾选, 发消息时携带。
  const handleToggleLink = useCallback(
    (enabled: boolean) => chatState.setLinkEnabled(enabled),
    [chatState.setLinkEnabled]
  );

  /**
   * 2026-11-06 小欧 - 附件上传前的会话保证。
   * 已有会话直接返回; 无会话时建一个并同步 URL(与 useChatSend 自动建会话同口径)。
   * 只在"用户真的选中了文件"后调用, 因此不会产生空会话。 — 小欧-2026-11-06
   */
  const ensureSessionForUpload = useCallback(async (): Promise<
    string | null
  > => {
    if (sessionId) return sessionId;
    try {
      const s = await sessionApi.createSession();
      setSessionId(s.session_id);
      setSearchParams({ session_id: s.session_id });
      return s.session_id;
    } catch {
      return null; // 失败不静默: 调用方(AttachmentArea)负责提示
    }
  }, [sessionId, setSessionId, setSearchParams]);

  // 2026-11-02 小欧 - 切换会话时重置跨会话泄漏状态（liveError）
  useEffect(() => {
    setLiveError(null);
  }, [sessionId]);

  // 2026-11-02 小欧 - 直播失败文案到达即刷新左列，消除 DB executing 残留
  useEffect(() => {
    if (liveError) void refreshTasks();
  }, [liveError, refreshTasks]);

  // 会话初始化 / 生命周期 / 标题编辑（抽离至各 hook）
  useChatInit({ chatFacade, urlSessionId });
  // 2026-11-02 小欧 - 新建会话时右栏收起（setRightOpen(false)），点任务经 handleSelectTaskOpenRight 再展开
  const { handleNewSession: handleNewSessionBase } = useChatLifecycle({
    chatFacade,
  });
  const handleNewSession = useCallback(() => {
    setRightOpen(false);
    return handleNewSessionBase();
  }, [handleNewSessionBase]);
  const { handleEditingStart, handleEditingCancel } = useChatTitle(chatState);

  const panels = useChatPanels({
    chatState,
    chatStreaming,
    chatTaskControl,
    chatSend,
    liveError,
    authorizationPending,
    recentConfirmedTool, // 2026-09-06 小欧 B1: 「已放行」短时高亮透传 — 小欧-2026-09-06
    handleAuthorizationConfirm,
    tasks,
    total,
    tasksLoading,
    refreshTasks,
    updateTaskResponse, // 2026-09-15 小欧(北京老陈定案): 左侧回复区只用 final.step.response 渲染——透传 useChatPanels→RightViewer — 小欧-2026-09-15
    effective,
    sessionTimes,
    activeTaskId,
    selectedDetail,
    handleSelectTask: handleSelectTaskOpenRight,
    sessionTokens,
    chainTokens,
    handleNewSession,
    handleEditingStart,
    handleEditingCancel,
    handleSend,
    onToggleLink: handleToggleLink,
    allowInterject: chatState.allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.4: 透传给 useChatPanels→ChatInput
    onToggleInterject: (v: boolean) => chatState.setAllowInterject(v), // 2026-10-07 小欧 - 文档[11] 3.5.4: ChatPage 是开关本地态唯一写入口
    // 2026-11-06 小欧 - 附件建会话
    ensureSession: ensureSessionForUpload,
    latestTaskId, // 2026-09-01 小欧 方案C: 左列最新任务锚点透传
    latestTaskRef, // 2026-09-01 小欧 方案C: 滚动定位ref透传
    rightOpen, // 2026-09-09 小欧: 右侧展开状态透传TaskListPanel
  });

  return (
    <div
      style={{
        height: '100%', // 2026-09-15 小欧: 外层Layout已锁定height:100vh+overflow:hidden, 本层填满Content即可, 不再用calc(100vh-59px)
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        padding: '0 8px 2px', // 2026-10-20 小欧 - 底 8→2(北京老陈指令: 控件行下留白压到 2px); 上下左右其余不变
        background: Colors.BG.PRIMARY,
        minWidth: 0,
        overflow: 'hidden',
      }}
    >
      <SessionLayout
        panels={panels}
        rightOpen={rightOpen}
        onToggleRight={() => setRightOpen((v) => !v)}
      />
      <AuthorizationModal
        key={authorizationPending?.confirmId ?? 'none'}
        visible={!!authorizationPending}
        request={authorizationPending}
        onConfirm={handleAuthorizationConfirm}
      />
    </div>
  );
};

export default ChatPage;
