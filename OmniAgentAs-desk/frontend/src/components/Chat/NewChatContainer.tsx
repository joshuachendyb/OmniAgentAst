/**
 * NewChatContainer组件 - 升级版对话容器
 * 
 * 功能：
 * - 完整会话管理（新建会话、编辑标题、历史记录加载）
 * - SSE流式输出 + 执行步骤可视化
 * - 安全检测v2.0（基于score的4级响应）
 * - 任务中断控制
 * 
 * @author 小新
 * @version 3.0.0
 * @since 2026-02-23
 * @update 整合 Chat/index.tsx 功能 + ChatContainer 流式输出
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Card, List, Tag, Space, message, Collapse, Badge } from 'antd';
import { 
  SendOutlined, 
  RobotOutlined, 
  PlusOutlined, 
  EditOutlined, 
  CloseCircleOutlined, 
  PauseCircleOutlined, 
  PlayCircleOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { sessionApi, ChatMessage, API_BASE_URL } from '../../services/api';
import { securityApi } from '../../services/api';
import MessageItem from './MessageItem';
import ExecutionPanel from './ExecutionPanel';
import DangerConfirmModal from '../DangerConfirmModal';
import SecurityAlert from '../SecurityAlert';
import { showSecurityNotification } from '../SecurityNotification';
import { getRiskLevel } from '../../types/security';
import { useSSE, ExecutionStep } from '../../utils/sse';

const { TextArea } = Input;
const { Panel } = Collapse;

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
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');
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
  const [blockedCommand, setBlockedCommand] = useState<{ command: string; score: number; message: string } | null>(null);

  // SSE Hook配置（用于流式输出）
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    setTaskId,
  } = useSSE(
    {
      baseURL: 'http://localhost:8000/api/v1',
      sessionId: sessionId || 'default-session',
    },
    // onStep - 收到执行步骤
    useCallback((step: ExecutionStep) => {
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming) {
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
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming) {
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
    useCallback((fullResponse: string, model?: string) => {
      setMessages(prev => {
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
          sessionApi.saveMessage(sessionId, {
            role: 'user',
            content: currentPending.content,
          });
          sessionApi.saveMessage(sessionId, {
            role: 'assistant',
            content: fullResponse,
          });
        } catch (saveError) {
          console.error('保存消息失败:', saveError);
        }
      }
      
      setLoading(false);
      setPendingMessage(null);
    }, [sessionId, pendingMessage]),
    // onError - 流式错误
    useCallback((error: string) => {
      console.error('SSE流式错误:', error);
      setMessages(prev => {
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

  const restoreState = () => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.messages && state.messages.length > 0) {
          setMessages(state.messages);
          setSessionId(state.sessionId);
          setSessionTitle(state.sessionTitle);
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

  // ============================================
  // 加载历史会话
  // ============================================
  useEffect(() => {
    const loadSession = async () => {
      const urlSessionId = searchParams.get('session_id');
      
      if (!urlSessionId) {
        const restored = restoreState();
        if (restored) {
          console.log('从缓存恢复会话状态');
          return;
        }
      }

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
            const titleFromApi = sessionData.messages[0]?.content?.substring(0, 30) || '会话';
            setSessionTitle(titleFromApi);
            console.log('从URL加载会话:', urlSessionId);
            return;
          }
        } catch (error) {
          console.warn('加载URL会话失败:', error);
        }
      }

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
    };
    setMessages((prev) => [...prev, assistantMessage]);
    
    // 保存待发送消息，用于onComplete时保存到会话
    setPendingMessage(userMessage);
    
    // 发送流式请求
    sendStreamMessage(userMessage.content);
  };

  /**
   * 任务中断处理
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

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      try {
        const newSession = await sessionApi.createSession(inputValue.trim().substring(0, 50));
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        console.log('创建新会话:', currentSessionId);
      } catch (error) {
        console.error('创建会话失败:', error);
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
            message: riskMessage
          });
          setMessages((prev) => prev.filter((msg) => msg.id !== userMessage.id));
          message.error('危险操作已被系统拦截');
          break;
      }
    } catch (error) {
      console.warn('安全检测异常:', error);
      setCheckingDanger(false);
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
   * 新建会话
   */
  const handleNewSession = async () => {
    try {
      const newSession = await sessionApi.createSession('新会话');
      setSessionId(newSession.session_id);
      setSessionTitle('新会话');
      setMessages([]);
      clearSteps();
      disconnect();
      window.history.pushState({}, '', `/?session_id=${newSession.session_id}`);
      message.success('已创建新会话');
    } catch (error) {
      message.error('创建会话失败');
      console.error('创建会话失败:', error);
    }
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
          {isReceiving && (
            <Badge status="processing" text="接收中..." />
          )}
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
            <ThunderboltOutlined /> {useStream ? '流式开启' : '流式关闭'}
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
      {/* 执行过程面板（可折叠） */}
      {useStream && showExecution && messages.some(m => m.isStreaming || (m.executionSteps && m.executionSteps.length > 0)) && (
        <Collapse 
          defaultActiveKey={['execution']} 
          style={{ marginBottom: 16 }}
        >
          <Panel 
            header={
              <Space>
                <ThunderboltOutlined />
                <span>AI思考过程</span>
                {isReceiving && <LoadingOutlined />}
              </Space>
            } 
            key="execution"
          >
            <ExecutionPanel steps={executionSteps} isActive={isReceiving} />
          </Panel>
        </Collapse>
      )}

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
            <p style={{ fontSize: 12 }}>
              {useStream ? '流式模式已开启 - 可实时查看AI思考过程' : '普通模式 - 一次性返回完整回复'}
            </p>
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
                <MessageItem 
                  message={item} 
                  showExecution={showExecution}
                />
              </List.Item>
            )}
          />
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
          placeholder={useStream ? "输入消息... (流式模式可实时查看思考过程)" : "输入消息..."}
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
          {isReceiving ? '接收中...' : checkingDanger ? '安全检查中...' : '发送消息'}
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
