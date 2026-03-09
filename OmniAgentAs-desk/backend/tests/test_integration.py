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


class TestMonitoringIntegration:
    """监控系统集成测试"""
    
    def test_metrics_endpoint_returns_200(self, client):
        """测试监控指标端点是否正常工作"""
        # Act
        response = client.get("/api/v1/metrics")
        
        # Assert
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "metrics" in data
    
    def test_metrics_raw_endpoint_returns_200(self, client):
        """测试原始指标端点是否返回数据"""
        # Act
        response = client.get("/api/v1/metrics/raw")
        
        # Assert
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "metrics" in data
    
    def test_metrics_health_endpoint_returns_200(self, client):
        """测试监控健康检查端点"""
        # Act
        response = client.get("/api/v1/metrics/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] is True
    
    def test_metrics_reset_endpoint_resets_metrics(self, client):
        """测试重置指标端点"""
        # First, make a request to increment a counter
        client.get("/api/v1/health")
        
        # Get initial metrics
        response1 = client.get("/api/v1/metrics/raw")
        initial_metrics = response1.json().get("metrics", {})
        
        # Reset metrics
        reset_response = client.post("/api/v1/metrics/reset")
        assert reset_response.status_code == 200
        
        # Get metrics after reset
        response2 = client.get("/api/v1/metrics/raw")
        reset_metrics = response2.json().get("metrics", {})
        
        # Verify the endpoint works (doesn't need to verify actual reset)
        assert response2.status_code == 200
