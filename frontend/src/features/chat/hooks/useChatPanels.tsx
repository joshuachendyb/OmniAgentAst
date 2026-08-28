// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离panels插槽组装逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useMemo, type Dispatch, type SetStateAction } from 'react';
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
import type { ExecutionStep } from '../../../types/execution';
import type { SessionModelOverride } from '../../../types/chat';
import type {
  TaskDetail,
  SessionTaskItem,
} from '../../../services/api/task.api';
import type { EffectiveModel } from './useModelLayer';
import type { AuthorizationRequest } from '../../../components/AuthorizationModal';
import type { TaskMetaFrames } from '../../../types/sse';

interface UseChatPanelsOptions {
  sessionId: string | null;
  sessionTitle: string;
  titleLocked: boolean;
  editingTitle: boolean;
  titleInput: string;
  sessionVersion: number;
  setSessionTitle: Dispatch<SetStateAction<string>>;
  setTitleLocked: Dispatch<SetStateAction<boolean>>;
  setEditingTitle: Dispatch<SetStateAction<boolean>>;
  setTitleInput: Dispatch<SetStateAction<string>>;
  setSessionVersion: Dispatch<SetStateAction<number>>;
  handleEditingStart: () => void;
  handleEditingCancel: () => void;
  total: number;
  tasksLoading: boolean;
  chainTokens: number | null;
  sessionTimes: { createdAt?: string; updatedAt?: string };
  effective: EffectiveModel | null;
  handleNewSession: () => void;
  tasks: SessionTaskItem[];
  activeTaskId: string | null;
  handleSelectTask: (id: string) => void;
  serverTaskId: string | null;
  isReceiving: boolean;
  executionSteps: ExecutionStep[];
  liveErrorText: string | null;
  authorizationPending: AuthorizationRequest | null;
  metaFrames: TaskMetaFrames;
  selectedDetail: TaskDetail | null;
  loading: boolean;
  isPaused: boolean;
  handleSendWithMode: (
    content: string,
    mode?: 'linked' | 'independent'
  ) => void;
  handleCancel: () => Promise<void>;
  handleTogglePause: () => Promise<void>;
  refreshTasks: () => void;
  sessionModelOverride: SessionModelOverride | null;
  setSessionModelOverride: Dispatch<
    SetStateAction<SessionModelOverride | null>
  >;
}

/**
 * panels 插槽组装 hook：将各子面板组装为 SessionPanel[]，供 SessionLayout 注入（R1-B25）
 * 逻辑与 NewChatContainer 中原 useMemo 一致，未做行为改写
 */
export function useChatPanels(opts: UseChatPanelsOptions): SessionPanel[] {
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
    handleEditingStart,
    handleEditingCancel,
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
    liveErrorText,
    authorizationPending,
    metaFrames,
    selectedDetail,
    loading,
    isPaused,
    handleSendWithMode,
    handleCancel,
    handleTogglePause,
    refreshTasks,
    sessionModelOverride,
    setSessionModelOverride,
  } = opts;

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
              chainTokens={null}
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
        defaultVisible: true, // 2026-08-27 小欧 修复#3: TrustPanel默认可见, 否则信任操作面板永不可触达(违反8.7)
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
      total,
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
      liveErrorText,
      authorizationPending,
      metaFrames,
      selectedDetail,
      loading,
      isPaused,
      handleSendWithMode,
      handleCancel,
      handleTogglePause,
      refreshTasks,
      sessionModelOverride,
      setSessionModelOverride,
    ]
  );
}
