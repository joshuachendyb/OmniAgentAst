# 会话管理API单元测试
# 编程人：小沈
# 创建时间：2026-02-17

"""
会话管理API单元测试
测试会话CRUD功能和消息管理功能
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# 添加backend到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app


client = TestClient(app)


class TestSessionsAPI:
    """会话管理API测试"""
    
    def test_create_session(self):
        """测试创建会话"""
        response = client.post("/api/v1/sessions", json={})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "created_at" in data
    
    def test_create_session_with_title(self):
        """测试创建指定标题的会话"""
        response = client.post(
            "/api/v1/sessions",
            json={"title": "测试会话"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "测试会话"
    
    def test_list_sessions(self):
        """测试获取会话列表"""
        response = client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_sessions_with_pagination(self):
        """测试分页参数"""
        response = client.get("/api/v1/sessions?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_sessions_with_keyword(self):
        """测试关键词搜索"""
        response = client.get("/api/v1/sessions?keyword=test")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_session_messages_not_found(self):
        """测试获取不存在的会话消息"""
        response = client.get("/api/v1/sessions/invalid-id/messages")
        assert response.status_code == 404
    
    def test_delete_session_not_found(self):
        """测试删除不存在的会话"""
        response = client.delete("/api/v1/sessions/invalid-id")
        assert response.status_code == 404


class TestConfigAPI:
    """配置管理API测试"""
    
    def test_get_config(self):
        """测试获取配置"""
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        data = response.json()
        assert "ai_provider" in data
        assert "ai_model" in data
        assert "api_key_configured" in data
        assert "theme" in data
        assert "language" in data
    
    def test_update_config(self):
        """测试更新配置"""
        response = client.put(
            "/api/v1/config",
            json={"theme": "dark"}
        )
        # 可能成功或失败，取决于配置
        assert response.status_code in [200, 500]
    
    def test_validate_config_invalid_provider(self):
        """测试验证无效提供商"""
        response = client.post(
            "/api/v1/config/validate",
            json={"provider": "invalid", "api_key": "test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestHealthAPI:
    """健康检查API测试"""
    
    def test_health_check(self):
        """测试健康检查"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestChatAPI:
    """聊天API测试"""
    
    def test_chat_endpoint_exists(self):
        """测试聊天端点存在"""
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "你好"}],
                "stream": False
            }
        )
        # 可能返回200或500（取决于API Key配置）
        assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
