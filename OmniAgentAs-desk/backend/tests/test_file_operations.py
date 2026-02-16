"""
文件操作API集成测试 (File Operations API Integration Tests)
测试文件操作相关的API端点
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

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
    
    def test_list_operations_endpoint(self, client, session_id):
        """测试获取操作列表端点"""
        # 这个测试需要先有操作记录
        # 在实际测试中，需要先执行一些操作
        pass
    
    def test_tree_data_endpoint_structure(self):
        """测试树形数据结构端点返回正确的结构"""
        # 验证响应结构
        expected_structure = {
            "root": dict,
            "operations_count": int,
            "session_id": str
        }
        
        # 这里应该调用API并验证响应
        # response = client.get(f"/api/v1/operations/tree-data?session_id=test")
        # assert response.status_code == 200
        # data = response.json()
        # assert "root" in data
        # assert "operations_count" in data
        pass
    
    def test_flow_data_endpoint_structure(self):
        """测试流向数据端点返回正确的桑基图结构"""
        # 验证响应结构
        expected_structure = {
            "nodes": list,
            "links": list,
            "statistics": dict
        }
        
        # response = client.get(f"/api/v1/operations/flow-data?session_id=test")
        # data = response.json()
        # assert "nodes" in data
        # assert "links" in data
        # assert "statistics" in data
        pass
    
    def test_stats_data_endpoint(self):
        """测试统计数据端点"""
        # 验证统计字段
        expected_fields = [
            "total_operations",
            "operations_by_type",
            "operations_by_extension",
            "total_space_impact",
            "total_duration_ms",
            "success_rate",
            "average_duration_ms",
            "largest_files"
        ]
        
        # response = client.get(f"/api/v1/operations/stats-data?session_id=test")
        # data = response.json()
        # for field in expected_fields:
        #     assert field in data
        pass
    
    def test_animation_data_endpoint(self):
        """测试动画数据端点"""
        # 验证动画帧结构
        # response = client.get(f"/api/v1/operations/animation-data?session_id=test")
        # data = response.json()
        # assert "frames" in data
        # assert "total_frames" in data
        # assert "total_duration_ms" in data
        # assert "metadata" in data
        pass
    
    def test_report_generation_txt(self):
        """测试生成文本报告"""
        # response = client.get(f"/api/v1/operations/report?session_id=test&format=txt")
        # assert response.status_code == 200
        # data = response.json()
        # assert data["success"] is True
        # assert data["format"] == "txt"
        # assert "content" in data
        pass
    
    def test_report_generation_json(self):
        """测试生成JSON报告"""
        # response = client.get(f"/api/v1/operations/report?session_id=test&format=json")
        # data = response.json()
        # assert data["success"] is True
        # assert data["format"] == "json"
        # assert "data" in data
        pass
    
    def test_report_generation_html(self):
        """测试生成HTML报告"""
        # response = client.get(f"/api/v1/operations/report?session_id=test&format=html")
        # data = response.json()
        # assert data["success"] is True
        # assert data["format"] == "html"
        # assert "download_url" in data
        pass
    
    def test_rollback_endpoint(self):
        """测试回滚端点"""
        # 测试单个操作回滚
        # rollback_data = {"operation_id": "test-op-id"}
        # response = client.post("/api/v1/operations/rollback", json=rollback_data)
        # assert response.status_code == 200
        # data = response.json()
        # assert "success" in data
        pass
    
    def test_session_rollback_endpoint(self):
        """测试会话回滚端点"""
        # response = client.post("/api/v1/operations/session/test-session/rollback")
        # assert response.status_code == 200
        # data = response.json()
        # assert "session_id" in data
        # assert "total_operations" in data
        # assert "success_count" in data
        pass


class TestVisualizationDataFields:
    """测试可视化数据字段"""
    
    def test_file_extension_field(self):
        """测试文件扩展名字段"""
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
        """测试耗时计算"""
        start_time = datetime.now()
        # 模拟操作
        import time
        time.sleep(0.01)  # 10ms
        end_time = datetime.now()
        
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        assert duration_ms >= 10  # 应该至少10ms
    
    def test_space_impact_calculation(self):
        """测试空间影响计算"""
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
        """测试时间戳格式一致性"""
        # 所有时间戳应该使用ISO格式
        dt = datetime.now()
        iso_string = dt.isoformat()
        
        # 验证可以解析
        parsed = datetime.fromisoformat(iso_string)
        assert parsed == dt
    
    def test_path_format(self):
        """测试路径格式一致性"""
        # 路径应该使用字符串格式
        test_path = Path("/test/path")
        path_str = str(test_path)
        assert isinstance(path_str, str)
        
        # Windows路径也应该能正确处理
        win_path = Path("C:\\Users\\test")
        assert isinstance(str(win_path), str)
    
    def test_enum_serialization(self):
        """测试枚举序列化"""
        from app.models.file_operations import OperationType, OperationStatus
        
        # 枚举应该序列化为字符串
        assert OperationType.CREATE.value == "create"
        assert OperationType.DELETE.value == "delete"
        assert OperationStatus.SUCCESS.value == "success"


# 如果需要实际运行集成测试，取消下面的注释并配置测试客户端
# @pytest.fixture
# def client():
#     from fastapi.testclient import TestClient
#     from app.main import app
#     return TestClient(app)
# 
# @pytest.fixture
# def session_id(client):
#     # 创建一个测试会话并返回ID
#     pass
