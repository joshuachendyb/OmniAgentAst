// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离panels插槽组装逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-08-29 小强 - 修复#21: TopbarStats chainTokens由硬编码null改为透传真实chainTokens(与依赖数组一致) - 小强-2026-08-29
import { useMemo } from 'react';
import { Typography } from 'antd';
import type { SessionPanel } from '../components/layout/SessionPanelRegistry';
import { ChatInput } from '../components/ChatInput';
import ChatHeader from '../components/ChatHeader';
import ChatToolbar from '../components/ChatToolbar';
import ModelPicker from '../components/ModelPicker';
import { TopbarStats } from '../components/topbar/TopbarStats';
import { TaskListPanel } from '../components/left/TaskListPanel';
import { RightViewer } from '../components/right/RightViewer';
import { TaskInfoBar } from '../components/taskinfo/TaskInfoBar';
import { TrustPanel } from '../components/config/TrustPanel';
import { Colors } from '@/utils/stepStyles';
import type {
  TaskDetail,
  SessionTaskItem,
} from '../../../services/api/task.api';
import type { EffectiveModel } from './useModelLayer';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';
import type { TaskMetaFrames } from '../../../types/sse';
import type { UseChatFacadeReturn } from './useChatFacade';

interface UseChatPanelsOptions {
  chatState: UseChatFacadeReturn['chatState'];
  chatStreaming: UseChatFacadeReturn['chatStreaming'];
  chatTaskControl: UseChatFacadeReturn['chatTaskControl'];
  chatSend: UseChatFacadeReturn['chatSend'];
  liveErrorText: string | null;
  authorizationPending: AuthorizationRequest | null;
  handleAuthorizationConfirm: (
    confirmed: boolean,
    trustSession: boolean
  ) => void;
  tasks: SessionTaskItem[];
  total: number;
  tasksLoading: boolean;
  refreshTasks: () => void;
  effective: EffectiveModel | null;
  sessionTimes: { createdAt?: string; updatedAt?: string };
  activeTaskId: string | null;
  selectedDetail: TaskDetail | null;
  handleSelectTask: (id: string) => void;
  chainTokens: number | null;
  handleNewSession: () => void;
  handleEditingStart: () => void;
  handleEditingCancel: () => void;
  handleSendWithMode: (
    content: string,
    mode?: 'linked' | 'independent'
  ) => void;
}

/**
 * panels 插槽组装 hook：将各子面板组装为 SessionPanel[]，供 SessionLayout 注入（R1-B25）
 * 逻辑与 NewChatContainer 中原 useMemo 一致，未做行为改写
 */
export function useChatPanels(opts: UseChatPanelsOptions): SessionPanel[] {
  const {
    chatState,
    chatStreaming,
    chatTaskControl,
    chatSend,
    liveErrorText,
    authorizationPending,
    handleAuthorizationConfirm,
    tasks,
    total,
    tasksLoading,
    refreshTasks,
    effective,
    sessionTimes,
    activeTaskId,
    selectedDetail,
    handleSelectTask,
    chainTokens,
    handleNewSession,
    handleEditingStart,
    handleEditingCancel,
    handleSendWithMode,
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
    currentResponse,
    metaFrames,
    serverTaskId,
  } = chatStreaming;
  const { handleCancel, handleTogglePause } = chatTaskControl;
  const { handleSend } = chatSend;

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
            <TopbarStats
              taskCount={total}
              chainTokens={chainTokens}
              createdAt={sessionTimes.createdAt}
              updatedAt={sessionTimes.updatedAt}
            />
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
            receiving={isReceiving}
            liveSteps={executionSteps}
            liveErrorText={liveErrorText}
            highlightToolName={authorizationPending?.toolName ?? null}
            onSettledRefresh={refreshTasks}
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
            receiving={isReceiving && activeTaskId === serverTaskId}
            detail={selectedDetail}
          />
        ),
        defaultVisible: true,
      },
      {
        slot: 'config',
        key: 'config.trust',
        component: <TrustPanel sessionId={sessionId} />,
        defaultVisible: true,
      },
      {
        slot: 'input',
        key: 'input.chat',
        component: (
          <ChatInput
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
      currentResponse,
      metaFrames,
      selectedDetail,
      loading,
      isPaused,
      handleSendWithMode,
      handleCancel,
      handleTogglePause,
      liveErrorText,
      authorizationPending,
      handleAuthorizationConfirm,
      refreshTasks,
    ]
  );
}
