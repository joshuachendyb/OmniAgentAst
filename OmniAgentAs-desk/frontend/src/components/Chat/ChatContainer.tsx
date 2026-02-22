/**
 * ChatContainer组件 - 带流式支持的对话容器
 * 
 * 功能：集成SSE流式通信，执行过程可视化、消息美化
 * 
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-17
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Card, List, Tag, Space, Alert, Select, Collapse, Badge } from 'antd';
import { 
  SendOutlined, 
  RobotOutlined, 
  ReloadOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import { chatApi, ChatMessage, ValidateResponse } from '../../services/api';
import MessageItem from './MessageItem';
import ExecutionPanel from './ExecutionPanel';
import { useSSE, ExecutionStep } from '../../utils/sse';

const { TextArea } = Input;
const { Option } = Select;
const { Panel } = Collapse;

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  executionSteps?: ExecutionStep[];
  isStreaming?: boolean;
  model?: string;  // 【新增】当前使用的模型
}

/**
 * Chat容器组件
 * 
 * 特性：
 * - 支持普通HTTP对话和SSE流式对话
 * - 实时显示AI思考过程（ReAct执行步骤）
 * - 可折叠的执行过程面板
 */
const ChatContainer: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<ValidateResponse | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<'zhipuai' | 'opencode'>('zhipuai');
  const [currentModel, setCurrentModel] = useState<string>('');
  const [showExecution, setShowExecution] = useState(true);
  const [useStream, setUseStream] = useState(true); // 默认使用流式
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentSessionId = useRef<string>('default-session');

  // SSE Hook配置
  const {
    isConnected: _isConnected,
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
  } = useSSE(
    {
      baseURL: 'http://localhost:8000/api/v1',
      sessionId: currentSessionId.current,
    },
    // onStep - 收到执行步骤
    useCallback((step: ExecutionStep) => {
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming) {
          // 更新最后一条消息的executionSteps
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
            model: model || lastMessage.model, // 保存当前使用的模型
          };
          return updated;
        }
        return prev;
      });
      setLoading(false);
    }, []),
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

  // 检查服务状态
  const checkServiceStatus = async () => {
    setCheckingStatus(true);
    try {
      const status = await chatApi.validateService();
      setServiceStatus(status);
      if (status.success && (status.provider === 'zhipuai' || status.provider === 'opencode')) {
        setCurrentProvider(status.provider);
      }
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
      setCurrentProvider(provider);
      
      if (result.model) {
        setCurrentModel(result.model);
      }
      
      const providerName = getProviderName(provider);
      const modelName = result.model || '未知模型';
      
      addSystemMessage(
        result.success 
          ? `✅ 已切换到 ${providerName} (${modelName})`
          : `⚠️ 切换到 ${providerName} (${modelName}) 失败: ${result.message}`
      );
    } catch (error) {
      addSystemMessage('❌ 切换提供商时发生错误');
    } finally {
      setLoading(false);
    }
  };

  // 添加系统消息
  const addSystemMessage = (content: string) => {
    setMessages(prev => [
      ...prev,
      {
        id: Date.now().toString(),
        role: 'system',
        content,
        timestamp: new Date(),
      },
    ]);
  };

  // 发送消息（支持流式和非流式）
  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    const userContent = inputValue.trim();
    setInputValue('');
    setLoading(true);

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userContent,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);

    if (useStream) {
      // 流式模式
      // 先添加一个空的AI消息占位
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        executionSteps: [],
        isStreaming: true,
      };
      setMessages(prev => [...prev, assistantMessage]);
      
      // 清空之前的步骤
      clearSteps();
      
      // 发送流式请求
      sendStreamMessage(userContent);
    }
  };

  // 清空对话
  const handleClear = () => {
    setMessages([]);
    clearSteps();
    disconnect();
  };

  const getProviderName = (provider: string) => {
    const names: Record<string, string> = {
      zhipuai: '智谱AI',
      opencode: 'OpenCode',
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      longcat: 'LongCat',
    };
    return names[provider] || provider;
  };

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>AI助手对话</span>
          {isReceiving && (
            <Badge status="processing" text="接收中..." />
          )}
        </Space>
      }
      extra={
        <Space>
          <Select
            value={currentProvider}
            style={{ width: 200 }}
            onChange={handleSwitchProvider}
            disabled={loading || isReceiving}
          >
            <Option value="zhipuai">智谱GLM (glm-4.7-flash)</Option>
            <Option value="opencode">OpenCode (MiniMax M2.5 Free)</Option>
          </Select>
          
          {/* 流式开关 */}
          <Tag.CheckableTag
            checked={useStream}
            onChange={setUseStream}
          >
            <ThunderboltOutlined /> {useStream ? '流式开启' : '流式关闭'}
          </Tag.CheckableTag>
          
          {/* 执行过程显示开关 */}
          <Button
            size="small"
            icon={showExecution ? <EyeOutlined /> : <EyeInvisibleOutlined />}
            onClick={() => setShowExecution(!showExecution)}
          >
            {showExecution ? '隐藏过程' : '显示过程'}
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
      {/* 服务状态提示 */}
      {serviceStatus && (
        <Alert
          message={serviceStatus.success ? 'AI服务正常' : 'AI服务异常'}
          description={
            <>
              <p><strong>当前提供商:</strong> {getProviderName(currentProvider)} {currentModel && `(${currentModel})`}</p>
              <p><strong>状态:</strong> {serviceStatus.message}</p>
              {!serviceStatus.success && (
                <p style={{ marginTop: 8, color: '#666' }}>
                  💡 提示: 您可以尝试切换到另一个提供商，或检查API配置
                </p>
              )}
            </>
          }
          type={serviceStatus.success ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

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
          loading={loading || isReceiving}
          disabled={!inputValue.trim()}
          block
        >
          {isReceiving ? '接收中...' : '发送消息'}
        </Button>
      </Space>
    </Card>
  );
};

export default ChatContainer;
