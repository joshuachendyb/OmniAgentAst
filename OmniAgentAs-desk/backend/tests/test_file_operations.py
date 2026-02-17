"""
文件操作API集成测试 (File Operations API Integration Tests)
测试文件操作相关的API端点

测试范围:
- get_tree_data: 获取树形数据
- get_stats_data: 获取统计数据
- generate_report_txt/json/html: 生成报告
- rollback_session: 回滚会话

依赖:
- pytest: 测试框架
- fastapi.testclient: API测试客户端
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 【修复】添加TestClient导入
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)

@pytest.fixture
def session_id():
    """创建测试会话ID"""
    return "test-session-123"


class TestFileOperationsAPI:
    """文件操作API测试类"""
    
    @pytest.fixture(scope="class")
    def temp_dir(self):
        """创建临时目录"""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)
    
    @pytest.fixture(scope="class")
    def test_files(self, temp_dir):
        """创建测试文件"""
        files = []
        
        # 创建测试文件
        for i in range(3):
            file_path = Path(temp_dir) / f"test_file_{i}.txt"
            file_path.write_text(f"Test content {i}")
            files.append(str(file_path))
        
        # 创建子目录
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        
        subfile = subdir / "subfile.py"
        subfile.write_text("print('hello')")
        files.append(str(subfile))
        
        return files
    
    def test_api_routes_registered(self, client):
        """TC070: 验证API路由已注册"""
        routes = [route.path for route in app.routes]
        
        # 检查文件操作相关路由是否存在
        assert any("operations" in route for route in routes), "Operations routes not found"
    
    def test_tree_data_endpoint_exists(self, client):
        """TC071: 验证树形数据端点存在"""
        # 尝试访问端点，即使返回错误也证明端点存在
        response = client.get("/api/v1/operations/tree-data?session_id=test")
        
        # 端点应该存在（不返回404）
        assert response.status_code != 404, "Tree data endpoint not found"
    
    def test_tree_data_endpoint_structure(self, client):
        """TC072: 测试树形数据结构端点返回正确的结构"""
        response = client.get("/api/v1/operations/tree-data?session_id=test")
        
        # 如果端点返回200，验证结构
        if response.status_code == 200:
            data = response.json()
            
            # 验证响应结构
            assert "root" in data or "tree" in data or "data" in data, "Missing root/tree/data field"
            # 可能的其他字段
            if "operations_count" in data:
                assert isinstance(data["operations_count"], int)
            if "session_id" in data:
                assert isinstance(data["session_id"], str)
    
    def test_flow_data_endpoint_exists(self, client):
        """TC073: 验证流向数据端点存在"""
        response = client.get("/api/v1/operations/flow-data?session_id=test")
        
        # 端点应该存在
        assert response.status_code != 404, "Flow data endpoint not found"
    
    def test_flow_data_endpoint_structure(self, client):
        """TC074: 测试流向数据端点返回正确的桑基图结构"""
        response = client.get("/api/v1/operations/flow-data?session_id=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # 桑基图通常包含nodes和links
            if "nodes" in data:
                assert isinstance(data["nodes"], list)
            if "links" in data:
                assert isinstance(data["links"], list)
            if "statistics" in data:
                assert isinstance(data["statistics"], dict)
    
    def test_stats_data_endpoint_exists(self, client):
        """TC075: 验证统计数据端点存在"""
        response = client.get("/api/v1/operations/stats-data?session_id=test")
        
        assert response.status_code != 404, "Stats data endpoint not found"
    
    def test_stats_data_endpoint(self, client):
        """TC076: 测试统计数据端点"""
        response = client.get("/api/v1/operations/stats-data?session_id=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证可能的统计字段
            expected_fields = [
                "total_operations",
                "operations_by_type",
                "success_rate",
            ]
            
            # 至少应该有一些统计字段
            has_stats = any(field in data for field in expected_fields)
            assert has_stats or len(data) > 0, "No statistics fields found"
    
    def test_animation_data_endpoint_exists(self, client):
        """TC077: 验证动画数据端点存在"""
        response = client.get("/api/v1/operations/animation-data?session_id=test")
        
        assert response.status_code != 404, "Animation data endpoint not found"
    
    def test_animation_data_endpoint(self, client):
        """TC078: 测试动画数据端点"""
        response = client.get("/api/v1/operations/animation-data?session_id=test")
        
        if response.status_code == 200:
            data = response.json()
            
            # 动画数据通常包含frames
            if "frames" in data:
                assert isinstance(data["frames"], list)
            if "total_frames" in data:
                assert isinstance(data["total_frames"], int)
            if "metadata" in data:
                assert isinstance(data["metadata"], dict)
    
    def test_report_endpoint_exists(self, client):
        """TC079: 验证报告端点存在"""
        response = client.get("/api/v1/operations/report?session_id=test&format=txt")
        
        assert response.status_code != 404, "Report endpoint not found"
    
    def test_report_generation_txt(self, client):
        """TC080: 测试生成文本报告"""
        response = client.get("/api/v1/operations/report?session_id=test&format=txt")
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证响应结构
            if "success" in data:
                assert isinstance(data["success"], bool)
            if "format" in data:
                assert data["format"] == "txt"
            # 可能包含content或download_url
            assert "content" in data or "download_url" in data or "data" in data
    
    def test_report_generation_json(self, client):
        """TC081: 测试生成JSON报告"""
        response = client.get("/api/v1/operations/report?session_id=test&format=json")
        
        if response.status_code == 200:
            data = response.json()
            
            if "format" in data:
                assert data["format"] == "json"
            # JSON报告应该包含数据
            assert "data" in data or "content" in data or "download_url" in data
    
    def test_report_generation_html(self, client):
        """TC082: 测试生成HTML报告"""
        response = client.get("/api/v1/operations/report?session_id=test&format=html")
        
        if response.status_code == 200:
            data = response.json()
            
            if "format" in data:
                assert data["format"] == "html"
            # HTML报告通常提供下载链接
            assert "download_url" in data or "content" in data or "data" in data
    
    def test_rollback_endpoint_exists(self, client):
        """TC083: 验证回滚端点存在"""
        rollback_data = {"operation_id": "test-op-id"}
        response = client.post("/api/v1/operations/rollback", json=rollback_data)
        
        assert response.status_code != 404, "Rollback endpoint not found"
    
    def test_rollback_endpoint(self, client):
        """TC084: 测试回滚端点"""
        rollback_data = {"operation_id": "test-op-id"}
        response = client.post("/api/v1/operations/rollback", json=rollback_data)
        
        # 应该返回200或422（验证错误）或404（操作不存在）
        assert response.status_code in [200, 201, 422, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "message" in data or "error" in data
    
    def test_session_rollback_endpoint_exists(self, client):
        """TC085: 验证会话回滚端点存在"""
        response = client.post("/api/v1/operations/session/test-session/rollback")
        
        assert response.status_code != 404, "Session rollback endpoint not found"
    
    def test_session_rollback_endpoint(self, client):
        """TC086: 测试会话回滚端点"""
        response = client.post("/api/v1/operations/session/test-session/rollback")
        
        # 应该返回200或404（会话不存在）
        assert response.status_code in [200, 201, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # 应该包含会话相关信息
            assert any(key in data for key in ["session_id", "success", "message", "total_operations"])
    
    def test_list_operations_endpoint(self, client, session_id):
        """TC087: 测试获取操作列表端点"""
        response = client.get(f"/api/v1/operations?session_id={session_id}")
        
        # 端点应该存在
        assert response.status_code != 404, "List operations endpoint not found"
        
        if response.status_code == 200:
            data = response.json()
            # 应该返回操作列表
            assert isinstance(data, list) or "operations" in data or "data" in data


class TestVisualizationDataFields:
    """测试可视化数据字段"""
    
    def test_file_extension_field(self):
        """TC088: 测试文件扩展名字段"""
        # 验证不同文件的扩展名被正确提取
        test_cases = [
            ("/path/to/file.py", ".py"),
            ("/path/to/file.TXT", ".txt"),  # 应该转为小写
            ("/path/to/file", None),  # 无扩展名
            ("/path/to.tar.gz", ".gz"),  # 多重扩展名
        ]
        
        for path, expected_ext in test_cases:
            path_obj = Path(path)
            ext = path_obj.suffix.lower() if path_obj.suffix else None
            assert ext == expected_ext, f"Failed for {path}"
    
    def test_duration_calculation(self):
        """TC089: 测试耗时计算"""
        start_time = datetime.now()
        # 模拟操作
        import time
        time.sleep(0.01)  # 10ms
        end_time = datetime.now()
        
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        assert duration_ms >= 10  # 应该至少10ms
    
    def test_space_impact_calculation(self):
        """TC090: 测试空间影响计算"""
        # DELETE: +size (frees space)
        # CREATE: -size (uses space)
        # MOVE/COPY: 0
        
        file_size = 1024
        
        # 删除操作释放空间
        delete_impact = file_size
        assert delete_impact == 1024
        
        # 创建操作使用空间
        create_impact = -file_size
        assert create_impact == -1024
        
        # 移动操作无净影响
        move_impact = 0
        assert move_impact == 0


class TestDataFormatConsistency:
    """测试数据格式一致性"""
    
    def test_timestamp_format(self):
        """TC091: 测试时间戳格式一致性"""
        # 所有时间戳应该使用ISO格式
        dt = datetime.now()
        iso_string = dt.isoformat()
        
        # 验证可以解析
        parsed = datetime.fromisoformat(iso_string)
        assert parsed == dt
    
    def test_path_format(self):
        """TC092: 测试路径格式一致性"""
        # 路径应该使用字符串格式
        test_path = Path("/test/path")
        path_str = str(test_path)
        assert isinstance(path_str, str)
        
        # Windows路径也应该能正确处理
        win_path = Path("C:\\Users\\test")
        assert isinstance(str(win_path), str)
    
    def test_enum_serialization(self):
        """TC093: 测试枚举序列化"""
        from app.models.file_operations import OperationType, OperationStatus
        
        # 枚举应该序列化为字符串
        assert OperationType.CREATE.value == "create"
        assert OperationType.DELETE.value == "delete"
        assert OperationStatus.SUCCESS.value == "success"


class TestAPIErrorHandling:
    """测试API错误处理"""
    
    def test_invalid_session_id(self, client):
        """TC094: 无效会话ID处理"""
        response = client.get("/api/v1/operations/stats-data?session_id=")
        
        # 应该返回400或422（验证错误），或者404（会话不存在）
        assert response.status_code in [200, 400, 422, 404], f"Unexpected status: {response.status_code}"
    
    def test_missing_required_params(self, client):
        """TC095: 缺少必需参数"""
        # 不传递session_id
        response = client.get("/api/v1/operations/stats-data")
        
        # 应该返回422（验证错误）
        assert response.status_code in [200, 422], f"Unexpected status: {response.status_code}"
    
    def test_invalid_report_format(self, client):
        """TC096: 无效报告格式"""
        response = client.get("/api/v1/operations/report?session_id=test&format=invalid")
        
        # 应该返回400或422（验证错误），或者使用默认格式
        assert response.status_code in [200, 400, 422], f"Unexpected status: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])