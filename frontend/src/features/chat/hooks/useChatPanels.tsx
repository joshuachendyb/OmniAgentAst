// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离panels插槽组装逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-29 小强 - 修复#21: TopbarStats chainTokens由硬编码null改为透传真实chainTokens(与依赖数组一致) - 小强-2026-08-29
// 编辑历史: 2026-08-30 小欧 - 13.14 TrustPanel由config slot移至TaskInfoBar第一行尾部集成，移除config.trust - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - 方案C: 新任务被隐藏修复。新增可选入参latestTaskId/latestTaskRef并透传给TaskListPanel(左列滚动定位) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): 入参新增sessionTokens(会话累计3字段), 解构并透传TopbarStats; chainTokens由number改3字段结构; sessionTokens加入useMemo依赖(否则实时/静态更新不重算是栏不刷新) - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 设计文档v1.21§5.7-C/D落码(工具结果显示与taskinfo显示分析与设计-小欧-2026-09-01.md): TaskInfoBar 增传
//   liveErrorText(位4 🛑 数据源, error 实时显示唯一位置=taskinfo 第一行——北京老陈定案) + RightViewer 收回
//   liveErrorText 传参(error 唯一位置收口, 防右栏+位4双显示); :79 解构/:304 依赖数组既有保留, 零新依赖 - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - RightViewer 增传 frames=metaFrames(useTaskInfo badge 派生输入): 等待圈三处丢失根治,
//   waiting 依赖由 streaming 单源改 streaming/highlight/badge 三源, badge runner/paused 撑住首屏/空闲超时/confirm空隙 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ChatInput增传sessionId(CI-02跨会话草稿泄漏)+useChatPanels依赖同步 — 小欧-2026-09-02
// 编辑历史: 2026-09-06 小欧 - B1「已放行」短时高亮: 入参加 recentConfirmedTool(可选Nullable), highlightToolName 合成
//   authorizationPending?.toolName ?? recentConfirmedTool, useMemo 依赖数组纳入 recentConfirmedTool —— 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定): deniedEntries 解构/透传 RightViewer(deps 同步),
//   承被拒工具点名条数据链路 — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈定案): liveErrorText✗ string 改 liveError(LiveError|null 对象形态)
//   + 解构/:260 TaskInfoBar 透传/:329 useMemo 依赖数组同步(liveErrorText→liveError) — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 目录整理+存量warning清零-A类: TaskListPanel import路径 left→layout(目录并入);
//   去TaskMetaFrames类型导入/chatSend/handleSend解构(死代码) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B7: 补handleEditingCancel/handleEditingStart依赖(真补);
//   删body未用currentResponse与handleAuthorizationConfirm(解构+依赖数组同步清除, 先误删5行opts解构已用git diff识别恢复) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 透传rightOpen状态给TaskListPanel, 控制模型标签provider前缀条件显示 - 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - S13: 从chatStreaming解构executionStepsRef透传RightViewer(final到达时快照用) - 小欧-2026-09-10
// 编辑历史: 2026-09-12 小欧 - P1-1三堂会审修复: opts.sessionTokens/chainTokens 形状改复用TokenLayer(消私有形状重复, DRY), import TokenLayer — 小欧-2026-09-12
// 编辑历史: 2026-09-14 小欧 [36]改动点③(方案A, 北京老陈批准): RightViewer 透传删 receiving={isReceiving}
//   (props 已删接收变量; TaskInfoBar 的 receiving 语义保留, isCurrentLive 改纯函数判定) — 小欧-2026-09-14
// 编辑历史: 2026-09-14 小欧 [36]删第二个变量+第三个(北京老陈令): TaskInfoBar receiving prop 已整体删除,
//   秒表启停改由 frames 权威信号(startInfo 非空 && finalStats 空=执行走廊)驱动, 本处透传 receiving 一并删除;
//   连接级 isReceiving 只保留 ChatInput(L278)消费 — 小欧-2026-09-14
// 编辑历史: 2026-09-15 小欧 - [33]第七章(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
//   UseChatPanelsOptions 新增 updateTaskResponse prop, 解构并透传 RightViewer; 删除 onSettledRefresh(不再传) — 小欧-2026-09-15
// 编辑历史: 2026-09-17 小沈 - TopbarStats 包 span 加 marginLeft:12, 标题与任务数间距加大到约20px(5字符留白) — 小沈-2026-09-17
// 编辑历史: 2026-09-17 小欧 - [46]第五章实施: 从 chatStreaming 解构 waitClock, 透传 RightViewer 并纳入 useMemo 依赖(heartbeatTs 变化触发面板重渲) - 小欧-2026-09-17
import { useMemo } from 'react';
import { Typography } from 'antd';
import type { SessionPanel } from '../components/layout/SessionPanelRegistry';
import { ChatInput } from '../components/ChatInput';
import ChatHeader from '../components/ChatHeader';
import ChatToolbar from '../components/ChatToolbar';
import ModelPicker from '../components/ModelPicker';
import { TopbarStats } from '../components/topbar/TopbarStats';
import { TaskListPanel } from '../components/layout/TaskListPanel';
import { RightViewer } from '../components/right/RightViewer';
import { TaskInfoBar } from '../components/taskinfo/TaskInfoBar';
import { Colors, type TokenLayer } from '@/utils/stepStyles'; // 2026-09-12 小欧 P1-1: 复用TokenLayer消opts重复私有形状 — 小欧-2026-09-12
import type {
  TaskDetail,
  SessionTaskItem,
} from '../../../services/api/task.api';
import type { EffectiveModel } from './useModelLayer';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';
import type { LiveError } from '../../../types/sse'; // 2026-09-08 小欧 6.3.4: LiveError 位4数据源对象形态 — 小欧-2026-09-08
import type { UseChatFacadeReturn } from './useChatFacade';

interface UseChatPanelsOptions {
  chatState: UseChatFacadeReturn['chatState'];
  chatStreaming: UseChatFacadeReturn['chatStreaming'];
  chatTaskControl: UseChatFacadeReturn['chatTaskControl'];
  chatSend: UseChatFacadeReturn['chatSend'];
  liveError: LiveError | null; // 小欧 2026-09-02+09-08: 位4 error 实时源(LiveError 对象形态) — 小欧-2026-09-08
  authorizationPending: AuthorizationRequest | null;
  // 2026-09-06 小欧 B1: 「已放行」短时高亮工具名(确认后 2s)→RightViewer highlightToolName 合源 — 小欧-2026-09-06
  recentConfirmedTool?: string | null;
  handleAuthorizationConfirm: (
    confirmed: boolean,
    trustSession: boolean,
    confirmId?: string
  ) => void;
  tasks: SessionTaskItem[];
  total: number;
  tasksLoading: boolean;
  refreshTasks: () => void;
  // 2026-09-15 小欧 [33]第七章(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
  //   updateTaskResponse 由 ChatPage 解构自 useSessionTasks 传入, 透传 RightViewer 供历史任务写 final.response — 小欧-2026-09-15
  updateTaskResponse: (taskId: string, response: string) => void;
  effective: EffectiveModel | null;
  sessionTimes: { createdAt?: string; updatedAt?: string };
  activeTaskId: string | null;
  selectedDetail: TaskDetail | null;
  handleSelectTask: (id: string) => void;
  sessionTokens: TokenLayer; // 2026-09-01 小欧: 会话累计 token (TokenLayer复用 P1-1) — 小欧-2026-09-12
  chainTokens: TokenLayer; // 2026-09-01 小欧: 链累计 token(改3字段, TokenLayer复用 P1-1) — 小欧-2026-09-12
  handleNewSession: () => void;
  handleEditingStart: () => void;
  handleEditingCancel: () => void;
  handleSendWithMode: (
    content: string,
    mode?: 'linked' | 'independent'
  ) => void;
  // 2026-09-01 小欧 方案C: 最新任务锚点id + 挂到最新任务项的ref(左列滚动定位透传)
  latestTaskId?: string | null;
  latestTaskRef?: React.MutableRefObject<HTMLDivElement | null>;
  // 2026-09-09 小欧: 右侧展开状态, 透传TaskListPanel控制模型标签provider显示
  rightOpen?: boolean;
}

/**
 * panels 插槽组装 hook：将各子面板组装为 SessionPanel[]，供 SessionLayout 注入
 * 逻辑与 NewChatContainer 中原 useMemo 一致，未做行为改写
 */
export function useChatPanels(opts: UseChatPanelsOptions): SessionPanel[] {
  const {
    chatState,
    chatStreaming,
    chatTaskControl,
    liveError,
    authorizationPending,
    recentConfirmedTool,
    tasks,
    total,
    tasksLoading,
    refreshTasks,
    updateTaskResponse, // 2026-09-15 小欧 [33]第七章: 透传 RightViewer 供历史任务写 final.response — 小欧-2026-09-15
    effective,
    sessionTimes,
    activeTaskId,
    selectedDetail,
    handleSelectTask,
    sessionTokens,
    chainTokens,
    handleNewSession,
    handleEditingStart,
    handleEditingCancel,
    handleSendWithMode,
    latestTaskId, // 2026-09-01 小欧 方案C: 透传最新任务锚点
    latestTaskRef, // 2026-09-01 小欧 方案C: 透传挂最新任务的ref
    rightOpen, // 2026-09-09 小欧: 右侧展开状态, 透传TaskListPanel控制模型标签provider显示
  } = opts;

  const {
    sessionId,
    sessionTitle,
    titleLocked,
    editingTitle,
    titleInput,
    sessionVersion,
    setSessionTitle,
    setTitleLocked,
    setEditingTitle,
    setTitleInput,
    setSessionVersion,
    sessionModelOverride,
    setSessionModelOverride,
    loading,
    isPaused,
  } = chatState;
  const {
    isReceiving,
    executionSteps,
    executionStepsRef, // 小欧 2026-09-10 S13: 透传 RightViewer 快照用
    metaFrames,
    serverTaskId,
    deniedSteps, // 2026-09-06 小欧 B2(方案C): 拒绝/拦截/超时执行轮集合透传 RightViewer → PipelineRenderer — 小欧-2026-09-06
    deniedEntries, // 2026-09-06 小欧 B2(6.4): 被拒工具点名条透传 RightViewer → ToolCallLine — 小欧-2026-09-06
    waitClock, // 2026-09-17 小欧 [46]第五章: 钟面信号透传 RightViewer → PipelineRenderer — 小欧-2026-09-17
  } = chatStreaming;
  const { handleCancel, handleTogglePause } = chatTaskControl;

  return useMemo<SessionPanel[]>(
    () => [
      {
        slot: 'topbar',
        key: 'topbar.header',
        component: (
          <span
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <ChatHeader
              sessionId={sessionId}
              sessionTitle={sessionTitle}
              titleLocked={titleLocked}
              editingTitle={editingTitle}
              titleInput={titleInput}
              sessionVersion={sessionVersion}
              setSessionTitle={setSessionTitle}
              setTitleLocked={setTitleLocked}
              setEditingTitle={setEditingTitle}
              setTitleInput={setTitleInput}
              setSessionVersion={setSessionVersion}
              onEditingStart={handleEditingStart}
              onEditingCancel={handleEditingCancel}
            />
            <span style={{ marginLeft: 12 }}>
              <TopbarStats
                taskCount={total}
                sessionTokens={sessionTokens}
                chainTokens={chainTokens}
                createdAt={sessionTimes.createdAt}
                updatedAt={sessionTimes.updatedAt}
              />
            </span>
            {effective && (
              <span
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <Typography.Text
                  type="secondary"
                  style={{ fontSize: 12, color: Colors.TEXT.PRIMARY }}
                >
                  {effective.display_name ||
                    `${effective.provider} (${effective.model})`}
                </Typography.Text>
                <span
                  style={{
                    width: 4,
                    height: 4,
                    borderRadius: '50%',
                    background:
                      effective.source === 'session'
                        ? Colors.PRIMARY
                        : Colors.BORDER.DEFAULT,
                    display: 'inline-block',
                  }}
                />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {effective.source === 'session' ? '会话' : '全局'}
                </Typography.Text>
              </span>
            )}
          </span>
        ),
        defaultVisible: true,
      },
      {
        slot: 'topbar',
        key: 'topbar.toolbar',
        component: <ChatToolbar onNewSession={handleNewSession} />,
        defaultVisible: true,
      },
      {
        slot: 'left',
        key: 'left.taskList',
        component: (
          <TaskListPanel
            tasks={tasks}
            activeTaskId={activeTaskId}
            onSelect={handleSelectTask}
            loading={tasksLoading}
            latestTaskId={latestTaskId}
            latestTaskRef={latestTaskRef}
            rightOpen={rightOpen}
          />
        ),
        defaultVisible: true,
      },
      {
        slot: 'right',
        key: 'right.viewer',
        component: (
          <RightViewer
            activeTaskId={activeTaskId}
            sessionId={sessionId}
            serverTaskId={serverTaskId}
            liveSteps={executionSteps}
            executionStepsRef={executionStepsRef} // 小欧 2026-09-10 S13: 同步 ref 透传
            highlightToolName={
              // 2026-09-06 小欧 B1: pending 优先, 确认瞬间被清 pending 后由 recentConfirmedTool 承接 2s(F4 高亮空转根治) — 小欧-2026-09-06
              authorizationPending?.toolName ?? recentConfirmedTool ?? null
            }
            frames={metaFrames} // 2026-09-02 小欧: badge 派生输入(startInfo 判定 running)
            deniedSteps={deniedSteps} // 2026-09-06 小欧 B2(方案C): 停齿轮判定 — 小欧-2026-09-06
            deniedEntries={deniedEntries} // 2026-09-06 小欧 B2(6.4): 被拒工具点名条 — 小欧-2026-09-06
            waitClock={waitClock} // 2026-09-17 小欧 [46]第五章: 钟面信号 — 小欧-2026-09-17
            sessionTokens={sessionTokens} // 2026-09-11 小欧: 折叠区4组token显示
            chainTokens={chainTokens}
            // 2026-09-15 小欧 [33]第七章(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
            //   历史任务加载 steps 后写 final.response 到左侧(替代原 onSettledRefresh 从 DB 拉 chat_tasks.response) — 小欧-2026-09-15
            updateTaskResponse={updateTaskResponse}
          />
        ),
        defaultVisible: true,
      },
      {
        slot: 'taskinfo',
        key: 'taskinfo.bar',
        component: (
          <TaskInfoBar
            steps={executionSteps}
            frames={metaFrames}
            detail={selectedDetail}
            sessionId={sessionId}
            liveError={liveError} // 小欧 2026-09-02+09-08: 位4 error 实时源(LiveError 对象形态, error 实时显示唯一位置=taskinfo 第一行, 北京老陈定案) — 小欧-2026-09-08
          />
        ),
        defaultVisible: true,
      },
      {
        slot: 'input',
        key: 'input.chat',
        component: (
          <ChatInput
            sessionId={sessionId}
            loading={loading}
            isReceiving={isReceiving}
            isPaused={isPaused}
            onSend={handleSendWithMode}
            onCancel={handleCancel}
            onTogglePause={handleTogglePause}
            modelPickerSlot={
              <ModelPicker
                sessionId={sessionId}
                sessionTitle={sessionTitle}
                sessionVersion={sessionVersion}
                sessionModelOverride={sessionModelOverride}
                setSessionModelOverride={setSessionModelOverride}
                setSessionVersion={setSessionVersion}
              />
            }
          />
        ),
        defaultVisible: true,
      },
    ],
    [
      handleEditingCancel,
      handleEditingStart,
      sessionId,
      sessionTitle,
      titleLocked,
      editingTitle,
      titleInput,
      sessionVersion,
      setSessionTitle,
      setTitleLocked,
      setEditingTitle,
      setTitleInput,
      setSessionVersion,
      sessionModelOverride,
      setSessionModelOverride,
      total,
      tasksLoading,
      sessionTokens, // 2026-09-01 小欧: 实时/静态双源更新需入依赖, 否则useMemo缓存旧值TopbarStats不刷新
      chainTokens,
      sessionTimes,
      effective,
      handleNewSession,
      tasks,
      activeTaskId,
      handleSelectTask,
      serverTaskId,
      isReceiving,
      executionSteps,
      executionStepsRef, // 小欧 2026-09-10 S13: ref 透传依赖
      metaFrames,
      deniedSteps, // 2026-09-06 小欧 B2(方案C): state 变化需触发面板重渲 — 小欧-2026-09-06
      deniedEntries, // 2026-09-06 小欧 B2(6.4): state 变化需触发面板重渲 — 小欧-2026-09-06
      waitClock, // 2026-09-17 小欧 [46]第五章: heartbeatTs 变化需触发面板重渲 — 小欧-2026-09-17
      selectedDetail,
      loading,
      isPaused,
      handleSendWithMode,
      handleCancel,
      handleTogglePause,
      liveError,
      authorizationPending, // 2026-09-06 小欧 B1: recentConfirmedTool 同入依赖(否则 useMemo 缓存旧值 highlight 不刷新) — 小欧-2026-09-06
      recentConfirmedTool,
      refreshTasks,
      updateTaskResponse, // 2026-09-15 小欧 [33]第七章: RightViewer 透传写 final.response — 小欧-2026-09-15
      latestTaskId, // 2026-09-01 小欧 方案C
      latestTaskRef, // 2026-09-01 小欧 方案C
    ]
  );
}
