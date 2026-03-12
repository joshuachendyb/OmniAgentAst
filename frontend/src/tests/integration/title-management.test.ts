/**
 * 标题管理功能测试
 *
 * @author 小新
 * @description 测试标题管理相关API和功能
 * @update 2026-02-25 新增标题管理测试
 */

import { describe, it, expect } from 'vitest';

import { sessionApi } from '../../services/api';
import type {
  Session,
  GetSessionMessagesResponse,
  UpdateSessionRequest,
  UpdateSessionResponse,
  BatchTitleResponse,
} from '../../services/api';

describe('标题管理功能测试', () => {
  describe('API接口定义', () => {
    it('应该定义Session接口包含新字段', () => {
      const session: Session = {
        session_id: 'test-session-1',
        title: '测试会话',
        title_locked: false,
        title_source: 'auto',
        title_updated_at: null,
        version: 1,
        created_at: '2026-02-25T10:00:00Z',
        updated_at: '2026-02-25T10:00:00Z',
        message_count: 0,
        is_valid: true,
      };

      expect(session.session_id).toBe('test-session-1');
      expect(session.title_locked).toBe(false);
      expect(session.title_source).toBe('auto');
      expect(session.title_updated_at).toBeNull();
      expect(session.version).toBe(1);
    });

    it('应该定义GetSessionMessagesResponse接口', () => {
      const response: GetSessionMessagesResponse = {
        session_id: 'test-session-1',
        title: '测试会话',
        title_locked: false,
        title_source: 'auto',
        title_updated_at: null,
        version: 1,
        messages: [],
      };

      expect(response.session_id).toBe('test-session-1');
      expect(response.version).toBe(1);
    });

    it('应该定义UpdateSessionRequest接口', () => {
      const request: UpdateSessionRequest = {
        title: '新标题',
        version: 1,
        updated_by: 'user',
      };

      expect(request.title).toBe('新标题');
      expect(request.version).toBe(1);
      expect(request.updated_by).toBe('user');
    });

    it('应该定义UpdateSessionResponse接口', () => {
      const response: UpdateSessionResponse = {
        success: true,
        title: '新标题',
        version: 2,
        title_locked: false,
        title_updated_at: '2026-02-25T11:00:00Z',
      };

      expect(response.success).toBe(true);
      expect(response.version).toBe(2);
    });

    it('应该定义BatchTitleResponse接口', () => {
      const response: BatchTitleResponse = {
        sessions: [
          {
            session_id: 'test-session-1',
            title: '测试会话1',
            title_locked: false,
            title_updated_at: null,
            version: 1,
          },
          {
            session_id: 'test-session-2',
            title: '测试会话2',
            title_locked: true,
            title_updated_at: '2026-02-25T10:30:00Z',
            version: 2,
          },
        ],
      };

      expect(response.sessions).toHaveLength(2);
      expect(response.sessions[0].title_locked).toBe(false);
      expect(response.sessions[1].title_locked).toBe(true);
    });
  });

  describe('API函数存在性', () => {
    it('应该存在getSessionMessages函数', () => {
      expect(typeof sessionApi.getSessionMessages).toBe('function');
    });

    it('应该存在updateSession函数', () => {
      expect(typeof sessionApi.updateSession).toBe('function');
    });

    it('应该存在getSessionTitlesBatch函数', () => {
      expect(typeof sessionApi.getSessionTitlesBatch).toBe('function');
    });
  });
});
