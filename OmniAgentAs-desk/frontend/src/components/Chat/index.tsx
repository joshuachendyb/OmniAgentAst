/**
 * Chat组件 - 对话主界面
 * 
 * 功能：消息列表展示、消息发送、服务状态检查、模型切换、安全检测(v2.0)
 * 
 * @author 小新
 * @version 2.2.0
 * @since 2026-02-17
 * @update 2026-02-19 升级到安全检测v2.0（基于score的4级响应） - by 小新
 */

import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, List, Tag, Space, message } from 'antd';
import { SendOutlined, RobotOutlined, PlusOutlined, EditOutlined, CloseCircleOutlined, PauseCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { chatApi, sessionApi, ChatMessage, API_BASE_URL } from '../../services/api';
import { securityApi } from '../../services/api';
import MessageItem from './MessageItem';
import DangerConfirmModal from '../DangerConfirmModal';
import SecurityAlert from '../SecurityAlert';
import { showSecurityNotification } from '../SecurityNotification';
import { getRiskLevel } from '../../types/security';

const { TextArea } = Input;

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
}

/**
 * Chat组件 - 对话主界面
 * 
 * @author 小新
 * @version 2.1.0
 */
const Chat: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>('新会话');
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 安全检测v2.0状态（基于score的4级响应）
  const [dangerModalVisible, setDangerModalVisible] = useState(false);
  const [dangerCommand, setDangerCommand] = useState('');
  const [dangerScore, setDangerScore] = useState(0);
  const [dangerMessage, setDangerMessage] = useState('');
  const [pendingMessage, setPendingMessage] = useState<Message | null>(null);
  const [checkingDanger, setCheckingDanger] = useState(false);
  const [blockedCommand, setBlockedCommand] = useState<{ command: string; score: number; message: string } | null>(null);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 保存消息和滚动位置的key
  const STORAGE_KEY = 'chat_session_state';

  // 保存状态到sessionStorage
  const saveState = () => {
    if (messages.length > 0) {
      const state = {
        messages,
        sessionId,
        sessionTitle,
        scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  };

  // 从sessionStorage恢复状态
  const restoreState = () => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.messages && state.messages.length > 0) {
          setMessages(state.messages);
          setSessionId(state.sessionId);
          setSessionTitle(state.sessionTitle);
          // 恢复滚动位置（在渲染后）
          setTimeout(() => {
            if (messagesEndRef.current?.parentElement) {
              messagesEndRef.current.parentElement.scrollTop = state.scrollPosition || 0;
            }
          }, 100);
          return true;
        }
      } catch (e) {
        console.warn('恢复会话状态失败:', e);
      }
    }
    return false;
  };

  // 页面可见性变化时保存/恢复状态
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        saveState();
      } else {
        // 页面重新可见时，尝试恢复状态
        // 但不强制恢复，让用户看到之前的状态
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [messages, sessionId, sessionTitle]);

  // 加载会话（从URL参数或最近会话）
  useEffect(() => {
    const loadSession = async () => {
      // 首先尝试从sessionStorage恢复状态（如果URL没有session_id）
      const urlSessionId = searchParams.get('session_id');
      
      // 如果URL没有session_id，尝试恢复之前的状态
      if (!urlSessionId) {
        const restored = restoreState();
        if (restored) {
          console.log('从缓存恢复会话状态');
          return;
        }
      }

      // 1. 检查URL是否有session_id参数
      if (urlSessionId) {
        try {
          const sessionData = await sessionApi.getSessionMessages(urlSessionId);
          if (sessionData.messages && sessionData.messages.length > 0) {
            setSessionId(urlSessionId);
            setMessages(sessionData.messages.map((m: any) => ({
              id: m.id?.toString() || Date.now().toString(),
              role: m.role,
              content: m.content,
              timestamp: new Date(m.timestamp),
            })));
            // 从会话信息获取标题
            const titleFromApi = sessionData.messages[0]?.content?.substring(0, 30) || '会话';
            setSessionTitle(titleFromApi);
            console.log('从URL加载会话:', urlSessionId);
            return;
          }
        } catch (error) {
          console.warn('加载URL会话失败:', error);
        }
      }

      // 2. 如果没有URL参数，加载最近的会话
      try {
        const response = await sessionApi.listSessions(1, 1);
        if (response.sessions && response.sessions.length > 0) {
          const latestSession = response.sessions[0];
          const sessionData = await sessionApi.getSessionMessages(latestSession.session_id);
          setSessionId(latestSession.session_id);
          setSessionTitle(latestSession.title);
          if (sessionData.messages && sessionData.messages.length > 0) {
            setMessages(sessionData.messages.map((m: any) => ({
              id: m.id?.toString() || Date.now().toString(),
              role: m.role,
              content: m.content,
              timestamp: new Date(m.timestamp),
            })));
          }
          console.log('加载最近会话:', latestSession.session_id);
        }
      } catch (error) {
        console.warn('加载最近会话失败:', error);
      }
    };

    loadSession();
  }, [searchParams]);

  /**
   * 执行实际的消息发送（在危险命令检测通过后调用）
   * 
   * @param userMessage - 用户消息
   * @author 小新
   * @update 2026-02-21 改为流式API + task_id方式（符合后端推荐方案一）
   */
  const executeSendMessage = async (userMessage: Message) => {
    setLoading(true);
    setIsPaused(false);
    
    // 生成task_id（使用UUID或时间戳）
    const taskId = crypto.randomUUID();
    setCurrentTaskId(taskId);

    try {
      // 构建消息历史（最多保留最近10条）
      const history: ChatMessage[] = messages
        .slice(-10)
        .map((msg) => ({ role: msg.role, content: msg.content }));

      // 创建临时的assistant消息，用于流式更新
      let assistantMessageId = (Date.now() + 1).toString();
      setMessages((prev) => [...prev, {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      }]);

      // 调用流式API
      await chatApi.sendMessageStream(
        [...history, { role: 'user', content: userMessage.content }],
        {
          onStep: (step) => {
            // 更新临时的assistant消息内容
            if (step.content) {
              setMessages((prev) => prev.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, content: msg.content + step.content }
                  : msg
              ));
            }
          },
          onComplete: (finalContent) => {
            // 更新最终内容
            setMessages((prev) => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: finalContent }
                : msg
            ));
            
            // 保存消息到会话
            if (sessionId) {
              try {
                sessionApi.saveMessage(sessionId, {
                  role: 'user',
                  content: userMessage.content,
                });
                sessionApi.saveMessage(sessionId, {
                  role: 'assistant',
                  content: finalContent,
                });
              } catch (saveError) {
                console.error('保存消息失败:', saveError);
              }
            }
          },
          onError: (error) => {
            setMessages((prev) => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: `错误: ${error}` }
                : msg
            ));
          }
        }
      );
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '请求失败: ' + (error as Error).message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      setCurrentTaskId(null);
      setPendingMessage(null);
    }
  };

  /**
   * 任务中断处理（调用后端取消接口）
   * 
   * @author 小新
   * @update 2026-02-21 改为使用后端推荐的取消接口方案一
   */
  const handleInterrupt = async () => {
    if (currentTaskId) {
      try {
        message.info('正在中断任务...');
        await fetch(`${API_BASE_URL}/chat/stream/cancel/${currentTaskId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        message.success('任务中断请求已发送');
      } catch (error) {
        message.error('发送中断请求失败: ' + (error as Error).message);
      }
    }
  };

  /**
   * 任务暂停/继续处理
   * 
   * 说明：后端暂未实现暂停功能（只实现了中断）
   * 当前仅保留UI交互，实际逻辑待后端实现后补充
   * 
   * @author 小新
   * @update 2026-02-21 添加说明，后端暂未实现暂停
   */
  const handleTogglePause = () => {
    // 后端暂未实现暂停功能，仅切换UI状态
    setIsPaused(!isPaused);
    message.info('暂停功能后端暂未实现，仅显示UI状态');
  };

  /**
   * 发送消息（带安全检测v2.0 - 基于score的4级响应）
   * 
   * 安全等级处理：
   * - 0-3分 (SAFE): 直接执行，无UI反馈
   * - 4-6分 (MEDIUM): 执行并显示顶部通知
   * - 7-8分 (HIGH): 显示弹窗，需用户确认
   * - 9-10分 (CRITICAL): 直接拒绝，显示红色警告
   * 
   * @author 小新
   * @update 2026-02-19 升级到v2.0安全检测
   */
  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    // 如果没有会话，创建新会话
    let currentSessionId = sessionId;
    if (!currentSessionId) {
      try {
        const newSession = await sessionApi.createSession(inputValue.trim().substring(0, 50));
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        console.log('创建新会话:', currentSessionId);
      } catch (error) {
        console.error('创建会话失败:', error);
        // 继续发送消息，不阻塞
      }
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    // 先显示用户消息
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setBlockedCommand(null);

    // 安全检测v2.0
    setCheckingDanger(true);
    try {
      const checkResult = await securityApi.checkCommand(userMessage.content);
      setCheckingDanger(false);
      
      if (!checkResult.success || !checkResult.data) {
        // 检测失败，允许发送（容错）
        console.warn('安全检测失败:', checkResult.error);
        await executeSendMessage(userMessage);
        return;
      }

      const { score, message: riskMessage } = checkResult.data;
      const riskLevel = getRiskLevel(score);

      // 根据风险等级处理
      switch (riskLevel.level) {
        case 'SAFE':
          // 0-3分：直接执行，无UI反馈
          await executeSendMessage(userMessage);
          break;

        case 'MEDIUM':
          // 4-6分：执行并显示顶部通知
          showSecurityNotification(userMessage.content, score, riskMessage);
          await executeSendMessage(userMessage);
          break;

        case 'HIGH':
          // 7-8分：显示确认弹窗，等待用户确认
          setDangerCommand(userMessage.content);
          setDangerScore(score);
          setDangerMessage(riskMessage);
          setPendingMessage(userMessage);
          setDangerModalVisible(true);
          break;

        case 'CRITICAL':
          // 9-10分：直接拒绝，显示红色警告
          setBlockedCommand({
            command: userMessage.content,
            score,
            message: riskMessage
          });
          // 从消息列表中移除被拦截的消息
          setMessages((prev) => prev.filter((msg) => msg.id !== userMessage.id));
          message.error('危险操作已被系统拦截');
          break;
      }
    } catch (error) {
      // 检测异常，允许发送（容错）
      console.warn('安全检测异常:', error);
      setCheckingDanger(false);
      await executeSendMessage(userMessage);
    }
  };

  /**
   * 危险命令确认执行
   * 
   * @author 小新
   */
  const handleDangerConfirm = async () => {
    if (pendingMessage) {
      setDangerModalVisible(false);
      await executeSendMessage(pendingMessage);
    }
  };

  /**
   * 危险命令取消执行
   * 
   * @author 小新
   */
  const handleDangerCancel = () => {
    setDangerModalVisible(false);
    // 从消息列表中移除待发送的消息
    if (pendingMessage) {
      setMessages((prev) => prev.filter((msg) => msg.id !== pendingMessage.id));
      message.info('已取消危险命令的执行');
    }
    setPendingMessage(null);
  };

  // 清空对话
  const handleClear = () => {
    setMessages([]);
  };

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>AI 对话助手</span>
          {sessionId && (
            <Tag 
              color="blue"
              icon={editingTitle ? null : <EditOutlined />}
              onClick={() => {
                if (!editingTitle) {
                  setTitleInput(sessionTitle);
                  setEditingTitle(true);
                }
              }}
              style={{ cursor: 'pointer' }}
            >
              {sessionTitle}
            </Tag>
          )}
          {editingTitle && (
            <Input
              size="small"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              onPressEnter={async () => {
                if (titleInput.trim() && sessionId) {
                  try {
                    await sessionApi.updateSession(sessionId, titleInput.trim());
                    setSessionTitle(titleInput.trim());
                    message.success('会话标题已更新');
                  } catch (error) {
                    message.error('更新标题失败');
                  }
                }
                setEditingTitle(false);
              }}
              onBlur={() => {
                setEditingTitle(false);
              }}
              style={{ width: 150 }}
              autoFocus
            />
          )}
        </Space>
      }
      extra={
        <Space>
          <Button
            icon={<PlusOutlined />}
            onClick={async () => {
              try {
                const newSession = await sessionApi.createSession('新会话');
                setSessionId(newSession.session_id);
                setSessionTitle('新会话');
                setMessages([]);
                // 更新URL
                window.history.pushState({}, '', `/?session_id=${newSession.session_id}`);
                message.success('已创建新会话');
              } catch (error) {
                message.error('创建会话失败');
                console.error('创建会话失败:', error);
              }
            }}
            size="small"
            type="primary"
          >
            新建会话
          </Button>
          {/* 服务状态检查已移至Layout组件 */}
          <Button onClick={handleClear} size="small">
            清空对话
          </Button>
        </Space>
      }
    >
      {/* 服务状态已显示在标题行Tag中 */}

      {/* 消息列表 */}
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
            <p style={{ fontSize: 12 }}>当前阶段: 1.2 AI模型接入</p>
          </div>
        ) : (
          <List
            itemLayout="horizontal"
            dataSource={messages}
            renderItem={(item) => (
              <List.Item
                style={{
                  justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
                  border: 'none',
                  padding: '8px 0',
                  width: '100%',
                }}
              >
                <MessageItem message={item} />
              </List.Item>
            )}
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 新增：中断和暂停按钮 */}
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
          placeholder="输入消息..."
          autoSize={{ minRows: 2, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={loading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading || checkingDanger}
          disabled={!inputValue.trim()}
          block
        >
          {checkingDanger ? '安全检查中...' : '发送消息'}
        </Button>
      </Space>

      {/* 被拦截的命令警告（9-10分） */}
      {blockedCommand && (
        <SecurityAlert
          command={blockedCommand.command}
          score={blockedCommand.score}
          message={blockedCommand.message}
        />
      )}

      {/* 危险命令确认弹窗（7-8分） */}
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

export default Chat;