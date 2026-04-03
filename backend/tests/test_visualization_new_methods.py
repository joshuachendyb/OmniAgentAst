"""
新增可视化方法测试 - 小健
========================

测试新增的3个方法：
1. generate_json_report
2. generate_html_report
3. generate_mermaid_report

审查人：小健
审查时间：2026-03-21
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


# ============================================================================
# 测试 generate_json_report 方法
# ============================================================================

class TestGenerateJsonReport:
    """测试 generate_json_report 方法"""

    def test_json_report_returns_string(self):
        """JSON报告返回字符串"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # Mock session service
        mock_session = MagicMock()
        mock_session.agent_id = "agent-001"
        mock_session.task_description = "测试任务"
        mock_session.created_at = "2026-03-21 10:00:00"
        
        with patch('app.utils.visualization.file_visualization.get_session_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_session.return_value = mock_session
            mock_get_service.return_value = mock_service
            
            # Mock database connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
                ("write", "D:/test.txt", None, "success", 2048, 0, "2026-03-21 10:02:00", None),
            ]
            mock_conn.cursor.return_value = mock_cursor
            
            with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                # 【小沈修改 2026-03-25】添加 task_description 参数
                result = visualizer.generate_json_report("sess-001", "测试任务")
                
                # 验证返回的是JSON字符串
                assert isinstance(result, str)
                
                # 验证可以解析为JSON
                data = json.loads(result)
                assert "session_id" in data
                assert "operations" in data
                assert data["session_id"] == "sess-001"
                assert len(data["operations"]) == 2

    def test_json_report_contains_required_fields(self):
        """JSON报告包含所有必需字段"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_session = MagicMock()
        mock_session.agent_id = "agent-001"
        mock_session.task_description = "测试任务"
        mock_session.created_at = "2026-03-21 10:00:00"
        
        with patch('app.utils.visualization.file_visualization.get_session_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_session.return_value = mock_session
            mock_get_service.return_value = mock_service
            
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
            ]
            mock_conn.cursor.return_value = mock_cursor
            
            with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                # 【小沈修改 2026-03-25】添加 task_description 参数
                result = visualizer.generate_json_report("sess-001", "测试任务")
                data = json.loads(result)
                
                # 验证顶层字段
                assert "session_id" in data
                assert "agent_id" in data
                assert "task_description" in data
                assert "created_at" in data
                assert "operations" in data
                
                # 验证操作记录字段
                op = data["operations"][0]
                assert "type" in op
                assert "source" in op
                assert "destination" in op
                assert "status" in op
                assert "file_size" in op
                assert "is_directory" in op
                assert "created_at" in op
                assert "error_message" in op

    def test_json_report_handles_empty_operations(self):
        """JSON报告处理空操作记录"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_session = MagicMock()
        mock_session.agent_id = "agent-001"
        mock_session.task_description = "测试任务"
        mock_session.created_at = "2026-03-21 10:00:00"
        
        with patch('app.utils.visualization.file_visualization.get_session_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_session.return_value = mock_session
            mock_get_service.return_value = mock_service
            
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []  # 空操作记录
            mock_conn.cursor.return_value = mock_cursor
            
            with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                # 【小沈修改 2026-03-25】添加 task_description 参数，空操作返回空字符串
                result = visualizer.generate_json_report("sess-001", "测试任务")
                assert result == ""

    def test_json_report_handles_session_not_found(self):
        """JSON报告处理session不存在的情况"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】不再依赖 session，空操作返回空字符串
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_json_report("nonexistent-session", "测试任务")
            
            # 空操作返回空字符串
            assert result == ""

    def test_json_report_saves_to_file(self):
        """JSON报告可以保存到文件"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_session = MagicMock()
        mock_session.agent_id = "agent-001"
        mock_session.task_description = "测试任务"
        mock_session.created_at = "2026-03-21 10:00:00"
        
        with patch('app.utils.visualization.file_visualization.get_session_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_session.return_value = mock_session
            mock_get_service.return_value = mock_service
            
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
            ]
            mock_conn.cursor.return_value = mock_cursor
            
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_report.json"
                
                with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                    # 【小沈修改 2026-03-25】添加 task_description 参数
                    result = visualizer.generate_json_report("sess-001", "测试任务", output_path)
                    
                    # 验证返回的是文件路径
                    assert result == str(output_path)
                    
                    # 验证文件存在
                    assert output_path.exists()
                    
                    # 验证文件内容
                    with open(output_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        assert data["session_id"] == "sess-001"


# ============================================================================
# 测试 generate_html_report 方法
# ============================================================================

class TestGenerateHtmlReport:
    """测试 generate_html_report 方法"""

    def test_html_report_returns_string(self):
        """HTML报告返回字符串"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】去掉 session mock，直接 mock 数据库
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            # 【小沈修改 2026-03-25】添加 task_description 参数
            result = visualizer.generate_html_report("sess-001", "测试任务")
            
            assert isinstance(result, str)
            assert "<!DOCTYPE html>" in result
            assert "<html" in result

    def test_html_report_contains_session_info(self):
        """HTML报告包含会话信息"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】去掉 session mock，直接 mock 数据库
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            # 【小沈修改 2026-03-25】添加 task_description 参数
            result = visualizer.generate_html_report("sess-001", "测试任务")
            
            assert "sess-001" in result
            assert "file-operation-agent" in result
            assert "测试任务" in result

    def test_html_report_contains_statistics(self):
        """HTML报告包含统计数据"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】去掉 session mock，直接 mock 数据库
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
            ("write", "D:/test.txt", None, "success", 2048, 0, "2026-03-21 10:02:00", None),
            ("delete", "D:/test.txt", None, "failed", 0, 0, "2026-03-21 10:03:00", "权限不足"),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            # 【小沈修改 2026-03-25】添加 task_description 参数
            result = visualizer.generate_html_report("sess-001", "测试任务")
            
            # 验证包含操作类型统计
            assert "read" in result or "操作类型统计" in result
            assert "成功" in result
            assert "失败" in result

    def test_html_report_handles_session_not_found(self):
        """HTML报告处理session不存在的情况"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】不再依赖 session，空操作返回空字符串
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_html_report("nonexistent-session", "测试任务")
            
            # 空操作返回空字符串
            assert result == ""

    def test_html_report_saves_to_file(self):
        """HTML报告可以保存到文件"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        # 【小沈修改 2026-03-25】去掉 session mock，直接 mock 数据库
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1024, 0, "2026-03-21 10:01:00", None),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.html"
            
            with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                # 【小沈修改 2026-03-25】添加 task_description 参数
                result = visualizer.generate_html_report("sess-001", "测试任务", output_path)
                
                assert result == str(output_path)
                assert output_path.exists()
                
                with open(output_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert "<!DOCTYPE html>" in content


# ============================================================================
# 测试 generate_mermaid_report 方法
# ============================================================================

class TestGenerateMermaidReport:
    """测试 generate_mermaid_report 方法"""

    def test_mermaid_report_returns_string(self):
        """Mermaid报告返回字符串"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1),
            ("write", "D:/output.txt", None, "success", 2),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            assert isinstance(result, str)
            assert "graph TD" in result

    def test_mermaid_report_contains_operations(self):
        """Mermaid报告包含操作节点"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1),
            ("write", "D:/output.txt", None, "success", 2),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            # 验证包含操作节点
            assert "Op0" in result
            assert "Op1" in result
            assert "Start" in result
            assert "End" in result
            
            # 验证包含操作类型
            assert "read" in result
            assert "write" in result

    def test_mermaid_report_handles_move_operation(self):
        """Mermaid报告处理move操作（有源和目标）"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("move", "D:/source.txt", "D:/dest.txt", "success", 1),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            # 验证包含源和目标文件名
            assert "source.txt" in result
            assert "dest.txt" in result or "→" in result

    def test_mermaid_report_handles_failed_status(self):
        """Mermaid报告处理失败状态"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "failed", 1),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            # 验证包含失败样式
            assert ":::failed" in result

    def test_mermaid_report_handles_blocked_status(self):
        """Mermaid报告处理被阻止状态"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "blocked", 1),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            # 验证包含被阻止样式
            assert ":::blocked" in result

    def test_mermaid_report_handles_empty_operations(self):
        """Mermaid报告处理空操作记录"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(visualizer, '_get_connection', return_value=mock_conn):
            result = visualizer.generate_mermaid_report("sess-001")
            
            # 空操作时仍然有开始和结束节点
            assert "graph TD" in result
            assert "Start" in result

    def test_mermaid_report_saves_to_file(self):
        """Mermaid报告可以保存到文件"""
        from app.utils.visualization.file_visualization import FileOperationVisualizer
        
        visualizer = FileOperationVisualizer()
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("read", "D:/test.txt", None, "success", 1),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.mmd"
            
            with patch.object(visualizer, '_get_connection', return_value=mock_conn):
                result = visualizer.generate_mermaid_report("sess-001", output_path)
                
                assert result == str(output_path)
                assert output_path.exists()
                
                with open(output_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert "graph TD" in content
