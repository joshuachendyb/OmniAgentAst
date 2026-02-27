/**
 * NewChatContainer组件 - 升级版对话容器
 *
 * 功能：
 * - 完整会话管理（新建会话、编辑标题、历史记录加载）
 * - SSE流式输出 + 执行步骤可视化
 * - 安全检测v2.0（基于score的4级响应）
 * - 任务中断控制
 * - 标题管理优化（版本控制、锁定状态、来源标记）
 *
 * @author 小新
 * @version 3.1.0
 * @since 2026-02-23
 * @update 2026-02-25 新增版本号控制、标题锁定状态、409冲突处理
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Input,
  Button,
  Card,
  List,
  Tag,
  Space,
  message,
  Badge,
  Tooltip,
} from 'antd';
import {
  SendOutlined,
  RobotOutlined,
  PlusOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  InfoCircleOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { sessionApi, ChatMessage, API_BASE_URL } from '../../services/api';
import { securityApi } from '../../services/api';
import MessageItem from './MessageItem';
import DangerConfirmModal from '../DangerConfirmModal';
import SecurityAlert from '../SecurityAlert';
import { showSecurityNotification } from '../SecurityNotification';
import { getRiskLevel } from '../../types/security';
import { useSSE, ExecutionStep } from '../../utils/sse';

const { TextArea } = Input;

// ⭐ 常量配置
const SESSION_EXPIRY_TIME = 5 * 60 * 1000; // 5分钟

// ⭐ 防抖函数（简单实现，不依赖lodash）
const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>): void => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, delay);
  };
};

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  executionSteps?: ExecutionStep[];
  isStreaming?: boolean;
  model?: string;
}

/**
 * NewChatContainer - 升级版对话容器
 *
 * 整合功能：
 * - Chat/index.tsx: 会话管理、安全检测、状态持久化
 * - ChatContainer: useSSE hook、ExecutionPanel、流式开关
 *
 * @author 小新
 * @version 3.0.0
 */
const NewChatContainer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>('新会话');
  const [sessionVersion, setSessionVersion] = useState<number>(1); // ⭐ 新增：会话版本号
  const [titleLocked, setTitleLocked] = useState<boolean>(false); // ⭐ 新增：标题锁定状态
  const [titleSource, setTitleSource] = useState<'user' | 'auto'>('auto'); // ⭐ 新增：标题来源
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');
  const [lastSavedTitle, setLastSavedTitle] = useState<string>(''); // ⭐ 新增：记录最后保存的标题
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 流式输出相关状态
  const [showExecution, setShowExecution] = useState(true);
  const [useStream, setUseStream] = useState(true); // 默认使用流式

  // 安全检测v2.0状态
  const [dangerModalVisible, setDangerModalVisible] = useState(false);
  const [dangerCommand, setDangerCommand] = useState('');
  const [dangerScore, setDangerScore] = useState(0);
  const [dangerMessage, setDangerMessage] = useState('');
  const [pendingMessage, setPendingMessage] = useState<Message | null>(null);
  const [checkingDanger, setCheckingDanger] = useState(false);
  const [blockedCommand, setBlockedCommand] = useState<{
    command: string;
    score: number;
    message: string;
  } | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // P1级别优化：新增状态变量
  type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [_sessionJumpLoading, setSessionJumpLoading] = useState(false);
  const [retryCount, setRetryCount] = useState<Record<string, number>>({});
  const [_lastSaveTime, setLastSaveTime] = useState<number>(0);
  const [_isSavingTitle, setIsSavingTitle] = useState(false);

  // SSE Hook配置（用于流式输出）
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    setTaskId,
    serverTaskId,
  } = useSSE(
    {
      baseURL: 'http://localhost:8000/api/v1',
      sessionId: sessionId || 'default-session',
    },
    // onStep - 收到执行步骤
    useCallback((step: ExecutionStep) => {
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
          lastMessage.isStreaming
        ) {
          const updatedSteps = [...(lastMessage.executionSteps || []), step];
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            executionSteps: updatedSteps,
          };
          return updated;
        }
        return prev;
      });
    }, []),
    // onChunk - 收到内容片段
    useCallback((chunk: string) => {
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
          lastMessage.isStreaming
        ) {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            content: lastMessage.content + chunk,
          };
          return updated;
        }
        return prev;
      });
    }, []),
    // onComplete - 流式完成
    useCallback(
      async (fullResponse: string, model?: string) => {
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === 'assistant') {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              content: fullResponse,
              isStreaming: false,
              model: model || lastMessage.model,
            };
            return updated;
          }
          return prev;
        });

        // 保存消息到会话
        const currentPending = pendingMessage;
        if (sessionId && currentPending) {
          try {
            // 保存用户消息
            await sessionApi.saveMessage(sessionId, {
              role: 'user',
              content: currentPending.content,
            });

            // 保存AI回复
            await sessionApi.saveMessage(sessionId, {
              role: 'assistant',
              content: fullResponse,
            });

            // 🔴 修复：确保会话标题持久化
            if (
              sessionTitle &&
              sessionTitle.trim() &&
              sessionTitle !== '新会话'
            ) {
              debouncedSaveTitle(sessionId, sessionTitle);
            }

            console.log('✅ 消息和标题保存成功');
          } catch (saveError) {
            console.error('保存消息或标题失败:', saveError);
          }
        }

        setLoading(false);
        setPendingMessage(null);
      },
      [sessionId, pendingMessage]
    ),
    // onError - 流式错误
    useCallback((error: string) => {
      console.error('SSE流式错误:', error);

      // 🔴 修复：更好的用户反馈
      message.error({
        content: `AI响应失败: ${error}`,
        duration: 5,
      });

      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            content: lastMessage.content || '抱歉，发生了错误',
            isStreaming: false,
          };
          return updated;
        }
        return prev;
      });
      setLoading(false);
    }, [])
  );

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentResponse, executionSteps]);

  // ============================================
  // 会话状态持久化
  // ============================================
  const STORAGE_KEY = 'chat_session_state';

  const saveState = () => {
    // 🔴 修复：只要有会话ID就保存，即使消息为空
    if (sessionId) {
      const state = {
        messages,
        sessionId,
        sessionTitle,
        timestamp: Date.now(), // 🔴 修复：添加时间戳，用于判断新旧
        scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      console.log('💾 保存会话状态:', sessionId, sessionTitle);
    }
  };

  const restoreState = () => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        // 🔴 修复：检查时间戳，避免恢复过时的状态（超过5分钟）
        const currentTime = Date.now();
        const savedTime = state.timestamp || 0;
        const timeDiff = currentTime - savedTime;

        // 只恢复5分钟内的状态
        if (timeDiff > SESSION_EXPIRY_TIME) {
          console.log('🕒 会话状态已过期，跳过恢复');
          sessionStorage.removeItem(STORAGE_KEY);
          return false;
        }

        if (state.sessionId) {
          setMessages(state.messages || []);
          setSessionId(state.sessionId);
          setSessionTitle(state.sessionTitle || '会话');
          setTimeout(() => {
            if (messagesEndRef.current?.parentElement) {
              messagesEndRef.current.parentElement.scrollTop =
                state.scrollPosition || 0;
            }
          }, 100);
          console.log('🔄 恢复会话状态:', state.sessionId, state.sessionTitle);
          return true;
        }
      } catch (e) {
        console.warn('恢复会话状态失败:', e);
        sessionStorage.removeItem(STORAGE_KEY); // 🔴 修复：清除损坏的数据
      }
    }
    return false;
  };

  // 页面可见性变化时保存状态
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        saveState();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [messages, sessionId, sessionTitle]);

  // P1级别优化：状态验证和同步机制
  useEffect(() => {
    if (!sessionId || !isInitialized) return;

    const validateAndSyncState = async () => {
      try {
        // 验证前端状态与后端一致性
        const sessionData = await sessionApi.getSessionMessages(sessionId);

        // 获取后端返回的正确标题
        const backendTitle = getSessionTitle(sessionData, '会话');

        // 如果前端标题与后端不一致，强制同步
        if (backendTitle !== sessionTitle && backendTitle !== '会话') {
          console.warn('🔄 标题不一致，强制同步:', {
            frontend: sessionTitle,
            backend: backendTitle,
          });
          setSessionTitle(backendTitle);
        }

        // 验证消息数量
        if (sessionData.messages && sessionData.messages.length > 0) {
          const frontendMsgCount = messages.filter(
            (m) => m.role !== 'system'
          ).length;
          const backendMsgCount = sessionData.messages.length;

          if (Math.abs(frontendMsgCount - backendMsgCount) > 2) {
            console.warn('🔄 消息数量差异较大，建议刷新页面');
          }
        }
      } catch (error) {
        console.warn('状态验证失败:', error);
        // 状态验证失败不影响用户体验，静默处理
      }
    };

    // 每2分钟验证一次状态一致性
    const intervalId = setInterval(
      () => {
        validateAndSyncState();
      },
      2 * 60 * 1000
    );

    return () => clearInterval(intervalId);
  }, [sessionId, sessionTitle, messages, isInitialized]);

  // 全局快捷键 - 前端小新代修改 UX-G02: 全局快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Enter 发送消息
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSend();
      }
      // Ctrl/Cmd + K 清空对话
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        handleClear();
      }
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
  }, [inputValue, loading]);

  // ============================================
  // 网络连接检查
  // ============================================

  /**
   * 检查网络连接状态
   */
  const checkNetworkConnection = async (): Promise<boolean> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'HEAD',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      clearTimeout(timeoutId);
      console.warn('网络连接检查失败:', error);
      return false;
    }
  };

  // ============================================
  // 统一的标题管理函数
  // ============================================

  /**
   * 获取会话标题 - 统一管理所有标题来源
   * 优先级：1. API返回的title > 2. 用户修改过的标题 > 3. 消息内容 > 4. 默认标题
   */
  const getSessionTitle = (
    sessionData: { title?: string; messages?: any[] },
    defaultTitle: string = '会话'
  ): string => {
    // 1. 最高优先级：API返回的title字段
    if (sessionData.title && sessionData.title.trim()) {
      return sessionData.title.trim();
    }

    // 2. 次优先级：消息内容（只在没有API title时使用）
    if (sessionData.messages && sessionData.messages.length > 0) {
      const firstMessage = sessionData.messages[0];
      if (firstMessage?.content) {
        // 只取前30个字符，避免过长
        const contentTitle = firstMessage.content.substring(0, 30).trim();
        if (contentTitle) {
          return contentTitle;
        }
      }
    }

    // 3. 默认标题
    return defaultTitle;
  };

  /**
   * 生成新会话标题 - 智能生成有意义的标题
   * 🔄 优化：添加更多时间细分，使标题更精确
   */
  const generateNewSessionTitle = (): string => {
    const now = new Date();
    const hours = now.getHours();
    let timeOfDay = '';

    // 更精确的时间段划分
    if (hours >= 5 && hours < 8) timeOfDay = '清晨';
    else if (hours >= 8 && hours < 12) timeOfDay = '上午';
    else if (hours >= 12 && hours < 14) timeOfDay = '午间';
    else if (hours >= 14 && hours < 18) timeOfDay = '下午';
    else if (hours >= 18 && hours < 21) timeOfDay = '晚间';
    else if (hours >= 21 && hours < 24) timeOfDay = '深夜';
    else timeOfDay = '深夜'; // 0-5点

    const dateStr = `${now.getMonth() + 1}月${now.getDate()}日`;
    return `${dateStr} ${timeOfDay}会话 ${hours}:${now.getMinutes().toString().padStart(2, '0')}`;
  };

  // ⭐ 确保标题持久化到后端（带防抖、重试、版本冲突处理）
  const ensureTitlePersisted = async (sessionId: string, title: string) => {
    if (!sessionId || !title.trim()) return;

    // ⭐ 防抖检查：标题未变化时跳过保存
    if (title === lastSavedTitle) {
      console.log('标题未变化，跳过保存');
      return;
    }

    // ⭐ 防抖检查：正在保存时跳过重复请求
    if (saveStatus === 'saving') {
      console.log('正在保存中，跳过重复请求');
      return;
    }

    const retryKey = `title-save-${sessionId}`;
    const currentRetry = retryCount[retryKey] || 0;

    try {
      setSaveStatus('saving');
      setIsSavingTitle(true);

      // 如果标题不是默认标题，保存到后端
      if (title !== '新会话' && title !== '会话') {
        // ⭐ 直接使用状态中的版本号
        const response = await sessionApi.updateSession(
          sessionId,
          title.trim(),
          sessionVersion
        );

        // ⭐ 更新本地版本号
        if (response.version) {
          setSessionVersion(response.version);
        }

        // ⭐ 更新最后保存的标题
        setLastSavedTitle(title);

        console.log(
          '💾 标题持久化成功:',
          sessionId,
          title,
          '版本:',
          sessionVersion
        );
      }

      // 更新本地sessionStorage
      saveState();

      // 保存成功
      setSaveStatus('saved');
      setIsSavingTitle(false);
      setLastSaveTime(Date.now());
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

      // 2秒后恢复到idle状态
      setTimeout(() => {
        setSaveStatus('idle');
      }, 2000);
    } catch (error: any) {
      console.warn('标题持久化失败:', error);

      // ⭐ 处理409版本冲突错误
      if (error?.response?.status === 409) {
        const errorMsg =
          error.response.data?.detail || '版本冲突，该会话已被其他人修改';
        message.error(errorMsg);

        // ⭐ 从服务器重新获取最新数据
        try {
          const sessionData = await sessionApi.getSessionMessages(sessionId);
          if (sessionData.version) {
            setSessionVersion(sessionData.version);
          }
          if (sessionData.title) {
            setSessionTitle(sessionData.title);
          }
          if (sessionData.title_locked !== undefined) {
            setTitleLocked(sessionData.title_locked);
          }
          if (sessionData.title_source) {
            setTitleSource(sessionData.title_source);
          }

          message.info('已自动同步最新数据，请重试');
        } catch (syncError) {
          console.error('同步最新数据失败:', syncError);
        }

        setSaveStatus('error');
        setIsSavingTitle(false);
        return;
      }

      // 其他错误：重试机制 - 最多3次
      setSaveStatus('error');
      setIsSavingTitle(false);

      if (currentRetry < 3) {
        const newRetry = currentRetry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
        message.warning(`保存失败，正在重试 (${newRetry}/3)...`);

        // 延迟1秒后重试
        setTimeout(() => {
          debouncedSaveTitle(sessionId, title);
        }, 1000);
      } else {
        // 超过重试次数，显示错误
        message.error('保存失败，请检查网络后重试');
        setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
      }
    }
  };

  // ⭐ 防抖版本的保存标题函数
  const debouncedSaveTitle = useCallback(
    debounce(async (sessionId: string, title: string) => {
      await ensureTitlePersisted(sessionId, title);
    }, 1000),
    []
  );

  // ============================================
  // 加载历史会话
  // ============================================
  useEffect(() => {
    const loadSession = async () => {
      const urlSessionId = searchParams.get('session_id');

      // 🔴 修复1: URL参数绝对优先 - 清除旧的sessionStorage
      if (urlSessionId) {
        // P1级别优化：添加会话跳转加载状态
        setSessionJumpLoading(true);
        message.loading({
          content: '正在加载会话...',
          key: 'session-load',
          duration: 0,
        });

        // 清除旧的sessionStorage，避免干扰
        sessionStorage.removeItem(STORAGE_KEY);

        const retryKey = `session-load-${urlSessionId}`;
        const currentRetry = retryCount[retryKey] || 0;

        try {
          const sessionData = await sessionApi.getSessionMessages(urlSessionId);
          if (sessionData.messages && sessionData.messages.length > 0) {
            setSessionId(urlSessionId);
            setMessages(
              sessionData.messages.map((m: any) => ({
                id: m.id?.toString() || Date.now().toString(),
                role: m.role,
                content: m.content,
                timestamp: new Date(m.timestamp),
              }))
            );

            // ⭐ 2026-02-25 更新：加载新增字段
            const title = getSessionTitle(sessionData, '会话');
            setSessionTitle(title);

            // ⭐ 设置新字段
            if (sessionData.version !== undefined) {
              setSessionVersion(sessionData.version);
            }
            if (sessionData.title_locked !== undefined) {
              setTitleLocked(sessionData.title_locked);
            }
            if (sessionData.title_source) {
              setTitleSource(sessionData.title_source);
            }

            // 加载成功
            setSessionJumpLoading(false);
            message.success({ content: '会话加载成功', key: 'session-load' });
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

            console.log(
              '🔵 从URL加载会话:',
              urlSessionId,
              '标题:',
              title,
              '版本:',
              sessionData.version
            );
            return;
          }
        } catch (error) {
          console.warn('加载URL会话失败:', error);

          // 重试机制 - 最多3次
          if (currentRetry < 3) {
            const newRetry = currentRetry + 1;
            setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
            message.warning({
              content: `加载失败，正在重试 (${newRetry}/3)...`,
              key: 'session-load',
              duration: 0,
            });

            // 延迟1秒后重试
            setTimeout(() => {
              loadSession();
            }, 1000);
          } else {
            // 超过重试次数，显示错误
            setSessionJumpLoading(false);
            message.error({
              content: '加载会话失败，请检查网络后重试',
              key: 'session-load',
            });
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
          }
        }
      }

      // 🔴 修复3: 只有在没有URL参数时才考虑sessionStorage
      if (!urlSessionId) {
        const restored = restoreState();
        if (restored) {
          console.log('🟢 从缓存恢复会话状态');
          // 如果是从缓存恢复，也要关闭加载状态
          setSessionJumpLoading(false);
          message.destroy('session-load');
          return;
        }
      }

      // 🔴 修复4: 如果都没有，加载加载最近会话
      try {
        const response = await sessionApi.listSessions(1, 1);
        if (response.sessions && response.sessions.length > 0) {
          const latestSession = response.sessions[0];
          const sessionData = await sessionApi.getSessionMessages(
            latestSession.session_id
          );
          setSessionId(latestSession.session_id);

          // 🔴 修复5: 使用统一的标题管理函数
          const title = getSessionTitle(
            {
              title: latestSession.title, // 优先使用listSessions返回的title
              messages: sessionData.messages,
            },
            '会话'
          );
          setSessionTitle(title);

          // ⭐ 2026-02-25 更新：加载新增字段
          if (latestSession.version !== undefined) {
            setSessionVersion(latestSession.version);
          }
          if (latestSession.title_locked !== undefined) {
            setTitleLocked(latestSession.title_locked);
          }
          if (latestSession.title_source) {
            setTitleSource(latestSession.title_source);
          }

          if (sessionData.messages && sessionData.messages.length > 0) {
            setMessages(
              sessionData.messages.map((m: any) => ({
                id: m.id?.toString() || Date.now().toString(),
                role: m.role,
                content: m.content,
                timestamp: new Date(m.timestamp),
              }))
            );
          }
          console.log(
            '🟡 加载最近会话:',
            latestSession.session_id,
            '标题:',
            title,
            '版本:',
            latestSession.version
          );

          // 关闭加载状态
          setSessionJumpLoading(false);
          message.destroy('session-load');
        }
      } catch (error) {
        console.warn('加载最近会话失败:', error);
        // 即使失败也关闭加载状态
        setSessionJumpLoading(false);
        message.destroy('session-load');
      }

      // 标记初始化完成
      setIsInitialized(true);
    };

    loadSession();
  }, [searchParams]);

  // ============================================
  // 消息发送逻辑
  // ============================================

  /**
   * 执行流式消息发送（使用useSSE hook）
   *
   * @update 2026-02-23 修复：添加assistant消息占位，确保onStep/onChunk能正确更新
   */
  const executeStreamSend = async (userMessage: Message) => {
    setLoading(true);
    clearSteps();

    // 【修复问题2】生成taskId用于中断功能
    const taskId = crypto.randomUUID();
    setCurrentTaskId(taskId);
    setTaskId(taskId);

    // 【关键修复】先创建assistant消息占位，设置isStreaming=true
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      executionSteps: [],
      isStreaming: true,
      model: undefined, // 前端小新代修改：明确设置可选属性
    };
    setMessages((prev) => [...prev, assistantMessage]);

    // 保存待发送消息，用于onComplete时保存到会话
    setPendingMessage(userMessage);

    // 发送流式请求
    sendStreamMessage(userMessage.content);
  };

  /**
   * 任务中断处理 - 前端小新代修改
   */
  const handleInterrupt = async () => {
    const taskIdToCancel = serverTaskId || currentTaskId;
    if (taskIdToCancel) {
      try {
        message.info('正在中断任务...');
        await fetch(`${API_BASE_URL}/chat/stream/cancel/${taskIdToCancel}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        message.success('任务中断请求已发送');
      } catch (error) {
        message.error('发送中断请求失败: ' + (error as Error).message);
      }
    }
  };

  /**
   * 任务暂停/继续
   */
  const handleTogglePause = () => {
    setIsPaused(!isPaused);
    message.info('暂停功能后端暂未实现，仅显示UI状态');
  };

  /**
   * 发送消息（带安全检测v2.0）
   */
  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    // 🔴 修复：添加输入长度限制和验证
    if (inputValue.trim().length > 5000) {
      message.warning('消息过长，请精简到5000字符以内');
      return;
    }

    // 🔴 修复：网络连接检查
    setLoading(true);
    try {
      const isNetworkOK = await checkNetworkConnection();
      if (!isNetworkOK) {
        message.error('网络连接异常，请检查网络后重试');
        setLoading(false);
        return;
      }
    } catch (error) {
      console.warn('网络检查异常:', error);
    } finally {
      setLoading(false);
    }

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      try {
        const newSession = await sessionApi.createSession(
          inputValue.trim().substring(0, 50)
        );
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        console.log('创建新会话:', currentSessionId);
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : '网络错误';
        message.error(`创建会话失败: ${errMsg}`);
        console.error('创建会话失败:', error);
        return; // 🔴 修复：创建会话失败时停止发送
      }
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setBlockedCommand(null);

    // 安全检测v2.0
    setCheckingDanger(true);
    try {
      const checkResult = await securityApi.checkCommand(userMessage.content);
      setCheckingDanger(false);

      if (!checkResult.success || !checkResult.data) {
        console.warn('安全检测失败:', checkResult.error);
        await executeStreamSend(userMessage);
        return;
      }

      const { score, message: riskMessage } = checkResult.data;
      const riskLevel = getRiskLevel(score);

      switch (riskLevel.level) {
        case 'SAFE':
          await executeStreamSend(userMessage);
          break;
        case 'MEDIUM':
          showSecurityNotification(userMessage.content, score, riskMessage);
          await executeStreamSend(userMessage);
          break;
        case 'HIGH':
          setDangerCommand(userMessage.content);
          setDangerScore(score);
          setDangerMessage(riskMessage);
          setPendingMessage(userMessage);
          setDangerModalVisible(true);
          break;
        case 'CRITICAL':
          setBlockedCommand({
            command: userMessage.content,
            score,
            message: riskMessage,
          });
          setMessages((prev) =>
            prev.filter((msg) => msg.id !== userMessage.id)
          );
          message.error('危险操作已被系统拦截');
          break;
      }
    } catch (error) {
      console.warn('安全检测异常:', error);
      setCheckingDanger(false);
      // 🔴 修复：更好的错误处理和用户反馈
      message.warning({
        content: '安全检测服务暂时不可用，将以普通模式发送消息',
        duration: 3,
      });
      await executeStreamSend(userMessage);
    }
  };

  /**
   * 危险命令确认执行
   */
  const handleDangerConfirm = async () => {
    if (pendingMessage) {
      setDangerModalVisible(false);
      await executeStreamSend(pendingMessage);
    }
  };

  /**
   * 危险命令取消执行
   */
  const handleDangerCancel = () => {
    setDangerModalVisible(false);
    if (pendingMessage) {
      setMessages((prev) => prev.filter((msg) => msg.id !== pendingMessage.id));
      message.info('已取消危险命令的执行');
    }
    setPendingMessage(null);
  };

  /**
   * 新建会话 - 内部实现，支持重试机制
   */
  const handleNewSessionInternal = async (retry: number = 0) => {
    const retryKey = 'new-session';
    const maxRetries = 3;

    setLoading(true);
    try {
      // 生成智能标题
      const newTitle = generateNewSessionTitle();
      const newSession = await sessionApi.createSession(newTitle);
      setSessionId(newSession.session_id);
      setSessionTitle(newTitle);
      setMessages([]);

      // 🔴 修复：清除旧的sessionStorage
      sessionStorage.removeItem(STORAGE_KEY);

      // 添加系统提示消息 - 新会话提示
      const systemMessage: Message = {
        id: (Date.now() + 1000).toString(),
        role: 'system',
        content: '💡 新会话已创建！开始与AI助手对话吧。',
        timestamp: new Date(),
      };
      setMessages([systemMessage]);

      clearSteps();
      disconnect();
      window.history.pushState({}, '', `/?session_id=${newSession.session_id}`);

      // 🎨 优化：添加更丰富的反馈
      message.success({
        content: `已创建新会话: ${newTitle}`,
        duration: 3,
        style: { marginTop: '50vh' },
      });

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } catch (error) {
      // P1级别优化：重试机制
      if (retry < maxRetries) {
        const newRetry = retry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));

        message.warning({
          content: `创建会话失败，正在重试 (${newRetry}/${maxRetries})...`,
          duration: 2,
        });

        // 延迟1秒后重试
        setTimeout(() => {
          handleNewSessionInternal(newRetry);
        }, 1000);
        return;
      }

      // 🔴 修复：更好的错误处理
      const errMsg = error instanceof Error ? error.message : '未知错误';
      message.error({
        content: `创建会话失败: ${errMsg}`,
        duration: 5,
      });
      console.error('创建会话失败:', error);

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } finally {
      setLoading(false);
    }
  };

  /**
   * 新建会话 - 按钮点击处理函数
   */
  const handleNewSession = () => {
    handleNewSessionInternal(0);
  };

  /**
   * 清空对话
   */
  const handleClear = () => {
    setMessages([]);
    clearSteps();
    disconnect();
  };

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>AI对话助手</span>
          {isReceiving && <Badge status="processing" text="接收中..." />}
          {sessionId &&
            (editingTitle ? (
              <Space>
                <Input
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  onPressEnter={async (e) => {
                    e.preventDefault();
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：回车时保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                        setSessionTitle(titleInput.trim());
                        setTitleSource('user'); // ⭐ 标记为用户修改
                        debouncedSaveTitle(sessionId, titleInput.trim());
                        message.success('标题已保存');
                      } catch (error) {
                        console.warn('保存标题失败:', error);
                        message.error('保存标题失败，请重试');
                      }
                    }
                    setEditingTitle(false);
                  }}
                  onBlur={async () => {
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：失去焦点时也保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                        setSessionTitle(titleInput.trim());
                        setTitleSource('user'); // ⭐ 标记为用户修改
                        debouncedSaveTitle(sessionId, titleInput.trim());
                        message.success('会话标题已更新');
                      } catch (error) {
                        message.error('更新标题失败');
                      }
                    }
                    setEditingTitle(false);
                  }}
                  style={{ width: 200 }}
                  autoFocus
                  placeholder="输入会话标题"
                />
              </Space>
            ) : (
              <span
                style={{
                  cursor: 'pointer',
                  color: titleSource === 'auto' ? '#666' : '#000',
                  fontSize: titleSource === 'auto' ? '14px' : '16px',
                  fontWeight: titleSource === 'user' ? 'bold' : 'normal',
                }}
                onClick={() => setEditingTitle(true)}
              >
                {sessionTitle || '未命名会话'}
                {titleSource === 'auto' && (
                  <Tooltip title="AI自动生成的标题">
                    <InfoCircleOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: '#999' }}
                    />
                  </Tooltip>
                )}
                {titleLocked && (
                  <Tooltip title="标题已锁定，防止自动覆盖">
                    <LockOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: '#1890ff' }}
                    />
                  </Tooltip>
                )}
              </span>
            ))}
        </Space>
      }
      extra={
        <Space>
          {/* 新建会话按钮 */}
          <Button
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            size="small"
            type="primary"
          >
            新建会话
          </Button>

          {/* 流式开关（同时控制显示过程） */}
          <Tag.CheckableTag
            checked={useStream}
            onChange={(checked) => {
              setUseStream(checked);
              if (!checked) {
                setShowExecution(false);
              }
            }}
          >
            <ThunderboltOutlined /> {useStream ? '流式关闭' : '流式开启'}
          </Tag.CheckableTag>

          {/* 执行过程显示开关（仅在流式模式下显示） */}
          {useStream && (
            <Button
              size="small"
              icon={showExecution ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              onClick={() => setShowExecution(!showExecution)}
            >
              {showExecution ? '隐藏过程' : '显示过程'}
            </Button>
          )}

          <Button onClick={handleClear} size="small">
            清空对话
          </Button>
        </Space>
      }
    >
      {/* AI思考过程面板已移至MessageItem内部 - 前端小新代修改 */}

      {/* 消息列表 - 前端小新代修改 UX-C04: 时间分隔线 */}
      <div
        style={{
          height: 400,
          overflowY: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
          backgroundColor: '#fafafa',
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#999', marginTop: 100 }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <p>开始与AI助手对话</p>
            <p style={{ fontSize: 12 }}>
              {useStream
                ? '流式模式已开启 - 可实时查看AI思考过程'
                : '普通模式 - 一次性返回完整回复'}
            </p>
          </div>
        ) : (
          <div>
            {(() => {
              // 时间分隔线
              const elements: React.ReactNode[] = [];
              let lastDate: string | null = null;

              for (let i = 0; i < messages.length; i++) {
                const item = messages[i];
                const currentDate = new Date(item.timestamp).toLocaleDateString(
                  'zh-CN'
                );

                if (lastDate !== currentDate) {
                  elements.push(
                    <div
                      key={`date-${i}`}
                      style={{
                        textAlign: 'center',
                        margin: '16px 0',
                        position: 'relative',
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          top: '50%',
                          left: 0,
                          right: 0,
                          height: 1,
                          backgroundColor: '#e8e8e8',
                        }}
                      />
                      <span
                        style={{
                          background: '#fafafa',
                          padding: '0 16px',
                          color: '#999',
                          fontSize: 12,
                          position: 'relative',
                          zIndex: 1,
                        }}
                      >
                        {currentDate}
                      </span>
                    </div>
                  );
                  lastDate = currentDate;
                }

                elements.push(
                  <List.Item
                    key={item.id}
                    style={{
                      justifyContent:
                        item.role === 'user' ? 'flex-end' : 'flex-start',
                      border: 'none',
                      padding: '8px 0',
                      width: '100%',
                    }}
                  >
                    <MessageItem message={item} showExecution={showExecution} />
                  </List.Item>
                );
              }

              return elements;
            })()}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 中断和暂停按钮 */}
        {loading && (
          <Space style={{ marginTop: 8, marginBottom: 8 }}>
            <Button
              danger
              icon={<CloseCircleOutlined />}
              onClick={handleInterrupt}
            >
              中断
            </Button>
            <Button
              icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={handleTogglePause}
            >
              {isPaused ? '继续' : '暂停'}
            </Button>
          </Space>
        )}
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={
            useStream
              ? '输入消息... (流式模式可实时查看思考过程)'
              : '输入消息...'
          }
          autoSize={{ minRows: 2, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={loading || isReceiving}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading || isReceiving || checkingDanger}
          disabled={!inputValue.trim()}
          block
        >
          {isReceiving
            ? '接收中...'
            : checkingDanger
              ? '安全检查中...'
              : '发送消息'}
        </Button>
      </Space>

      {/* 被拦截的命令警告 */}
      {blockedCommand && (
        <SecurityAlert
          command={blockedCommand.command}
          score={blockedCommand.score}
          message={blockedCommand.message}
        />
      )}

      {/* 危险命令确认弹窗 */}
      <DangerConfirmModal
        visible={dangerModalVisible}
        command={dangerCommand}
        score={dangerScore}
        message={dangerMessage}
        onConfirm={handleDangerConfirm}
        onCancel={handleDangerCancel}
        loading={loading}
      />
    </Card>
  );
};

export default NewChatContainer;
