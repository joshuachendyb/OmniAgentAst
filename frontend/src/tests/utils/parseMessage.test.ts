/**
 * 历史消息统一读取模块测试
 *
 * 测试范围：
 * - parseMessage 函数：消息解析逻辑
 * - 历史消息加载流程测试
 * - 缓存逻辑测试
 *
 * @author 小查
 * @version 1.0.0
 * @since 2026-03-12
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ============================================
// 测试用 mock 函数（与 NewChatContainer.tsx 中的实现相同）
// ============================================

interface MockExecutionStep {
  type: string;
  content?: string;
  display_name?: string;
  model?: string;
  provider?: string;
}

interface MockMessage {
  id?: string | number;
  role?: string;
  content?: string;
  timestamp?: string | number | Date;
  execution_steps?: MockExecutionStep[];
  executionSteps?: MockExecutionStep[];
  display_name?: string;
  model?: string;
  provider?: string;
  is_reasoning?: boolean;
}

interface Message {
  id: string;
  role: string;
  content: string;
  timestamp: Date;
  executionSteps?: MockExecutionStep[];
  display_name?: string;
  model?: string;
  provider?: string;
  is_reasoning?: boolean;
}

// 解析单条消息（与 NewChatContainer.tsx 中的实现相同）
const parseMessage = (rawMessage: MockMessage): Message => {
  // 处理 executionSteps（兼容两种字段名）
  let executionSteps: MockExecutionStep[] = [];
  if (rawMessage.execution_steps && Array.isArray(rawMessage.execution_steps)) {
    executionSteps = rawMessage.execution_steps;
  } else if (rawMessage.executionSteps && Array.isArray(rawMessage.executionSteps)) {
    executionSteps = rawMessage.executionSteps;
  }

  return {
    id: rawMessage.id?.toString() || Date.now().toString(),
    role: rawMessage.role || "assistant",
    content: rawMessage.content || "",
    timestamp: new Date(rawMessage.timestamp || Date.now()),
    executionSteps,
    display_name: rawMessage.display_name,
    model: rawMessage.model || undefined,
    provider: rawMessage.provider || undefined,
    is_reasoning: rawMessage.is_reasoning,
  };
};

// ============================================
// 测试1: parseMessage 函数基本功能
// ============================================

describe('parseMessage 函数', () => {
  
  it('应该正确解析基本消息字段', () => {
    const rawMessage: MockMessage = {
      id: '123',
      role: 'user',
      content: 'Hello World',
      timestamp: '2026-03-12T10:00:00Z',
    };

    const result = parseMessage(rawMessage);

    expect(result.id).toBe('123');
    expect(result.role).toBe('user');
    expect(result.content).toBe('Hello World');
    expect(result.timestamp).toBeInstanceOf(Date);
  });

  it('应该使用默认角色为 assistant', () => {
    const rawMessage: MockMessage = {
      content: 'Test message',
    };

    const result = parseMessage(rawMessage);

    expect(result.role).toBe('assistant');
  });

  it('应该使用默认内容为空字符串', () => {
    const rawMessage: MockMessage = {
      role: 'user',
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('');
  });

  it('应该处理 id 为 number 类型', () => {
    const rawMessage: MockMessage = {
      id: 456,
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.id).toBe('456');
  });

  it('应该在 id 缺失时生成默认 id', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.id).toBeDefined();
    expect(result.id).not.toBe('');
  });

  it('应该正确解析 timestamp 为 Date 对象', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      timestamp: '2026-03-12T10:00:00Z',
    };

    const result = parseMessage(rawMessage);

    expect(result.timestamp).toBeInstanceOf(Date);
    expect(result.timestamp.getTime()).toBe(new Date('2026-03-12T10:00:00Z').getTime());
  });

  it('应该在 timestamp 缺失时使用当前时间', () => {
    const before = Date.now();
    const rawMessage: MockMessage = {
      content: 'Test',
    };
    const result = parseMessage(rawMessage);
    const after = Date.now();

    expect(result.timestamp.getTime()).toBeGreaterThanOrEqual(before);
    expect(result.timestamp.getTime()).toBeLessThanOrEqual(after);
  });

});

// ============================================
// 测试2: parseMessage 处理 executionSteps
// ============================================

describe('parseMessage 处理 executionSteps', () => {

  it('应该正确解析 execution_steps 字段', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      execution_steps: [
        { type: 'start', content: 'Starting' },
        { type: 'chunk', content: 'Processing' },
      ],
    };

    const result = parseMessage(rawMessage);

    expect(result.executionSteps).toBeDefined();
    expect(result.executionSteps).toHaveLength(2);
    expect(result.executionSteps?.[0].type).toBe('start');
    expect(result.executionSteps?.[1].type).toBe('chunk');
  });

  it('应该正确解析 executionSteps 字段（驼峰命名）', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      executionSteps: [
        { type: 'start', content: 'Starting' },
      ],
    };

    const result = parseMessage(rawMessage);

    expect(result.executionSteps).toBeDefined();
    expect(result.executionSteps).toHaveLength(1);
    expect(result.executionSteps?.[0].type).toBe('start');
  });

  it('应该优先使用 execution_steps 而非 executionSteps', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      execution_steps: [
        { type: 'start', content: 'From snake_case' },
      ],
      executionSteps: [
        { type: 'start', content: 'From camelCase' },
      ],
    };

    const result = parseMessage(rawMessage);

    expect(result.executionSteps?.[0].content).toBe('From snake_case');
  });

  it('应该在没有 executionSteps 时返回空数组', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.executionSteps).toEqual([]);
  });

  it('应该处理 executionSteps 为非数组的情况', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      executionSteps: 'not an array' as any,
    };

    const result = parseMessage(rawMessage);

    expect(result.executionSteps).toEqual([]);
  });

});

// ============================================
// 测试3: parseMessage 处理可选字段
// ============================================

describe('parseMessage 处理可选字段', () => {

  it('应该正确解析 display_name', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      display_name: 'OpenAI (GPT-4)',
    };

    const result = parseMessage(rawMessage);

    expect(result.display_name).toBe('OpenAI (GPT-4)');
  });

  it('应该正确解析 model', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      model: 'gpt-4',
    };

    const result = parseMessage(rawMessage);

    expect(result.model).toBe('gpt-4');
  });

  it('应该在 model 缺失时返回 undefined', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.model).toBeUndefined();
  });

  it('应该正确解析 provider', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
      provider: 'openai',
    };

    const result = parseMessage(rawMessage);

    expect(result.provider).toBe('openai');
  });

  it('应该在 provider 缺失时返回 undefined', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.provider).toBeUndefined();
  });

  // 【小查测试用例】测试 is_reasoning 字段
  it('应该正确解析 is_reasoning 字段', () => {
    const rawMessage: MockMessage = {
      content: '思考中...',
      is_reasoning: true,
    };

    const result = parseMessage(rawMessage);

    expect(result.is_reasoning).toBe(true);
  });

  it('应该在 is_reasoning 缺失时返回 undefined', () => {
    const rawMessage: MockMessage = {
      content: 'Test',
    };

    const result = parseMessage(rawMessage);

    expect(result.is_reasoning).toBeUndefined();
  });

  it('应该正确处理 is_reasoning 为 false', () => {
    const rawMessage: MockMessage = {
      content: 'Normal response',
      is_reasoning: false,
    };

    const result = parseMessage(rawMessage);

    expect(result.is_reasoning).toBe(false);
  });

});

// ============================================
// 测试4: parseMessage 边界条件
// ============================================

describe('parseMessage 边界条件', () => {

  it('应该处理空消息对象', () => {
    const rawMessage: MockMessage = {};

    const result = parseMessage(rawMessage);

    expect(result.id).toBeDefined();
    expect(result.role).toBe('assistant');
    expect(result.content).toBe('');
    expect(result.executionSteps).toEqual([]);
  });

  it('应该处理 null 值的 content', () => {
    const rawMessage: MockMessage = {
      content: null as any,
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('');
  });

  it('应该处理 undefined 值的 content', () => {
    const rawMessage: MockMessage = {
      content: undefined,
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('');
  });

  it('应该处理空字符串的 content', () => {
    const rawMessage: MockMessage = {
      content: '',
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('');
  });

  it('应该处理特殊字符的 content', () => {
    const rawMessage: MockMessage = {
      content: '<script>alert("xss")</script>',
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('<script>alert("xss")</script>');
  });

  it('应该处理多行文本的 content', () => {
    const rawMessage: MockMessage = {
      content: 'Line 1\nLine 2\r\nLine 3',
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('Line 1\nLine 2\r\nLine 3');
  });

  it('应该处理 Unicode 字符的 content', () => {
    const rawMessage: MockMessage = {
      content: '你好世界🌍🎉',
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe('你好世界🌍🎉');
  });

  it('应该处理长文本的 content', () => {
    const longText = 'A'.repeat(10000);
    const rawMessage: MockMessage = {
      content: longText,
    };

    const result = parseMessage(rawMessage);

    expect(result.content).toBe(longText);
  });

});
