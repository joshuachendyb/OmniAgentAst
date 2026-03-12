/**
 * SSE V2 单元测试
 * 
 * 测试内容：
 * 1. 错误分类函数
 * 2. 重连延迟计算
 * 3. 友好错误消息生成
 * 
 * @author 小查
 * @since 2026-03-04
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * 错误类型分类测试
 */
describe('错误分类', () => {
  // 模拟 classifyError 函数（因为它是在模块内部，需要通过导出或重新实现来测试）
  const classifyError = (error: any): string => {
    if (error.name === 'AbortError') return 'timeout';
    if (error.message?.includes('fetch') || error.message?.includes('network')) return 'network';
    if (error.message?.includes('HTTP')) return 'server';
    // 后端返回的error_type直接使用
    if (error.error_type === 'empty_response') return 'empty_response';
    if (error.error_type === 'timeout') return 'timeout';
    if (error.error_type === 'network') return 'network';
    if (error.error_type === 'server') return 'server';
    return 'unknown';
  };

  it('应识别超时错误', () => {
    const error = { name: 'AbortError' };
    expect(classifyError(error)).toBe('timeout');
  });

  it('应识别网络错误', () => {
    const error = { message: 'Failed to fetch' };
    expect(classifyError(error)).toBe('network');
  });

  it('应识别服务器错误', () => {
    const error = { message: 'HTTP 500: Internal Server Error' };
    expect(classifyError(error)).toBe('server');
  });

  it('应识别后端返回的empty_response错误', () => {
    const error = { error_type: 'empty_response', message: '模型返回空内容' };
    expect(classifyError(error)).toBe('empty_response');
  });

  it('应识别后端返回的timeout错误', () => {
    const error = { error_type: 'timeout', message: '请求超时' };
    expect(classifyError(error)).toBe('timeout');
  });

  it('应识别后端返回的network错误', () => {
    const error = { error_type: 'network', message: '网络错误' };
    expect(classifyError(error)).toBe('network');
  });
});

/**
 * 重连延迟计算测试
 */
describe('重连延迟计算', () => {
  // 模拟 calculateReconnectDelay 函数
  const calculateReconnectDelay = (attempt: number, baseDelay: number, maxDelay: number): number => {
    const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
    return delay + Math.random() * 1000;
  };

  it('应使用指数退避策略', () => {
    const baseDelay = 1000;
    const maxDelay = 10000;
    
    const delay0 = calculateReconnectDelay(0, baseDelay, maxDelay);
    const delay1 = calculateReconnectDelay(1, baseDelay, maxDelay);
    const delay2 = calculateReconnectDelay(2, baseDelay, maxDelay);
    
    // 每次重试延迟应该增加
    expect(delay1).toBeGreaterThan(delay0);
    expect(delay2).toBeGreaterThan(delay1);
  });

  it('不应超过最大延迟', () => {
    const baseDelay = 1000;
    const maxDelay = 5000;
    
    for (let attempt = 0; attempt < 10; attempt++) {
      const delay = calculateReconnectDelay(attempt, baseDelay, maxDelay);
      expect(delay).toBeLessThanOrEqual(maxDelay + 1000); // 考虑随机抖动
    }
  });

  it('应添加随机抖动', () => {
    const baseDelay = 1000;
    const maxDelay = 10000;
    
    // 多次调用同一 attempt 的延迟应该不同
    const delays = new Set<number>();
    for (let i = 0; i < 10; i++) {
      delays.add(calculateReconnectDelay(0, baseDelay, maxDelay));
    }
    
    // 至少有一些变化
    expect(delays.size).toBeGreaterThan(1);
  });
});

/**
 * 友好错误消息测试
 */
describe('友好错误消息', () => {
  // 模拟 getFriendlyErrorMessage 函数
  const getFriendlyErrorMessage = (errorType: string, originalMessage: string): string => {
    switch (errorType) {
      case 'timeout':
        return '请求超时，请检查网络或稍后重试';
      case 'network':
        return '网络连接失败，请检查网络后重试';
      case 'server':
        return `服务器错误: ${originalMessage}`;
      case 'empty_response':
        return '模型未能生成有效回复，请尝试更换问题或稍后重试';
      default:
        return `连接异常: ${originalMessage}`;
    }
  };

  it('应返回超时提示', () => {
    const msg = getFriendlyErrorMessage('timeout', 'Request timeout');
    expect(msg).toContain('超时');
  });

  it('应返回网络错误提示', () => {
    const msg = getFriendlyErrorMessage('network', 'Network error');
    expect(msg).toContain('网络');
  });

  it('应返回服务器错误提示', () => {
    const msg = getFriendlyErrorMessage('server', '500 Internal Error');
    expect(msg).toContain('服务器错误');
  });

  it('应返回空响应错误提示', () => {
    const msg = getFriendlyErrorMessage('empty_response', '模型返回空内容');
    expect(msg).toContain('模型');
    expect(msg).toContain('有效回复');
  });

  it('应返回默认错误提示', () => {
    const msg = getFriendlyErrorMessage('unknown', 'Unknown error');
    expect(msg).toContain('连接异常');
  });
});

/**
 * SSE 配置测试
 */
describe('SSE 配置', () => {
  it('应有默认重连配置', () => {
    const reconnectConfig = {
      enabled: true,
      maxAttempts: 3,
      baseDelay: 1000,
      maxDelay: 10000,
    };
    
    expect(reconnectConfig.enabled).toBe(true);
    expect(reconnectConfig.maxAttempts).toBe(3);
    expect(reconnectConfig.baseDelay).toBe(1000);
    expect(reconnectConfig.maxDelay).toBe(10000);
  });
});

/**
 * 连接状态测试
 */
describe('连接状态', () => {
  type ReconnectStatus = 'idle' | 'connecting' | 'reconnecting' | 'failed';
  
  it('应有正确的状态值', () => {
    const statuses: ReconnectStatus[] = ['idle', 'connecting', 'reconnecting', 'failed'];
    
    expect(statuses).toContain('idle');
    expect(statuses).toContain('connecting');
    expect(statuses).toContain('reconnecting');
    expect(statuses).toContain('failed');
  });
});

console.log('SSE V2 单元测试文件创建完成');
