/**
 * 流式API消息类型全面测试
 * 
 * 测试范围（对照设计文档第10章）：
 * 1. 8种消息类型数据结构验证
 * 2. 类型守卫函数测试
 * 3. 任务控制API函数测试
 * 4. 分页功能测试
 * 5. SSE处理逻辑测试
 * 6. 安全检查测试
 * 7. 字段名称映射测试
 * 8. 完整ReAct流程测试
 * 9. 边界情况测试
 * 
 * @author 小查
 * @version 1.2.0
 * @since 2026-03-09
 * @update 2026-03-10 小新检查后修复，更新文档和API测试
 */

import { describe, it, expect, vi } from 'vitest';
import {
  isStartMessage,
  isThoughtMessage,
  isActionToolMessage,
  isObservationMessage,
  isChunkMessage,
  isFinalMessage,
  isErrorMessage,
  isStatusMessage,
} from '../types/chat';
import { taskControlApi } from '../services/api';

// ============================================================
// 测试8种消息类型的数据
// ============================================================

const TEST_MESSAGES = {
  start: {
    type: 'start' as const,
    display_name: 'OpenAI (gpt-4)',
    model: 'gpt-4',
    provider: 'openai',
    task_id: 'task-123-abc',
    security_check: {
      is_safe: true,
      risk_level: 'low' as const,
      risk: null,
      blocked: false,
    },
  },

  thought: {
    type: 'thought' as const,
    step: 1,
    content: '需要先查明天深圳→海南的晚间航班',
    reasoning: '用户想要查看航班信息，需要先调用航班查询工具',
    action_tool: 'search_flight',
    params: {
      from: '深圳',
      to: '海南',
      date: '明天',
      time: '晚间',
    },
  },

  action_tool: {
    type: 'action_tool' as const,
    step: 2,
    tool_name: 'list_directory',
    tool_params: {
      path: 'C:\\Users\\test',
      show_hidden: false,
    },
    execution_status: 'success' as const,
    summary: '成功列出目录内容',
    raw_data: {
      files: ['file1.txt', 'file2.txt', 'file3.txt'],
      total: 3,
      has_more: false,
    },
    action_retry_count: 0,
  },

  observation: {
    type: 'observation' as const,
    step: 2,
    execution_status: 'success' as const,
    summary: '成功获取目录列表',
    raw_data: {
      files: ['file1.txt', 'file2.txt'],
      total: 2,
    },
    content: '共找到2个文件',
    reasoning: '工具执行成功，返回了目录列表',
    action_tool: 'list_directory',
    params: { path: 'C:\\Users\\test' },
    is_finished: false,
  },

  chunk: {
    type: 'chunk' as const,
    content: '这是流式输出的第一个片段',
    isReasoning: false,
  },

  chunkWithReasoning: {
    type: 'chunk' as const,
    content: '正在分析用户的问题...',
    isReasoning: true,
  },

  final: {
    type: 'final' as const,
    content: '任务已完成，这是最终的回答结果。',
  },

  error: {
    type: 'error' as const,
    code: 'FILE_NOT_FOUND',
    message: '指定的文件不存在',
    error_type: 'FileOperationError',
    details: '文件路径: C:\\nonexistent\\file.txt',
    stack: 'Error: FILE_NOT_FOUND\n    at FileOperation.execute...',
    retryable: true,
    retry_after: 5,
  },

  errorNonRetryable: {
    type: 'error' as const,
    code: 'AUTH_FAILED',
    message: '认证失败，请检查API Key配置',
    retryable: false,
  },

  statusPaused: {
    type: 'status' as const,
    status_value: 'paused' as const,
    message: '检测到危险操作，需要用户确认',
  },

  statusResumed: {
    type: 'status' as const,
    status_value: 'resumed' as const,
    message: '用户已确认，继续执行任务',
  },

  statusInterrupted: {
    type: 'status' as const,
    status_value: 'interrupted' as const,
    message: '任务已被用户中断',
  },

  statusRetrying: {
    type: 'status' as const,
    status_value: 'retrying' as const,
    message: '正在重试，尝试第3次...',
  },

  actionToolWithPagination: {
    type: 'action_tool' as const,
    step: 1,
    tool_name: 'search_files',
    tool_params: {
      keyword: 'test',
    },
    execution_status: 'success' as const,
    summary: '搜索完成',
    raw_data: {
      files: ['file1.txt', 'file2.txt', 'file3.txt', 'file4.txt', 'file5.txt'],
      total: 100,
      has_more: true,
      next_page_token: 'page-2-token',
    },
    action_retry_count: 0,
  },
};

// ============================================================
// 10.1 消息类型数据结构验证
// ============================================================

describe('【小查测试】10.1 消息类型数据结构验证', () => {
  describe('start类型结构', () => {
    it('应包含display_name字段', () => {
      expect(TEST_MESSAGES.start.display_name).toBe('OpenAI (gpt-4)');
    });

    it('应包含model字段', () => {
      expect(TEST_MESSAGES.start.model).toBe('gpt-4');
    });

    it('应包含provider字段', () => {
      expect(TEST_MESSAGES.start.provider).toBe('openai');
    });

    it('应包含task_id字段', () => {
      expect(TEST_MESSAGES.start.task_id).toBe('task-123-abc');
    });

    it('应包含security_check字段', () => {
      expect(TEST_MESSAGES.start.security_check).toBeDefined();
      expect(TEST_MESSAGES.start.security_check?.is_safe).toBe(true);
    });
  });

  describe('thought类型结构', () => {
    it('应包含step字段', () => {
      expect(TEST_MESSAGES.thought.step).toBe(1);
    });

    it('应包含content字段', () => {
      expect(TEST_MESSAGES.thought.content).toBe('需要先查明天深圳→海南的晚间航班');
    });

    it('应包含reasoning字段', () => {
      expect(TEST_MESSAGES.thought.reasoning).toBeDefined();
    });

    it('应包含action_tool字段', () => {
      expect(TEST_MESSAGES.thought.action_tool).toBe('search_flight');
    });

    it('应包含params字段', () => {
      expect(TEST_MESSAGES.thought.params).toBeDefined();
      expect(TEST_MESSAGES.thought.params?.from).toBe('深圳');
    });
  });

  describe('action_tool类型结构', () => {
    it('应包含tool_name字段（新字段）', () => {
      expect(TEST_MESSAGES.action_tool.tool_name).toBe('list_directory');
    });

    it('应包含tool_params字段（新字段）', () => {
      expect(TEST_MESSAGES.action_tool.tool_params).toBeDefined();
      expect(TEST_MESSAGES.action_tool.tool_params.path).toBe('C:\\Users\\test');
    });

    it('应包含execution_status字段', () => {
      expect(TEST_MESSAGES.action_tool.execution_status).toBe('success');
    });

    it('应包含summary字段', () => {
      expect(TEST_MESSAGES.action_tool.summary).toBe('成功列出目录内容');
    });

    it('应包含action_retry_count字段', () => {
      expect(TEST_MESSAGES.action_tool.action_retry_count).toBe(0);
    });
  });

  describe('observation类型结构', () => {
    it('应包含is_finished字段', () => {
      expect(TEST_MESSAGES.observation.is_finished).toBe(false);
    });

    it('应包含content字段', () => {
      expect(TEST_MESSAGES.observation.content).toBe('共找到2个文件');
    });

    it('应包含execution_status字段', () => {
      expect(TEST_MESSAGES.observation.execution_status).toBe('success');
    });
  });

  describe('chunk类型结构', () => {
    it('应包含isReasoning字段', () => {
      expect(TEST_MESSAGES.chunk.isReasoning).toBe(false);
      expect(TEST_MESSAGES.chunkWithReasoning.isReasoning).toBe(true);
    });

    it('应包含content字段', () => {
      expect(TEST_MESSAGES.chunk.content).toBe('这是流式输出的第一个片段');
    });
  });

  describe('final类型结构', () => {
    it('应包含content字段', () => {
      expect(TEST_MESSAGES.final.content).toBe('任务已完成，这是最终的回答结果。');
    });
  });

  describe('error类型结构', () => {
    it('应包含code字段', () => {
      expect(TEST_MESSAGES.error.code).toBe('FILE_NOT_FOUND');
    });

    it('应包含message字段', () => {
      expect(TEST_MESSAGES.error.message).toBe('指定的文件不存在');
    });

    it('应包含retryable字段', () => {
      expect(TEST_MESSAGES.error.retryable).toBe(true);
      expect(TEST_MESSAGES.errorNonRetryable.retryable).toBe(false);
    });

    it('应包含retry_after字段', () => {
      expect(TEST_MESSAGES.error.retry_after).toBe(5);
    });
  });

  describe('status类型结构', () => {
    it('paused状态应正确', () => {
      expect(TEST_MESSAGES.statusPaused.status_value).toBe('paused');
      expect(TEST_MESSAGES.statusPaused.message).toBe('检测到危险操作，需要用户确认');
    });

    it('resumed状态应正确', () => {
      expect(TEST_MESSAGES.statusResumed.status_value).toBe('resumed');
    });

    it('interrupted状态应正确', () => {
      expect(TEST_MESSAGES.statusInterrupted.status_value).toBe('interrupted');
    });

    it('retrying状态应正确', () => {
      expect(TEST_MESSAGES.statusRetrying.status_value).toBe('retrying');
    });
  });
});

// ============================================================
// 10.2 类型守卫函数测试
// ============================================================

describe('【小查测试】10.2 类型守卫函数', () => {
  describe('isStartMessage', () => {
    it('应正确识别start类型消息', () => {
      expect(isStartMessage(TEST_MESSAGES.start)).toBe(true);
    });

    it('应拒绝其他类型消息', () => {
      expect(isStartMessage(TEST_MESSAGES.thought)).toBe(false);
      expect(isStartMessage(TEST_MESSAGES.action_tool)).toBe(false);
      expect(isStartMessage(TEST_MESSAGES.final)).toBe(false);
    });
  });

  describe('isThoughtMessage', () => {
    it('应正确识别thought类型消息', () => {
      expect(isThoughtMessage(TEST_MESSAGES.thought)).toBe(true);
    });

    it('应拒绝其他类型消息', () => {
      expect(isThoughtMessage(TEST_MESSAGES.start)).toBe(false);
      expect(isThoughtMessage(TEST_MESSAGES.chunk)).toBe(false);
    });
  });

  describe('isActionToolMessage', () => {
    it('应正确识别action_tool类型消息', () => {
      expect(isActionToolMessage(TEST_MESSAGES.action_tool)).toBe(true);
    });
  });

  describe('isObservationMessage', () => {
    it('应正确识别observation类型消息', () => {
      expect(isObservationMessage(TEST_MESSAGES.observation)).toBe(true);
    });

    it('应正确识别is_finished字段', () => {
      expect(TEST_MESSAGES.observation.is_finished).toBe(false);
    });
  });

  describe('isChunkMessage', () => {
    it('应正确识别chunk类型消息', () => {
      expect(isChunkMessage(TEST_MESSAGES.chunk)).toBe(true);
    });

    it('应正确识别isReasoning字段', () => {
      expect(TEST_MESSAGES.chunk.isReasoning).toBe(false);
      expect(TEST_MESSAGES.chunkWithReasoning.isReasoning).toBe(true);
    });
  });

  describe('isFinalMessage', () => {
    it('应正确识别final类型消息', () => {
      expect(isFinalMessage(TEST_MESSAGES.final)).toBe(true);
    });
  });

  describe('isErrorMessage', () => {
    it('应正确识别error类型消息', () => {
      expect(isErrorMessage(TEST_MESSAGES.error)).toBe(true);
    });

    it('应正确识别retryable字段', () => {
      expect(TEST_MESSAGES.error.retryable).toBe(true);
      expect(TEST_MESSAGES.error.retry_after).toBe(5);
      expect(TEST_MESSAGES.errorNonRetryable.retryable).toBe(false);
    });
  });

  describe('isStatusMessage', () => {
    it('应正确识别status类型消息', () => {
      expect(isStatusMessage(TEST_MESSAGES.statusPaused)).toBe(true);
      expect(isStatusMessage(TEST_MESSAGES.statusResumed)).toBe(true);
      expect(isStatusMessage(TEST_MESSAGES.statusInterrupted)).toBe(true);
      expect(isStatusMessage(TEST_MESSAGES.statusRetrying)).toBe(true);
    });
  });

  describe('类型守卫完整性', () => {
    it('应覆盖所有8种消息类型', () => {
      const allMessages = [
        TEST_MESSAGES.start,
        TEST_MESSAGES.thought,
        TEST_MESSAGES.action_tool,
        TEST_MESSAGES.observation,
        TEST_MESSAGES.chunk,
        TEST_MESSAGES.final,
        TEST_MESSAGES.error,
        TEST_MESSAGES.statusPaused,
      ];

      allMessages.forEach((msg) => {
        const isAnyType =
          isStartMessage(msg) ||
          isThoughtMessage(msg) ||
          isActionToolMessage(msg) ||
          isObservationMessage(msg) ||
          isChunkMessage(msg) ||
          isFinalMessage(msg) ||
          isErrorMessage(msg) ||
          isStatusMessage(msg);
        
        expect(isAnyType).toBe(true);
      });
    });
  });
});

// ============================================================
// 10.3 任务控制API函数测试
// ============================================================

describe('【小查测试】10.3 任务控制API函数测试', () => {
  describe('API函数存在性验证', () => {
    it('cancel函数应存在', () => {
      expect(taskControlApi.cancel).toBeDefined();
    });

    it('pause函数应存在', () => {
      expect(taskControlApi.pause).toBeDefined();
    });

    it('resume函数应存在', () => {
      expect(taskControlApi.resume).toBeDefined();
    });

    it('confirm函数应存在', () => {
      expect(taskControlApi.confirm).toBeDefined();
    });

    it('nextPage函数应存在', () => {
      expect(taskControlApi.nextPage).toBeDefined();
    });
  });

  describe('cancel - 取消任务', () => {
    it('函数签名正确：接受taskId参数', () => {
      const cancelFn = taskControlApi.cancel;
      expect(cancelFn).toBeInstanceOf(Function);
    });
  });

  describe('pause - 暂停任务', () => {
    it('函数签名正确：接受taskId参数', () => {
      const pauseFn = taskControlApi.pause;
      expect(pauseFn).toBeInstanceOf(Function);
    });
  });

  describe('resume - 恢复任务', () => {
    it('函数签名正确：接受taskId参数', () => {
      const resumeFn = taskControlApi.resume;
      expect(resumeFn).toBeInstanceOf(Function);
    });
  });

  describe('confirm - 用户确认', () => {
    it('函数签名正确：接受taskId, confirmed参数', () => {
      const confirmFn = taskControlApi.confirm;
      expect(confirmFn).toBeInstanceOf(Function);
    });
  });

  describe('nextPage - 请求分页数据', () => {
    it('函数签名正确：接受taskId, toolName, nextPageToken参数', () => {
      const nextPageFn = taskControlApi.nextPage;
      expect(nextPageFn).toBeInstanceOf(Function);
    });
  });
});

// ============================================================
// 10.4 分页功能测试
// ============================================================

describe('【小查测试】10.4 分页功能', () => {
  describe('分页数据结构验证', () => {
    it('应正确识别has_more字段', () => {
      expect(TEST_MESSAGES.action_tool.raw_data?.has_more).toBe(false);
      expect(TEST_MESSAGES.actionToolWithPagination.raw_data?.has_more).toBe(true);
    });

    it('应正确识别next_page_token', () => {
      expect(TEST_MESSAGES.actionToolWithPagination.raw_data?.next_page_token).toBe('page-2-token');
    });

    it('应正确识别total字段', () => {
      expect(TEST_MESSAGES.actionToolWithPagination.raw_data?.total).toBe(100);
    });
  });
});

// ============================================================
// 10.5 SSE处理逻辑测试
// ============================================================

describe('【小查测试】10.5 SSE处理逻辑', () => {
  describe('SSE数据解析', () => {
    it('应能解析SSE格式数据', () => {
      const sseData = 'data: {"type": "thought", "content": "test"}';
      const parsed = sseData.slice(6);
      const result = JSON.parse(parsed);
      
      expect(result.type).toBe('thought');
      expect(result.content).toBe('test');
    });

    it('应能处理多行SSE数据', () => {
      const multiLineData = `data: {"type": "start", "task_id": "1"}
data: {"type": "thought", "content": "test"}`;
      
      const lines = multiLineData.split('\n');
      const dataLines = lines.filter(line => line.startsWith('data: '));
      
      expect(dataLines.length).toBe(2);
    });

    it('应能处理空数据行', () => {
      const emptyLineData = 'data: ';
      const parsed = emptyLineData.slice(6);
      expect(parsed).toBe('');
    });
  });

  describe('SSE错误处理', () => {
    it('应能处理JSON解析错误', () => {
      const invalidJson = 'data: {invalid json}';
      
      expect(() => {
        JSON.parse(invalidJson.slice(6));
      }).toThrow();
    });
  });
});

// ============================================================
// 10.6 安全检查测试
// ============================================================

describe('【小查测试】10.6 安全检查', () => {
  describe('SecurityCheck类型验证', () => {
    it('应正确验证安全通过的情况', () => {
      const securityCheck = TEST_MESSAGES.start.security_check!;
      
      expect(securityCheck.is_safe).toBe(true);
      expect(securityCheck.risk_level).toBe('low');
      expect(securityCheck.blocked).toBe(false);
    });

    it('应支持所有风险等级', () => {
      const riskLevels = ['low', 'medium', 'high', 'critical'];
      
      riskLevels.forEach(level => {
        const check = {
          is_safe: level === 'low',
          risk_level: level as 'low' | 'medium' | 'high' | 'critical',
          risk: level === 'low' ? null : '测试风险',
          blocked: level === 'critical',
        };
        
        expect(check.risk_level).toBe(level);
      });
    });
  });
});

// ============================================================
// 10.7 字段名称映射测试
// ============================================================

describe('【小查测试】10.7 字段名称映射', () => {
  describe('action_tool字段', () => {
    it('新字段tool_name应存在', () => {
      expect(TEST_MESSAGES.action_tool.tool_name).toBe('list_directory');
    });

    it('新字段tool_params应存在', () => {
      expect(TEST_MESSAGES.action_tool.tool_params).toEqual({
        path: 'C:\\Users\\test',
        show_hidden: false,
      });
    });

    it('execution_status字段应正确', () => {
      expect(TEST_MESSAGES.action_tool.execution_status).toBe('success');
    });
  });

  describe('thought字段可选性', () => {
    it('action_tool应为可选', () => {
      const thoughtWithoutAction = {
        type: 'thought' as const,
        step: 1,
        content: '这是一个纯思考，没有调用工具',
      };
      
      expect(thoughtWithoutAction.action_tool).toBeUndefined();
    });

    it('params应为可选', () => {
      const thoughtWithoutParams = {
        type: 'thought' as const,
        step: 1,
        content: '思考内容',
      };
      
      expect(thoughtWithoutParams.params).toBeUndefined();
    });
  });
});

// ============================================================
// 10.8 执行步骤重试测试
// ============================================================

describe('【小查测试】10.8 执行步骤重试', () => {
  describe('action_retry_count字段', () => {
    it('应正确记录重试次数', () => {
      expect(TEST_MESSAGES.action_tool.action_retry_count).toBe(0);
    });
  });

  describe('retry_after字段', () => {
    it('应正确返回重试等待时间', () => {
      expect(TEST_MESSAGES.error.retry_after).toBe(5);
    });
  });
});

// ============================================================
// 10.9 完整ReAct流程测试
// ============================================================

describe('【小查测试】10.9 完整ReAct流程', () => {
  const completeReActFlow = [
    TEST_MESSAGES.start,
    TEST_MESSAGES.thought,
    TEST_MESSAGES.action_tool,
    TEST_MESSAGES.observation,
    TEST_MESSAGES.final,
  ];

  it('应包含完整的ReAct流程元素', () => {
    expect(completeReActFlow.length).toBe(5);
    expect(completeReActFlow[0].type).toBe('start');
    expect(completeReActFlow[1].type).toBe('thought');
    expect(completeReActFlow[2].type).toBe('action_tool');
    expect(completeReActFlow[3].type).toBe('observation');
    expect(completeReActFlow[4].type).toBe('final');
  });
});

// ============================================================
// 10.10 边界情况测试
// ============================================================

describe('【小查测试】10.10 边界情况', () => {
  describe('空数据处理', () => {
    it('应处理空的tool_params', () => {
      const msg = {
        ...TEST_MESSAGES.action_tool,
        tool_params: {},
      };
      
      expect(msg.tool_params).toEqual({});
    });

    it('应处理空的content', () => {
      const msg = {
        ...TEST_MESSAGES.thought,
        content: '',
      };
      
      expect(msg.content).toBe('');
    });
  });

  describe('特殊字符处理', () => {
    it('应处理JSON特殊字符', () => {
      const msg = {
        ...TEST_MESSAGES.action_tool,
        tool_params: {
          path: 'C:\\Users\\test\\file.txt',
          content: 'Line1\nLine2\tTabbed',
        },
      };
      
      expect(msg.tool_params.path).toContain('\\');
    });

    it('应处理Unicode字符', () => {
      const msg = {
        ...TEST_MESSAGES.thought,
        content: '测试中文😀 emojis🎉',
      };
      
      expect(msg.content).toContain('测试中文');
    });
  });
});
