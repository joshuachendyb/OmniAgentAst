import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """创建测试客户端fixture"""
    return TestClient(app)

class TestEndToEndCommunication:
    """端到端通信测试"""
    
    def test_frontend_can_call_health_endpoint(self, client):
        """TC005: 模拟前端调用健康检查接口"""
        # Arrange - 模拟前端请求
        headers = {
            "Origin": "http://localhost:3000",
            "Content-Type": "application/json"
        }
        
        # Act
        response = client.get("/api/v1/health", headers=headers)
        
        # Assert
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
    
    def test_frontend_can_call_echo_endpoint(self, client):
        """TC006: 模拟前端调用回显接口"""
        # Arrange
        headers = {
            "Origin": "http://localhost:3000",
            "Content-Type": "application/json"
        }
        test_message = "测试消息"
        
        # Act
        response = client.post(
            "/api/v1/echo", 
            json={"message": test_message},
            headers=headers
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["received"] == test_message
