import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """创建测试客户端fixture"""
    return TestClient(app)

class TestHealthEndpoints:
    """健康检查接口测试"""
    
    def test_health_check_success(self, client):
        """TC001: 健康检查接口应返回正常状态"""
        # Arrange
        
        # Act
        response = client.get("/api/v1/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        # 【修复】版本号应该从version.txt读取，不是硬编码0.1.0
        assert "version" in data
    
    def test_echo_endpoint(self, client):
        """TC002: 回显接口应正确返回消息"""
        # Arrange
        test_message = "Hello OmniAgent"
        
        # Act
        response = client.post("/api/v1/echo", json={"message": test_message})
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["received"] == test_message
        assert "timestamp" in data


class TestCORSMiddleware:
    """CORS中间件测试"""
    
    def test_cors_headers_present(self, client):
        """TC003: CORS响应头应正确设置"""
        # Act
        response = client.options("/api/v1/health")
        
        # Assert
        assert "access-control-allow-origin" in response.headers


class TestRootEndpoint:
    """根路由测试"""
    
    def test_root_endpoint(self, client):
        """TC004: 根路由应返回API信息"""
        # Act
        response = client.get("/")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "OmniAgentAst" in data["message"]
        assert "version" in data
