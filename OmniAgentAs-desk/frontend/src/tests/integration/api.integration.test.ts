/**
 * API Integration Tests
 *
 * @author 小新
 * @description Integration tests for API services with mock server
 * @update 2026-02-18 修复API调用以匹配实际API定义 by 小新
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock axios before importing the API
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
import { chatApi, configApi, sessionApi, securityApi } from '../../services/api';

describe('API Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Chat API', () => {
    it('should have sendMessage method', () => {
      expect(typeof chatApi.sendMessage).toBe('function');
    });

    it('should have validateService method', () => {
      expect(typeof chatApi.validateService).toBe('function');
    });

    it('should have switchProvider method', () => {
      expect(typeof chatApi.switchProvider).toBe('function');
    });
  });

  describe('Config API', () => {
    it('should have getConfig method', () => {
      expect(typeof configApi.getConfig).toBe('function');
    });

    it('should have updateConfig method', () => {
      expect(typeof configApi.updateConfig).toBe('function');
    });

    it('should have validateConfig method', () => {
      expect(typeof configApi.validateConfig).toBe('function');
    });
  });

  describe('Session API', () => {
    it('should have createSession method', () => {
      expect(typeof sessionApi.createSession).toBe('function');
    });

    it('should have listSessions method', () => {
      expect(typeof sessionApi.listSessions).toBe('function');
    });

    it('should have deleteSession method', () => {
      expect(typeof sessionApi.deleteSession).toBe('function');
    });
  });

  describe('Security API', () => {
    it('should have checkCommand method', () => {
      expect(typeof securityApi.checkCommand).toBe('function');
    });
  });
});
