/**
 * API Integration Tests
 * 
 * @author 小新
 * @description Integration tests for API services with mock server
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { chatApi, configApi, sessionApi, securityApi } from '../../services/api';
import axios from 'axios';

// Mock axios
vi.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('API Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Chat API', () => {
    it('should send message successfully', async () => {
      const mockResponse = {
        data: {
          response: 'Hello! How can I help you?',
          session_id: 'test-session',
          message_id: 'msg-123',
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await chatApi.sendMessage({
        message: 'Hello',
        session_id: 'test-session',
      });

      expect(result.response).toBe('Hello! How can I help you?');
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          message: 'Hello',
          session_id: 'test-session',
        })
      );
    });

    it('should validate service status', async () => {
      const mockResponse = {
        data: {
          success: true,
          provider: 'zhipuai',
          model: 'glm-4-flash',
          message: 'Service is running',
        },
      };

      mockedAxios.get.mockResolvedValueOnce(mockResponse);

      const result = await chatApi.validateService();

      expect(result.success).toBe(true);
      expect(result.provider).toBe('zhipuai');
      expect(result.model).toBe('glm-4-flash');
    });

    it('should switch provider successfully', async () => {
      const mockResponse = {
        data: {
          success: true,
          provider: 'opencode',
          model: 'MiniMax-M2.5',
          message: 'Provider switched',
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await chatApi.switchProvider('opencode');

      expect(result.success).toBe(true);
      expect(result.provider).toBe('opencode');
    });

    it('should handle API errors gracefully', async () => {
      const errorMessage = 'Network error';
      mockedAxios.post.mockRejectedValueOnce(new Error(errorMessage));

      await expect(
        chatApi.sendMessage({ message: 'Hello', session_id: 'test' })
      ).rejects.toThrow(errorMessage);
    });
  });

  describe('Config API', () => {
    it('should get model config', async () => {
      const mockConfig = {
        provider: 'zhipuai',
        model: 'glm-4-flash',
        apiKey: '***',
        temperature: 0.7,
        maxTokens: 2048,
      };

      mockedAxios.get.mockResolvedValueOnce({ data: mockConfig });

      const result = await configApi.getModelConfig();

      expect(result.provider).toBe('zhipuai');
      expect(result.model).toBe('glm-4-flash');
    });

    it('should update model config', async () => {
      const updateData = {
        provider: 'opencode' as const,
        model: 'MiniMax-M2.5',
        apiKey: 'new-api-key',
      };

      const mockResponse = {
        data: {
          success: true,
          message: 'Config updated',
          config: updateData,
        },
      };

      mockedAxios.put.mockResolvedValueOnce(mockResponse);

      const result = await configApi.updateModelConfig(updateData);

      expect(result.success).toBe(true);
      expect(mockedAxios.put).toHaveBeenCalledWith(
        expect.stringContaining('/config/model'),
        updateData
      );
    });
  });

  describe('Session API', () => {
    it('should get session list', async () => {
      const mockSessions = [
        {
          id: 'session-1',
          title: 'Test Session 1',
          provider: 'zhipuai',
          createdAt: '2026-02-17T10:00:00Z',
          updatedAt: '2026-02-17T10:30:00Z',
          messageCount: 10,
        },
        {
          id: 'session-2',
          title: 'Test Session 2',
          provider: 'opencode',
          createdAt: '2026-02-17T11:00:00Z',
          updatedAt: '2026-02-17T11:30:00Z',
          messageCount: 5,
        },
      ];

      mockedAxios.get.mockResolvedValueOnce({ data: mockSessions });

      const result = await sessionApi.getSessions({ limit: 10 });

      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('session-1');
      expect(result[1].provider).toBe('opencode');
    });

    it('should delete session', async () => {
      mockedAxios.delete.mockResolvedValueOnce({
        data: { success: true },
      });

      await sessionApi.deleteSession('session-1');

      expect(mockedAxios.delete).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/session-1')
      );
    });

    it('should clear all sessions', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { success: true, deletedCount: 5 },
      });

      await sessionApi.clearAllSessions();

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/clear')
      );
    });
  });

  describe('Security API', () => {
    it('should get security config', async () => {
      const mockConfig = {
        contentFilterEnabled: true,
        contentFilterLevel: 'medium',
        whitelistEnabled: false,
        commandWhitelist: ['ls', 'cat', 'pwd'],
        commandBlacklist: ['rm -rf /', 'sudo'],
        confirmDangerousOps: true,
        maxFileSize: 100,
      };

      mockedAxios.get.mockResolvedValueOnce({ data: mockConfig });

      const result = await securityApi.getSecurityConfig();

      expect(result.contentFilterEnabled).toBe(true);
      expect(result.contentFilterLevel).toBe('medium');
      expect(result.commandWhitelist).toContain('ls');
    });

    it('should update security config', async () => {
      const updateData = {
        contentFilterEnabled: true,
        contentFilterLevel: 'high' as const,
      };

      mockedAxios.put.mockResolvedValueOnce({
        data: { success: true, config: updateData },
      });

      const result = await securityApi.updateSecurityConfig(updateData);

      expect(result.success).toBe(true);
      expect(result.config.contentFilterLevel).toBe('high');
    });

    it('should validate command', async () => {
      const mockResponse = {
        data: {
          allowed: true,
          reason: null,
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await securityApi.validateCommand('ls -la');

      expect(result.allowed).toBe(true);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/security/validate-command'),
        { command: 'ls -la' }
      );
    });

    it('should reject dangerous commands', async () => {
      const mockResponse = {
        data: {
          allowed: false,
          reason: 'Command is in blacklist',
        },
      };

      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await securityApi.validateCommand('rm -rf /');

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('blacklist');
    });
  });

  describe('API Error Handling', () => {
    it('should handle 401 unauthorized', async () => {
      const error = {
        response: {
          status: 401,
          data: { message: 'Unauthorized' },
        },
      };

      mockedAxios.get.mockRejectedValueOnce(error);

      await expect(chatApi.validateService()).rejects.toBeDefined();
    });

    it('should handle 500 server error', async () => {
      const error = {
        response: {
          status: 500,
          data: { message: 'Internal Server Error' },
        },
      };

      mockedAxios.get.mockRejectedValueOnce(error);

      await expect(chatApi.validateService()).rejects.toBeDefined();
    });

    it('should handle network timeout', async () => {
      const error = new Error('Network Error');
      mockedAxios.get.mockRejectedValueOnce(error);

      await expect(chatApi.validateService()).rejects.toThrow('Network Error');
    });
  });
});
