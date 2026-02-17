/**
 * Chat组件 - 对话主界面
 * 
 * 功能：消息列表展示、消息发送、服务状态检查、模型切换
 * 
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-17
 */

import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, List, Typography, Tag, Space, Alert, Select } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, CheckCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { chatApi, ChatMessage, ValidateResponse } from '../../services/api';
import MessageItem from './MessageItem';

const { TextArea } = Input;
const { Text } = Typography;
const { Option } = Select;

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
}

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<ValidateResponse | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<'zhipuai' | 'opencode'>('zhipuai');
  const [currentModel, setCurrentModel] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
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
    }
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
          <Tag color={serviceStatus?.success ? 'success' : 'warning'}>
            {serviceStatus?.success ? (
              <><CheckCircleOutlined /> {getProviderName(currentProvider)} {currentModel && `(${currentModel})`}</>
            ) : (
              <>{getProviderName(currentProvider)} {currentModel && `(${currentModel})`} - 未就绪</>
            )}
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
                <>
                  <p style={{ marginTop: 8, color: '#666' }}>
                    💡 提示: 您可以尝试切换到另一个提供商，或检查API配置
                  </p>
                </>
              )}
            </>
          }
          type={serviceStatus.success ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 16 }}
        />
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
          loading={loading}
          disabled={!inputValue.trim()}
          block
        >
          发送消息
        </Button>
      </Space>
    </Card>
  );
};

export default Chat;