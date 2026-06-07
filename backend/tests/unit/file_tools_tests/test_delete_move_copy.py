"""
file_operation 工具深度测试 (替代原 delete_file/move_file/copy_file) - 小健

【创建时间】2026-04-29 小健
【更新时间】2026-05-21 小健 — 适配 file_operation 新API
"""

import pytest
import asyncio
import tempfile
from pathlib import Path


class TestFileOperationDelete:
    """测试 file_operation delete 动作"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_delete_file(self, mock_file_tools, temp_dir):
        """测试删除文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        result = asyncio.run(mock_file_tools.file_operation(action="delete", source=str(test_file)))
        
        assert result["code"] == "SUCCESS"
        assert not test_file.exists()
    
    def test_delete_nonexistent(self, mock_file_tools, temp_dir):
        """测试删除不存在的文件（幂等，不报错）"""
        result = asyncio.run(mock_file_tools.file_operation(action="delete", source=str(temp_dir / "nonexistent.txt")))
        
        # file_operation 对不存在的文件返回 success（幂等）
        assert result["code"] == "SUCCESS"
    
    def test_delete_directory_recursive(self, mock_file_tools, temp_dir):
        """测试递归删除目录"""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
        
        result = asyncio.run(mock_file_tools.file_operation(action="delete", source=str(test_dir), recursive=True))
        
        assert result["code"] == "SUCCESS"

    def test_delete_empty_directory(self, mock_file_tools, temp_dir):
        """测试删除空目录"""
        test_dir = temp_dir / "empty"
        test_dir.mkdir()

        result = asyncio.run(mock_file_tools.file_operation(action="delete", source=str(test_dir)))

        assert result["code"] == "SUCCESS"


class TestFileOperationMove:
    """测试 file_operation move 动作"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_move_file(self, mock_file_tools, temp_dir):
        """测试移动文件"""
        src = temp_dir / "src.txt"
        dst = temp_dir / "dst.txt"
        src.write_text("content")
        
        result = asyncio.run(mock_file_tools.file_operation(action="move", source=str(src), destination=str(dst)))
        
        assert result["code"] == "SUCCESS"
        assert not src.exists()
        assert dst.exists()

    def test_move_nonexistent(self, mock_file_tools, temp_dir):
        """测试移动不存在的文件"""
        result = asyncio.run(mock_file_tools.file_operation(action="move", source=str(temp_dir / "nonexistent.txt"), destination=str(temp_dir / "dst.txt")))

        assert result["code"] == "ERR_FILE_NOT_FOUND"


class TestFileOperationCopy:
    """测试 file_operation copy 动作"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_copy_file(self, mock_file_tools, temp_dir):
        """测试复制文件"""
        src = temp_dir / "src.txt"
        dst = temp_dir / "dst.txt"
        src.write_text("content")
        
        result = asyncio.run(mock_file_tools.file_operation(action="copy", source=str(src), destination=str(dst)))
        
        assert result["code"] == "SUCCESS"
        assert src.exists()
        assert dst.exists()
    
    def test_copy_nonexistent(self, mock_file_tools, temp_dir):
        """测试复制不存在的文件"""
        result = asyncio.run(mock_file_tools.file_operation(action="copy", source=str(temp_dir / "nonexistent.txt"), destination=str(temp_dir / "dst.txt")))
        
        assert result["code"].startswith("ERR_")
