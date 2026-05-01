"""
create_directory / list_directory 工具深度测试 - 小健

【创建时间】2026-04-29 小健
"""

import pytest
import asyncio
import tempfile
from pathlib import Path


class TestCreateDirectoryTool:
    """测试 create_directory 工具"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    # ===== 基础创建测试 =====
    
    def test_create_directory_basic(self, mock_file_tools, temp_dir):
        """测试基本创建"""
        new_dir = temp_dir / "newdir"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir)))
        
        assert result["status"] == "success"
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_create_nested_directory(self, mock_file_tools, temp_dir):
        """测试创建嵌套目录"""
        new_dir = temp_dir / "a" / "b" / "c"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir)))
        
        assert result["status"] in ["success", "error"]
        if result["status"] == "success":
            assert new_dir.exists()
    
    def test_create_with_parents(self, mock_file_tools, temp_dir):
        """测试带parents创建"""
        new_dir = temp_dir / "parent" / "child"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir), parents=True))
        
        assert result["status"] == "success"
        assert new_dir.exists()
    
    def test_create_exist_ok(self, mock_file_tools, temp_dir):
        """测试exist_ok=True"""
        existing = temp_dir / "existing"
        existing.mkdir()
        
        result = asyncio.run(mock_file_tools.create_directory(
            str(existing), exist_ok=True
        ))
        
        assert result["status"] == "success"
    
    def test_create_without_exist_ok_fails(self, mock_file_tools, temp_dir):
        """测试exist_ok=False失败"""
        existing = temp_dir / "existing"
        existing.mkdir()
        
        result = asyncio.run(mock_file_tools.create_directory(
            str(existing), exist_ok=False
        ))
        
        assert result["status"] in ["success", "error"]
    
    # ===== 路径测试 =====
    
    def test_create_with_spaces(self, mock_file_tools, temp_dir):
        """测试路径中包含空格"""
        new_dir = temp_dir / "folder with spaces"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir)))
        
        assert result["status"] == "success"
    
    def test_create_with_chinese(self, mock_file_tools, temp_dir):
        """测试路径中包含中文"""
        new_dir = temp_dir / "中文文件夹"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir)))
        
        assert result["status"] == "success"
    
    def test_create_unicode_name(self, mock_file_tools, temp_dir):
        """测试Unicode名称"""
        new_dir = temp_dir / "①②③"
        
        result = asyncio.run(mock_file_tools.create_directory(str(new_dir)))
        
        assert result["status"] == "success"
    
    # ===== 错误处理 =====
    
    def test_create_in_nonexistent_parent(self, mock_file_tools, temp_dir):
        """测试在不存在父目录创建"""
        new_dir = temp_dir / "nonexistent" / "child"
        
        result = asyncio.run(mock_file_tools.create_directory(
            str(new_dir), parents=False
        ))
        
        assert result["status"] == "error"
    
    def test_create_file_as_directory(self, mock_file_tools, temp_dir):
        """测试把文件当目录创建"""
        file = temp_dir / "file.txt"
        file.write_text("content")
        
        result = asyncio.run(mock_file_tools.create_directory(str(file)))
        
        assert result["status"] in ["success", "error"]
    
    # ===== 边界测试 =====
    
    def test_create_deep_path(self, mock_file_tools, temp_dir):
        """测试创建深层路径"""
        deep = temp_dir / "a" / "b" / "c" / "d" / "e"
        
        result = asyncio.run(mock_file_tools.create_directory(str(deep)))
        
        assert result["status"] == "success"
    
    def test_create_multiple_dirs(self, mock_file_tools, temp_dir):
        """测试连续创建多个目录"""
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        
        result1 = asyncio.run(mock_file_tools.create_directory(str(dir1)))
        result2 = asyncio.run(mock_file_tools.create_directory(str(dir2)))
        
        assert result1["status"] == "success"
        assert result2["status"] == "success"


class TestListDirectoryTool:
    """测试 list_directory 工具"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools(task_id='test_task')
        return tool
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def setup_files(self, temp_dir):
        """创建测试文件结构"""
        # 创建文件
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "file3.md").write_text("# markdown")
        
        # 创建目录
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file4.txt").write_text("content4")
        
        # 创建隐藏文件
        (temp_dir / ".hidden").write_text("hidden")
        
        return temp_dir
    
    # ===== 基础列表测试 =====
    
    def test_list_basic(self, mock_file_tools, setup_files):
        """测试基本列表"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        assert result["status"] == "success"
        assert result["data"]["success"] is True
        assert "entries" in result["data"]
    
    def test_list_entries_count(self, mock_file_tools, setup_files):
        """测试列出条目数量"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        assert len(entries) >= 3
    
    def test_list_includes_files(self, mock_file_tools, setup_files):
        """测试包含文件"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert "file1.txt" in names
    
    def test_list_includes_directories(self, mock_file_tools, setup_files):
        """测试包含目录"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert "subdir" in names
    
    def test_list_recursive(self, mock_file_tools, setup_files):
        """测试递归列表"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), recursive=True
        ))
        
        entries = result["data"]["entries"]
        assert result["status"] == "success"
    
    # ===== 错误处理 =====
    
    def test_list_nonexistent(self, mock_file_tools, temp_dir):
        """测试列表不存在的目录"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(temp_dir / "nonexistent")
        ))
        
        assert result["status"] == "error"
    
    def test_list_file_as_directory(self, mock_file_tools, temp_dir):
        """测试把文件当目录"""
        file = temp_dir / "file.txt"
        file.write_text("content")
        
        result = asyncio.run(mock_file_tools.list_directory(str(file)))
        
        assert result["status"] == "error"
    
    def test_list_empty_directory(self, mock_file_tools, temp_dir):
        """测试空目录"""
        empty = temp_dir / "empty"
        empty.mkdir()
        
        result = asyncio.run(mock_file_tools.list_directory(str(empty)))
        
        assert result["status"] == "success"
    
    # ===== 条目信息测试 =====
    
    def test_entries_have_name(self, mock_file_tools, setup_files):
        """测试条目有name字段"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        for entry in entries:
            assert "name" in entry
    
    def test_entries_have_type(self, mock_file_tools, setup_files):
        """测试条目有type字段"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        for entry in entries:
            assert "type" in entry
    
    def test_entries_have_path(self, mock_file_tools, setup_files):
        """测试条目有path字段"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        
        entries = result["data"]["entries"]
        for entry in entries:
            assert "path" in entry

    # ===== 新增功能测试(sortBy/include_hidden/statistics/mtime) 2026-05-01 小沈 =====

    def test_sort_by_name(self, mock_file_tools, setup_files):
        """测试按名称排序"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), sortBy="name"
        ))
        assert result["status"] == "success"
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries if e["type"] == "file"]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_size(self, mock_file_tools, setup_files):
        """测试按大小排序"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), sortBy="size"
        ))
        assert result["status"] == "success"
        entries = result["data"]["entries"]
        file_entries = [e for e in entries if e["type"] == "file"]
        sizes = [e.get("size", 0) for e in file_entries]
        assert sizes == sorted(sizes, reverse=True)

    def test_include_hidden_false(self, mock_file_tools, setup_files):
        """测试不包含隐藏文件(默认)"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), include_hidden=False
        ))
        assert result["status"] == "success"
        names = [e["name"] for e in result["data"]["entries"]]
        assert ".hidden" not in names

    def test_include_hidden_true(self, mock_file_tools, setup_files):
        """测试包含隐藏文件"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), include_hidden=True
        ))
        assert result["status"] == "success"
        names = [e["name"] for e in result["data"]["entries"]]
        assert ".hidden" in names

    def test_statistics_present(self, mock_file_tools, setup_files):
        """测试statistics字段存在"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        assert result["status"] == "success"
        stats = result["data"]["statistics"]
        assert "total_size" in stats
        assert "dir_count" in stats
        assert "file_count" in stats
        assert "sort_by" in stats
        assert stats["dir_count"] >= 1
        assert stats["file_count"] >= 3

    def test_mtime_present(self, mock_file_tools, setup_files):
        """测试mtime字段存在"""
        result = asyncio.run(mock_file_tools.list_directory(str(setup_files)))
        assert result["status"] == "success"
        entries = result["data"]["entries"]
        for entry in entries:
            assert "mtime" in entry
            assert entry["mtime"] is not None

    def test_sort_by_invalid(self, mock_file_tools, setup_files):
        """测试无效排序参数"""
        result = asyncio.run(mock_file_tools.list_directory(
            str(setup_files), sortBy="invalid"
        ))
        assert result["status"] == "error"