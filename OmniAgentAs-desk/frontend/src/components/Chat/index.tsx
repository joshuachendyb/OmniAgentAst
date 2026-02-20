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
import { Input, Button, Card, List, Tag, Space, Select, message, Popconfirm } from 'antd';
import { SendOutlined, RobotOutlined, ReloadOutlined, PlusOutlined, EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { chatApi, configApi, sessionApi, ChatMessage, ValidateResponse } from '../../services/api';
import { securityApi } from '../../services/api';
import MessageItem from './MessageItem';
import DangerConfirmModal from '../DangerConfirmModal';
import SecurityAlert from '../SecurityAlert';
import { showSecurityNotification } from '../SecurityNotification';
import { getRiskLevel } from '../../types/security';

const { TextArea } = Input;
const { Option } = Select;

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
  const [serviceStatus, setServiceStatus] = useState<ValidateResponse | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<'zhipuai' | 'opencode'>('zhipuai');
  const [currentModel, setCurrentModel] = useState<string>('');
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

  // 加载会话（从URL参数或最近会话）
  useEffect(() => {
    const loadSession = async () => {
      // 1. 首先检查URL是否有session_id参数
      const urlSessionId = searchParams.get('session_id');
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
            setSessionTitle(sessionData.messages[0]?.content?.substring(0, 30) || '会话');
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

  // 【修复】组件加载时先获取配置，再检查服务状态
  useEffect(() => {
    const initProvider = async () => {
      try {
        const config = await configApi.getConfig();
        if (config.ai_provider === 'zhipuai' || config.ai_provider === 'opencode') {
          setCurrentProvider(config.ai_provider);
        }
        if (config.ai_model) {
          setCurrentModel(config.ai_model);
        }
      } catch (error) {
        console.warn('获取配置失败:', error);
      } finally {
        // 无论是否获取到配置，都检查服务状态
        checkServiceStatus();
      }
    };
    initProvider();
  }, []);

  // 检查服务状态
  const checkServiceStatus = async () => {
    setCheckingStatus(true);
    try {
      const status = await chatApi.validateService();
      setServiceStatus(status);
      if (status.success && (status.provider === 'zhipuai' || status.provider === 'opencode')) {
        setCurrentProvider(status.provider);
      }
      // 更新模型名称
      if (status.model) {
        setCurrentModel(status.model);
      }
    } catch (error) {
      setServiceStatus({
        success: false,
        provider: 'unknown',
        model: '',
        message: '服务检查失败: ' + (error as Error).message,
      });
    } finally {
      setCheckingStatus(false);
    }
  };

  // 切换提供商
  const handleSwitchProvider = async (provider: 'zhipuai' | 'opencode') => {
    setLoading(true);
    try {
      const result = await chatApi.switchProvider(provider);
      setServiceStatus(result);
      
      // 无论成功还是失败，都更新当前显示的提供商
      // 让用户知道当前选择的模型状态
      setCurrentProvider(provider);
      
      // 更新模型名称
      if (result.model) {
        setCurrentModel(result.model);
      }
      
      const providerName = getProviderName(provider);
      const modelName = result.model || '未知模型';
      
      if (result.success) {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: `✅ 已切换到 ${providerName} (${modelName})`,
            timestamp: new Date(),
          },
        ]);
      } else {
        // 切换失败，显示具体错误信息，但不回退
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: `⚠️ 切换到 ${providerName} (${modelName}) 失败: ${result.message}`,
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      // 请求异常，更新提供商但不回退
      setCurrentProvider(provider);
      const providerName = getProviderName(provider);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'system',
          content: `❌ 切换到 ${providerName} 请求失败: ${(error as Error).message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 执行实际的消息发送（在危险命令检测通过后调用）n   * 
   * @param userMessage - 用户消息
   * @author 小新
   */
  const executeSendMessage = async (userMessage: Message) => {
    setLoading(true);

    try {
      // 构建消息历史（最多保留最近10条）
      const history: ChatMessage[] = messages
        .slice(-10)
        .map((msg) => ({ role: msg.role, content: msg.content }));

      const response = await chatApi.sendMessage([
        ...history,
        { role: 'user', content: userMessage.content },
      ]);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.success ? response.content : `错误: ${response.error || '未知错误'}`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // 保存消息到会话
      if (sessionId) {
        try {
          // 保存用户消息
          await sessionApi.saveMessage(sessionId, {
            role: 'user',
            content: userMessage.content,
          });
          // 保存助手回复
          await sessionApi.saveMessage(sessionId, {
            role: 'assistant',
            content: assistantMessage.content,
          });
          console.log('消息已保存到会话:', sessionId);
        } catch (saveError) {
          console.error('保存消息失败:', saveError);
        }
      }
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
      setPendingMessage(null);
    }
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

  // 获取提供商显示名称
  const getProviderName = (provider: string) => {
    switch (provider) {
      case 'zhipuai':
        return '智谱GLM';
      case 'opencode':
        return 'OpenCode';
      default:
        return provider;
    }
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
          <Tag color={serviceStatus?.success ? 'success' : 'warning'}>
            {getProviderName(currentProvider)} {currentModel && `(${currentModel})`}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Select
            value={currentProvider}
            style={{ width: 200 }}
            onChange={handleSwitchProvider}
            disabled={loading}
          >
            <Option value="zhipuai">智谱GLM (glm-4.7-flash)</Option>
            <Option value="opencode">OpenCode (MiniMax M2.5 Free)</Option>
          </Select>
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
          <Button
            icon={<ReloadOutlined />}
            onClick={checkServiceStatus}
            loading={checkingStatus}
            size="small"
          >
            检查服务
          </Button>
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