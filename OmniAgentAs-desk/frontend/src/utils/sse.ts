/**
 * SSE工具模块 - Server-Sent Events流式处理
 * 
 * 功能：建立SSE连接、接收流式数据、处理执行步骤
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { message } from 'antd';

/**
 * 执行步骤类型
 */
export interface ExecutionStep {
  /** 步骤类型 */
  type: 'thought' | 'action' | 'observation' | 'final' | 'error';
  /** 步骤内容 */
  content?: string;
  /** 工具名称 */
  tool?: string;
  /** 工具参数 */
  params?: Record<string, any>;
  /** 执行结果 */
  result?: any;
  /** 时间戳 */
  timestamp: number;
  /** 步骤序号 */
  stepNumber?: number;
}

/**
 * 流式消息类型
 */
export interface StreamMessage {
  /** 消息类型 */
  type: 'start' | 'step' | 'chunk' | 'complete' | 'error';
  /** 消息数据 */
  data?: ExecutionStep | string;
  /** 完整消息ID */
  messageId?: string;
  /** 错误信息 */
  error?: string;
}

/**
 * SSE连接配置
 */
export interface SSEConfig {
  /** API基础URL */
  baseURL: string;
  /** 会话ID */
  sessionId: string;
  /** 认证Token */
  token?: string;
}

/**
 * SSE Hook返回值
 */
export interface UseSSEReturn {
  /** 是否连接中 */
  isConnected: boolean;
  /** 是否正在接收 */
  isReceiving: boolean;
  /** 执行步骤列表 */
  executionSteps: ExecutionStep[];
  /** 当前AI回复内容 */
  currentResponse: string;
  /** 发送消息 */
  sendMessage: (content: string) => void;
  /** 断开连接 */
  disconnect: () => void;
  /** 清空步骤 */
  clearSteps: () => void;
}

/**
 * SSE Hook - 用于组件中流式通信
 * 
 * @param config - SSE配置
 * @param onStep - 执行步骤回调
 * @param onChunk - 消息片段回调
 * @param onComplete - 完成回调
 * @param onError - 错误回调
 * @returns SSE控制对象
 */
export const useSSE = (
  config: SSEConfig,
  onStep?: (step: ExecutionStep) => void,
  onChunk?: (chunk: string) => void,
  onComplete?: (fullResponse: string) => void,
  onError?: (error: string) => void
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [currentResponse, setCurrentResponse] = useState('');
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const responseBufferRef = useRef('');

  /**
   * 断开连接
   */
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    setIsReceiving(false);
  }, []);

  /**
   * 清空执行步骤
   */
  const clearSteps = useCallback(() => {
    setExecutionSteps([]);
    setCurrentResponse('');
    responseBufferRef.current = '';
  }, []);

  /**
   * 发送消息建立SSE连接
   */
  const sendMessage = useCallback((content: string) => {
    // 断开已有连接
    disconnect();
    clearSteps();
    
    setIsReceiving(true);
    
    // 构建URL（包含查询参数）
    const url = new URL(`${config.baseURL}/chat/stream`);
    url.searchParams.append('session_id', config.sessionId);
    url.searchParams.append('message', content);
    if (config.token) {
      url.searchParams.append('token', config.token);
    }
    
    // 创建EventSource
    const eventSource = new EventSource(url.toString());
    eventSourceRef.current = eventSource;
    
    // 连接打开
    eventSource.onopen = () => {
      setIsConnected(true);
      console.log('[SSE] 连接已建立');
    };
    
    // 接收消息
    eventSource.onmessage = (event) => {
      try {
        const data: StreamMessage = JSON.parse(event.data);
        
        switch (data.type) {
          case 'start':
            console.log('[SSE] 开始接收:', data.messageId);
            break;
            
          case 'step':
            if (data.data && typeof data.data === 'object') {
              const step = data.data as ExecutionStep;
              setExecutionSteps(prev => [...prev, step]);
              onStep?.(step);
            }
            break;
            
          case 'chunk':
            if (typeof data.data === 'string') {
              const chunk = data.data;
              responseBufferRef.current += chunk;
              setCurrentResponse(responseBufferRef.current);
              onChunk?.(chunk);
            }
            break;
            
          case 'complete':
            setIsReceiving(false);
            setIsConnected(false);
            eventSource.close();
            onComplete?.(responseBufferRef.current);
            console.log('[SSE] 接收完成');
            break;
            
          case 'error':
            setIsReceiving(false);
            setIsConnected(false);
            eventSource.close();
            const errorMsg = data.error || '未知错误';
            message.error(`流式传输错误: ${errorMsg}`);
            onError?.(errorMsg);
            console.error('[SSE] 错误:', errorMsg);
            break;
        }
      } catch (err) {
        console.error('[SSE] 解析消息失败:', err);
      }
    };
    
    // 连接错误
    eventSource.onerror = (error) => {
      console.error('[SSE] 连接错误:', error);
      setIsConnected(false);
      setIsReceiving(false);
      eventSource.close();
      onError?.('SSE连接错误');
      message.error('连接异常，请重试');
    };
    
  }, [config, disconnect, clearSteps, onStep, onChunk, onComplete, onError]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage,
    disconnect,
    clearSteps,
  };
};

/**
 * 创建SSE连接（非Hook方式）
 * 
 * @param url - SSE端点URL
 * @param handlers - 事件处理器
 * @returns EventSource实例
 */
export const createSSEConnection = (
  url: string,
  handlers: {
    onOpen?: () => void;
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string) => void;
    onComplete?: (fullResponse: string) => void;
    onError?: (error: string) => void;
    onClose?: () => void;
  }
): EventSource => {
  const eventSource = new EventSource(url);
  let responseBuffer = '';
  
  eventSource.onopen = () => {
    console.log('[SSE] 连接已建立');
    handlers.onOpen?.();
  };
  
  eventSource.onmessage = (event) => {
    try {
      const data: StreamMessage = JSON.parse(event.data);
      
      switch (data.type) {
        case 'start':
          console.log('[SSE] 开始接收:', data.messageId);
          break;
          
        case 'step':
          if (data.data && typeof data.data === 'object') {
            handlers.onStep?.(data.data as ExecutionStep);
          }
          break;
          
        case 'chunk':
          if (typeof data.data === 'string') {
            responseBuffer += data.data;
            handlers.onChunk?.(data.data);
          }
          break;
          
        case 'complete':
          eventSource.close();
          handlers.onComplete?.(responseBuffer);
          handlers.onClose?.();
          console.log('[SSE] 接收完成');
          break;
          
        case 'error':
          eventSource.close();
          handlers.onError?.(data.error || '未知错误');
          handlers.onClose?.();
          console.error('[SSE] 错误:', data.error);
          break;
      }
    } catch (err) {
      console.error('[SSE] 解析消息失败:', err);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('[SSE] 连接错误:', error);
    handlers.onError?.('连接错误');
    handlers.onClose?.();
    eventSource.close();
  };
  
  return eventSource;
};

/**
 * 解析执行步骤内容
 * 
 * @param step - 执行步骤
 * @returns 格式化后的显示文本
 */
export const formatExecutionStep = (step: ExecutionStep): string => {
  switch (step.type) {
    case 'thought':
      return step.content || '思考中...';
    case 'action':
      if (step.tool) {
        return `执行工具: ${step.tool}${step.params ? `(${JSON.stringify(step.params)})` : ''}`;
      }
      return step.content || '执行动作...';
    case 'observation':
      return step.result ? `观察结果: ${JSON.stringify(step.result)}` : step.content || '观察中...';
    case 'final':
      return step.content || '任务完成';
    case 'error':
      return `错误: ${step.content || '未知错误'}`;
    default:
      return step.content || '';
  }
};

export default useSSE;
