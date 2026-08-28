// 编辑历史: 2026-08-22 小欧 - sessionModel 结构化: 接入 ModelPicker 组件(L2 会话级模型覆盖), 解构 sessionModelOverride/setSessionModelOverride
// 编辑历史: 2026-08-26 小欧 - 修复A1(顶栏时间悬浮接线sessionApi.getSession)/A2(右侧默认展开新任务,点击旧任务展开,可收起)/A3(信息条随选中历史任务切换selectedDetail派生): 对应7.1⑤/7.3/7.5/7.6/4.5.1
// 编辑历史: 2026-08-27 小欧 - 修复#3: TrustPanel默认可见(原false致永不可触达); 修复#2: L2经sessionModelOverride同步useModelLayer使顶栏徽标反映会话级模型
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: HITL confirm(trust_session=True)成功后派发omni-trust-changed事件(通知TrustPanel刷新)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 删除未使用解构变量(1)/授权超时改用taskControlApi.confirm(2)/删除调试console.log(3)/anchorTaskId空值守卫(4)/抽离saveChatState(5)
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-6/去框-P0-1: 外层Card套壳→div(flex列/minHeight0/白底), 去boxShadow+border双重留白, 仅保留1处120px高度约束(配合SessionLayout flex收敛)
// 编辑历史: 2026-08-28 小欧 - 根治toast根因: 静态message.destroy改走antdApp.getMessage()上下文实例 - 小欧-2026-08-28
import React, {
  useEffect,
  useCallback,
  useState,
  useRef,
  useMemo,
} from 'react';
import { Typography } from 'antd';
import { getMessage } from '../../utils/antdApp';
import { useSearchParams } from 'react-router-dom';
import {
  API_BASE_URL,
  taskControlApi,
  tokenUsageApi,
  sessionApi,
  executionApi,
  type TaskDetail,
} from '../../services/api';
import { saveChatState } from '../../utils/sessionStorage';

import { ChatInput } from './ChatInput';
import ChatHeader from './ChatHeader';
import ChatToolbar from './ChatToolbar';
import ModelPicker from './ModelPicker';
import AuthorizationModal, {
  AuthorizationRequest,
} from '../AuthorizationModal';
import { useChatFacade } from '../../hooks/chat/useChatFacade';
import { useSessionTasks } from '../../hooks/chat/useSessionTasks';
import { useModelLayer } from '../../hooks/chat/useModelLayer';
import { SessionLayout } from './layout/SessionLayout';
import type { SessionPanel } from './layout/SessionPanelRegistry';
import { TopbarStats } from './topbar/TopbarStats';
import { TaskListPanel } from './left/TaskListPanel';
import { RightViewer } from './right/RightViewer';
import { TaskInfoBar } from './taskinfo/TaskInfoBar';
import { TrustPanel } from './config/TrustPanel';
import { useLoadingMessage } from '../../hooks/useLoadingMessage';
import { useBeforeUnload } from '../../hooks/useBeforeUnload';
import { Colors } from '@/utils/stepStyles';

const NewChatContainer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const chatFacade = useChatFacade({
    baseURL: API_BASE_URL,
    sessionId: searchParams.get('session_id'),
    onError: (message: string) => setLiveErrorText(message),
  });
  const {
    chatState,
    chatStreaming,
    chatSession,
    chatPersistence,
    chatSend,
    chatTaskControl,
  } = chatFacade;

  // 解构chatState
  const {
    // 独立状态
    useStream,
    setUseStream,
    setIsInitialized,
    setSessionJumpLoading,
    setIsMessageListLoading,
    retryCount,
    setRetryCount,
    setIsRenderingMessages,
    isPaused,
    messages,
    loading,
    sessionId,
    sessionTitle,
    setSessionTitle,
    sessionVersion,
    setSessionVersion,
    titleLocked,
    setTitleLocked,
    editingTitle,
    setEditingTitle,
    titleInput,
    setTitleInput,
    sessionModelOverride,
    setSessionModelOverride,
    // Refs
    messagesEndRef,
    messagesRef,
    isPausedRef,
    executionStepsRef,
    userScrolledUpRef,
    isLoadingHistoryRef,
  } = chatState;

  // 解构chatStreaming
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    metaFrames,
    serverTaskId,
  } = chatStreaming;

  // 解构chatTaskControl
  const { handleCancel, handleTogglePause } = chatTaskControl;

  // 解构chatSend
  const { handleSend } = chatSend;

  // 【v3.4新增 2026-06-09 小沈】授权弹窗状态
  const [authorizationPending, setAuthorizationPending] =
    useState<AuthorizationRequest | null>(null);
  const authorizationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  // 【v3.4新增 2026-06-09 小沈】授权请求回调（从useChatCallbacks传递）
  useEffect(() => {
    // 通过自定义事件监听授权请求
    const handleAuthorizationRequired = (
      event: CustomEvent<Record<string, unknown>>
    ) => {
      // 后端发送snake_case字段，前端AuthorizationModal使用camelCase
      const rawData = event.detail;
      setAuthorizationPending({
        confirmId: rawData.confirm_id as string,
        toolName: rawData.tool_name as string,
        params: (rawData.params ?? {}) as Record<string, unknown>,
        safetyLevel: rawData.safety_level as string,
      });
    };

    window.addEventListener(
      'authorization_required',
      handleAuthorizationRequired as EventListener
    );
    return () => {
      window.removeEventListener(
        'authorization_required',
        handleAuthorizationRequired as EventListener
      );
    };
  }, []);

  // 【v3.4新增 2026-06-09 小沈】授权超时自动关闭（60秒与后端一致）
  useEffect(() => {
    if (authorizationPending) {
      authorizationTimeoutRef.current = setTimeout(() => {
        // 2026-08-27 小欧 三堂会审: 授权超时自动拒绝改用 taskControlApi.confirm(false,false)
        taskControlApi.confirm(authorizationPending.confirmId, false, false).catch(() => undefined);
        setAuthorizationPending(null);
      }, 60000);
    }
    return () => {
      if (authorizationTimeoutRef.current) {
        clearTimeout(authorizationTimeoutRef.current);
        authorizationTimeoutRef.current = null;
      }
    };
  }, [authorizationPending]);

  // chatPersistence 直接使用（restoreState）

  // 使用useLoadingMessage Hook管理loading
  const { show: showLoading, hide: hideLoading } = useLoadingMessage({
    duration: 0,
  });

  // 新建会话
  const handleNewSession = useCallback(() => {
    chatSession.handleNewSession(0);
  }, [chatSession]);

  // —— 8.3.3 插槽化组装新增状态与数据源 ——
  // 【小欧 2026-08-26 修复 A2】右侧查看区(对话主体)默认展开，否则发消息后主屏空白(7.3/7.5)
  const [rightOpen, setRightOpen] = useState(true);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [chainTokens, setChainTokens] = useState<number | null>(null); // 顶栏会话累计 token（A6 链口径）
  const [liveErrorText, setLiveErrorText] = useState<string | null>(null);
  const { tasks, total, loading: tasksLoading, refresh: refreshTasks } = useSessionTasks(sessionId);
  const { effective } = useModelLayer({
    sessionId,
    sessionTitle,
    sessionVersion,
    setSessionVersion,
    sessionModelOverride, // 2026-08-27 小欧 修复#2: 传入L2覆盖使顶栏徽标反映会话级模型(修复L2死代码)
  });

  // 【小欧 2026-08-26 修复 A1】会话创建/更新时间(7.1⑤ 顶栏悬浮数据源)
  const [sessionTimes, setSessionTimes] = useState<{
    createdAt?: string;
    updatedAt?: string;
  }>({});
  useEffect(() => {
    if (!sessionId) return;
    sessionApi
      .getSession(sessionId)
      .then((s) => setSessionTimes({ createdAt: s.created_at, updatedAt: s.updated_at }))
      .catch(() => undefined);
  }, [sessionId]);

  // 【小欧 2026-08-27 修复#42】切换会话时重置跨会话泄漏状态, 避免RightViewer向旧会话任务发REST/残留统计
  useEffect(() => {
    setActiveTaskId(null);
    setSelectedDetail(null);
    setChainTokens(null);
    setLiveErrorText(null);
  }, [sessionId]);

  // 【小欧 2026-08-26 修复 A3】任务信息条随左列点击切换：选中历史任务时拉取其详情，
  // 注入 TaskInfoBar 作为动态信息来源(7.6 目标"当前任务=点击查看的历史任务")
  const [selectedDetail, setSelectedDetail] = useState<TaskDetail | null>(null);
  useEffect(() => {
    if (activeTaskId && activeTaskId !== serverTaskId) {
      // 2026-08-27 小欧 修复#43: 增加cancelled守卫, 避免快速连点任务时旧响应覆盖新数据
      let cancelled = false;
      executionApi
        .getTaskDetail(activeTaskId)
        .then((d) => {
          if (!cancelled) setSelectedDetail(d);
        })
        .catch(() => {
          if (!cancelled) setSelectedDetail(null);
        });
      return () => {
        cancelled = true;
      };
    } else {
      setSelectedDetail(null);
    }
  }, [activeTaskId, serverTaskId]);

  // 【小欧 2026-08-27 修复#6】新会话首个任务自动激活: serverTaskId 就绪但 activeTaskId 尚空时跟随,
  // 避免右侧执行详情/任务信息条不随首个实时任务联动(历史点击手动选择时不覆盖)
  // 2026-08-28 小欧 v1.3: 纯历史会话(serverTaskId为空)加载后默认选中列表首项, 任务信息框显第一个任务(用户三态需求②)
  useEffect(() => {
    if (activeTaskId) return;
    if (serverTaskId) {
      setActiveTaskId(serverTaskId);
      return;
    }
    if (!isReceiving && tasks.length > 0) {
      setActiveTaskId(tasks[0].task_id);
    }
  }, [serverTaskId, activeTaskId, isReceiving, tasks]);

  // 任务结束沿（isReceiving true→false）统一刷新：任务列表 / 顶栏链累计 token
  const prevReceivingRef = useRef(false);
  useEffect(() => {
    if (prevReceivingRef.current && !isReceiving) {
      void refreshTasks();
      if (sessionId) {
        const anchorTaskId = serverTaskId ?? tasks[0]?.task_id;
        // 2026-08-27 小欧 三堂会审: 空值守卫, 无锚定任务则跳过getChainTokens
        if (!anchorTaskId) {
          prevReceivingRef.current = isReceiving;
          return;
        }
        tokenUsageApi
          .getChainTokens({ sessionId, taskId: anchorTaskId })
          .then((r) =>
            setChainTokens(
              r.chain_accumulated_tokens?.total_tokens ?? r.total_tokens
            )
          )
          .catch(() => undefined);
      }
    }
    prevReceivingRef.current = isReceiving;
  }, [isReceiving, refreshTasks, sessionId, tasks]);

  const handleSelectTask = useCallback((id: string) => {
    setActiveTaskId(id);
    setRightOpen(true);
  }, []);

  const handleSendWithMode = useCallback(
    (content: string, mode?: 'linked' | 'independent') => {
      setLiveErrorText(null);
      void handleSend(content, mode);
    },
    [handleSend]
  );

  // 滚动控制参数
  const SCROLL_THRESHOLD = 150;

  // 延迟滚动
  const scrollToBottomDelayed = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, [messagesEndRef]);

  // 同步 isPaused 状态到 ref
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused, isPausedRef]);

  // 自动滚动到底部 - 修复清理后缺失的自动滚动功能
  useEffect(() => {
    scrollToBottomDelayed();
  }, [messages, currentResponse, executionSteps, scrollToBottomDelayed]);

  // 同步executionSteps到ref - 修复清理后缺失的同步功能
  useEffect(() => {
    executionStepsRef.current = executionSteps;
  }, [executionSteps, executionStepsRef]); // ✅ 加上executionStepsRef依赖

  // 滚动位置监听
  useEffect(() => {
    const container = messagesEndRef.current?.parentElement;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      userScrolledUpRef.current = distanceFromBottom > SCROLL_THRESHOLD;
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [messagesEndRef, userScrolledUpRef]);

  // 当页面从隐藏状态变为显示时也自动滚动到底部
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        scrollToBottomDelayed();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [currentResponse, executionSteps, isReceiving, scrollToBottomDelayed]);

  // 保存状态（用于beforeunload）
  const handleSaveBeforeUnload = useCallback(() => {
    if (!isReceiving || !sessionId) return;

    let messagesToSave = messagesRef.current;
    if (executionStepsRef.current.length > 0) {
      messagesToSave = messagesRef.current.map((msg, idx) => {
        if (
          msg.role === 'assistant' &&
          msg.isStreaming &&
          idx === messagesRef.current.length - 1
        ) {
          return {
            ...msg,
            executionSteps: executionStepsRef.current,
          };
        }
        return msg;
      });
    }

    const state = {
      messages: messagesToSave,
      sessionId,
      sessionTitle,
      timestamp: Date.now(),
      scrollPosition: 0,
      isPaused,
      isReceiving,
    };

    // 2026-08-27 小欧 三堂会审: 会话状态保存下沉至 saveChatState(容量阈值/降级/容错)
    saveChatState(state);
  }, [
    isReceiving,
    sessionId,
    sessionTitle,
    isPaused,
    executionStepsRef,
    messagesRef,
  ]);

  // 使用useBeforeUnload Hook统一管理
  useBeforeUnload({
    shouldSave: !!isReceiving && !!sessionId,
    saveData: handleSaveBeforeUnload,
    showDialog: true,
    dialogMessage: '正在接收消息，确定要离开吗？',
  });

  // 组件卸载前清理
  useEffect(() => {
    return () => {
      getMessage().destroy('session-load');
    };
  }, []);

  // 会话状态持久化 - 使用chatSession.initializeSession
  // 仅当searchParams变化时才重新初始化（URL的sessionId变化）
  useEffect(() => {
    const onLoadingStart = () => {
      setSessionJumpLoading(true);
      showLoading('正在加载会话...', 'session-load');
    };

    const onLoadingEnd = () => {
      hideLoading('session-load');
      setSessionJumpLoading(false);
    };

    const onRenderStart = () => {
      setIsRenderingMessages(true);
    };

    const onRenderEnd = () => {
      setIsRenderingMessages(false);
    };

    const onMessageListLoadingStart = () => {
      // No-op: rendered inside initializeSession
    };

    const onMessageListLoadingEnd = () => {
      setIsMessageListLoading(false);
    };

    chatSession.initializeSession({
      searchParams,
      retryCount,
      setRetryCount,
      isLoadingHistoryRef,
      setIsInitialized,
      restoreState: chatPersistence.restoreState,
      onLoadingStart,
      onLoadingEnd,
      onRenderStart,
      onRenderEnd,
      onMessageListLoadingStart,
      onMessageListLoadingEnd,
    });
    // ✅ 仅保留searchParams，避免重复执行initializeSession（其他函数通过useCallback保持稳定）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 组件卸载时清理loading
  useEffect(() => {
    return () => {
      hideLoading('session-load');
    };
  }, [hideLoading]);

  // 全局快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + N 新建会话
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        handleNewSession();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleNewSession]);

  // ChatHeader回调
  const handleEditingStart = useCallback(() => {
    if (!editingTitle && sessionId) {
      setTitleInput(sessionTitle || '');
    }
    setEditingTitle(true);
  }, [editingTitle, sessionId, sessionTitle, setTitleInput, setEditingTitle]);

  const handleEditingCancel = useCallback(() => {
    setEditingTitle(false);
  }, [setEditingTitle]);

  // 【v3.4新增 2026-06-09 小沈】授权确认处理
  const handleAuthorizationConfirm = useCallback(
    async (confirmed: boolean, trustSession: boolean) => {
      if (!authorizationPending) {
        return;
      }

      try {
        await taskControlApi.confirm(
          authorizationPending.confirmId,
          confirmed,
          trustSession
        );
        // 2026-08-27 小欧 三堂会审: HITL confirm(trust_session=True)写入成功后派发事件, 通知信任面板刷新
        if (trustSession && sessionId) {
          window.dispatchEvent(new CustomEvent('omni-trust-changed', { detail: { sessionId } }));
        }
      } catch (error) {
        console.error('[Authorization] 确认失败:', error);
      } finally {
        setAuthorizationPending(null);
      }
    },
    [authorizationPending]
  );

  // —— 8.3.3 panels 组装（prop 注入 SessionLayout，R1-B25）——
  const panels = useMemo<SessionPanel[]>(
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
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12, color: Colors.TEXT.PRIMARY }}>
                  {effective.display_name || `${effective.provider} (${effective.model})`}
                </Typography.Text>
                <span style={{ width: 4, height: 4, borderRadius: '50%', background: effective.source === 'session' ? Colors.PRIMARY : Colors.BORDER.DEFAULT, display: 'inline-block' }} />
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

  return (
    <div
      style={{
        height: 'calc(100vh - 120px)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        padding: '0 8px 8px',
        background: Colors.BG.PRIMARY,
        minWidth: 0,
      }}
    >
      <SessionLayout
        panels={panels}
        rightOpen={rightOpen}
        onToggleRight={() => setRightOpen((v) => !v)}
      />
      <AuthorizationModal
        visible={!!authorizationPending}
        request={authorizationPending}
        onConfirm={handleAuthorizationConfirm}
      />
    </div>
  );
};

export default NewChatContainer;
