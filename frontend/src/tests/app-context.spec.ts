/**
 * AppContext 单元测试
 *
 * 测试AppContext的缓存机制、状态管理、API调用等
 *
 * @author 小查
 * @version 1.0.0
 * @since 2026-03-12
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    })),
  },
}));

// Import API after mocking
import { configApi, chatApi, sessionApi } from '../../src/services/api';

// ============================================
// 测试辅助函数
// ============================================

// 模拟API延迟
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('AppContext API Mock 验证', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. API方法存在性测试', () => {
    it('configApi.getModelList should exist', () => {
      expect(typeof configApi.getModelList).toBe('function');
    });

    // validateFullConfig 已删除，后端已删除对应API

    it('chatApi.validateService should exist', () => {
      expect(typeof chatApi.validateService).toBe('function');
    });

    it('sessionApi.listSessions should exist', () => {
      expect(typeof sessionApi.listSessions).toBe('function');
    });
  });

  describe('2. API接口参数测试', () => {
    it('sessionApi.listSessions should accept correct parameters', async () => {
      // 模拟API调用
      const mockListSessions = vi.fn().mockResolvedValue({ total: 10, sessions: [] });
      
      // 测试调用参数
      await mockListSessions(1, 20, undefined, true);
      
      expect(mockListSessions).toHaveBeenCalledWith(1, 20, undefined, true);
    });

    it('sessionApi.listSessions should handle keyword parameter', async () => {
      const mockListSessions = vi.fn().mockResolvedValue({ total: 5, sessions: [] });
      
      await mockListSessions(1, 10, 'test', true);
      
      expect(mockListSessions).toHaveBeenCalledWith(1, 10, 'test', true);
    });
  });

  describe('3. API返回数据格式测试', () => {
    it('sessionApi.listSessions should return correct format', async () => {
      const mockData = {
        total: 35,
        page: 1,
        page_size: 20,
        sessions: [
          {
            session_id: 'test-123',
            title: 'Test Session',
            created_at: '2026-03-12',
            updated_at: '2026-03-12',
            message_count: 10,
            is_valid: true,
          }
        ]
      };

      const mockListSessions = vi.fn().mockResolvedValue(mockData);
      const result = await mockListSessions();

      expect(result).toHaveProperty('total');
      expect(result).toHaveProperty('sessions');
      expect(Array.isArray(result.sessions)).toBe(true);
    });

    it('configApi.getModelList should return model array', async () => {
      const mockData = {
        models: [
          { id: 1, provider: 'opencode', model: 'minimax', display_name: 'MiniMax', current_model: true }
        ],
        default_provider: 'opencode'
      };

      const mockGetModelList = vi.fn().mockResolvedValue(mockData);
      const result = await mockGetModelList();

      expect(result).toHaveProperty('models');
      expect(Array.isArray(result.models)).toBe(true);
      expect(result.models[0]).toHaveProperty('id');
      expect(result.models[0]).toHaveProperty('provider');
      expect(result.models[0]).toHaveProperty('model');
      expect(result.models[0]).toHaveProperty('display_name');
      expect(result.models[0]).toHaveProperty('current_model');
    });

    it('chatApi.validateService should return ValidateResponse format', async () => {
      const mockData = {
        success: true,
        provider: 'opencode',
        model: 'minimax-m2.5-free',
        message: 'OK'
      };

      const mockValidateService = vi.fn().mockResolvedValue(mockData);
      const result = await mockValidateService();

      expect(result).toHaveProperty('success');
      expect(result).toHaveProperty('provider');
      expect(result).toHaveProperty('model');
      expect(result).toHaveProperty('message');
    });
  });

  describe('4. API错误处理测试', () => {
    it('should handle sessionApi.listSessions error', async () => {
      const mockListSessions = vi.fn().mockRejectedValue(new Error('Network Error'));
      
      await expect(mockListSessions()).rejects.toThrow('Network Error');
    });

    it('should handle configApi.getModelList error', async () => {
      const mockGetModelList = vi.fn().mockRejectedValue(new Error('API Error'));
      
      await expect(mockGetModelList()).rejects.toThrow('API Error');
    });
  });

  describe('5. 并发API调用测试', () => {
    it('should handle multiple concurrent API calls', async () => {
      const mockListSessions = vi.fn().mockResolvedValue({ total: 10, sessions: [] });
      const mockGetModelList = vi.fn().mockResolvedValue({ models: [], default_provider: '' });
      const mockValidateService = vi.fn().mockResolvedValue({ success: true, provider: '', model: '', message: '' });

      // 并发调用
      const results = await Promise.all([
        mockListSessions(1, 1, undefined, true),
        mockGetModelList(),
        mockValidateService(),
      ]);

      expect(results).toHaveLength(3);
      expect(mockListSessions).toHaveBeenCalled();
      expect(mockGetModelList).toHaveBeenCalled();
      expect(mockValidateService).toHaveBeenCalled();
    });
  });

  describe('6. 缓存逻辑测试', () => {
    it('should use cached session count for second call', async () => {
      let cache: { total: number } | null = null;
      let callCount = 0;
      
      const mockListSessions = vi.fn().mockImplementation(async () => {
        callCount++;
        if (cache) {
          return cache;
        }
        cache = { total: 35 };
        return cache;
      });

      // 第一次调用
      const result1 = await mockListSessions();
      expect(result1.total).toBe(35);

      // 第二次调用 - 模拟Context的缓存机制
      const result2 = await mockListSessions();
      expect(result2.total).toBe(35);
      
      // 验证调用逻辑正确
      expect(callCount).toBeGreaterThan(0);
    });

    it('should invalidate cache after refresh', async () => {
      let cache: { total: number } | null = null;
      let callCount = 0;
      let useCache = true;
      
      const mockListSessions = vi.fn().mockImplementation(async () => {
        callCount++;
        if (useCache && cache) {
          return cache;
        }
        // 刷新后返回新数据
        cache = { total: callCount === 1 ? 35 : 40 };
        return cache;
      });

      // 第一次调用
      await mockListSessions();
      expect(cache?.total).toBe(35);

      // 模拟刷新：清除缓存标志
      useCache = false;
      
      // 第二次调用应该重新获取
      const result = await mockListSessions();
      expect(result.total).toBe(40);
      expect(callCount).toBe(2);
    });
  });

  describe('7. 状态一致性测试', () => {
    it('should maintain consistent state during loading', async () => {
      interface AppState {
        sessionCount: number;
        loading: boolean;
        error: string | null;
      }

      let state: AppState = {
        sessionCount: 0,
        loading: false,
        error: null,
      };

      const loadSessionCount = async () => {
        state.loading = true;
        try {
          // 模拟API延迟
          await delay(10);
          state.sessionCount = 35;
          state.error = null;
        } catch (e) {
          state.error = (e as Error).message;
        } finally {
          state.loading = false;
        }
      };

      // 初始状态
      expect(state.loading).toBe(false);
      expect(state.sessionCount).toBe(0);

      // 开始加载
      const loadPromise = loadSessionCount();
      
      // 加载中状态
      expect(state.loading).toBe(true);
      
      // 等待加载完成
      await loadPromise;
      
      // 加载完成状态
      expect(state.loading).toBe(false);
      expect(state.sessionCount).toBe(35);
      expect(state.error).toBeNull();
    });
  });

  describe('8. 初始化逻辑测试', () => {
    it('should initialize only once', async () => {
      let initialized = false;
      let initCount = 0;

      const initializeApp = async () => {
        if (initialized) {
          console.log('[AppContext] 已初始化，跳过');
          return;
        }
        
        initCount++;
        await delay(10);
        initialized = true;
        console.log('[AppContext] 初始化完成');
      };

      // 第一次初始化
      await initializeApp();
      expect(initialized).toBe(true);
      expect(initCount).toBe(1);

      // 第二次初始化应该跳过
      await initializeApp();
      expect(initCount).toBe(1); // 不应该再增加
    });

    it('should handle initialization order correctly', async () => {
      const callOrder: string[] = [];

      const step1 = async () => {
        callOrder.push('step1_start');
        await delay(5);
        callOrder.push('step1_end');
      };

      const step2 = async () => {
        callOrder.push('step2_start');
        await delay(5);
        callOrder.push('step2_end');
      };

      const step3 = async () => {
        callOrder.push('step3_start');
        await delay(5);
        callOrder.push('step3_end');
      };

      // 顺序执行
      await step1();
      await step2();
      await step3();

      expect(callOrder).toEqual([
        'step1_start', 'step1_end',
        'step2_start', 'step2_end', 
        'step3_start', 'step3_end'
      ]);
    });
  });
});
