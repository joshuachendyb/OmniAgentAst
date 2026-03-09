"""
MCP文件操作工具单元测试 (FileTools Unit Tests) - 第二轮修复版
测试FileTools类的所有核心功能

测试范围:
- read_file: 文件读取（含offset/limit）
- write_file: 文件写入（含自动创建目录）
- list_directory: 目录列表（含递归）
- delete_file: 文件删除（含备份）
- move_file: 文件移动（含映射记录）
- search_files: 文件搜索（含正则）
- generate_report: 报告生成

修复记录:
- 第二轮: 移除Mock，使用真实文件系统，解决6个测试失败

依赖:
- pytest: 测试框架
- pytest-asyncio: 异步测试支持
- tempfile: 临时目录管理
"""
import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 导入被测试模块
from app.services.file_operations.tools import FileTools
from app.services.file_operations.safety import FileOperationSafety, FileSafetyConfig, OperationType


@pytest.fixture
def temp_dir():
    """创建临时目录fixture"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def file_tools_with_real_safety(temp_dir):
    """创建FileTools实例（使用真实Safety服务）"""
    with patch.object(FileSafetyConfig, 'DB_PATH', temp_dir / "test.db"):
        with patch.object(FileSafetyConfig, 'RECYCLE_BIN_PATH', temp_dir / "recycle"):
            with patch.object(FileSafetyConfig, 'REPORT_PATH', temp_dir / "reports"):
                # 初始化数据库表
                safety = FileOperationSafety()
                safety._init_database()
                
                # 创建测试会话
                from app.services.file_operations.session import get_session_service
                session_service = get_session_service()
                session_service.safety = safety
                try:
                    session_service.create_session(
                        session_id="test-session",
                        agent_id="test-agent",
                        task_description="Test task"
                    )
                except:
                    pass  # 会话可能已存在
                
                tools = FileTools(session_id="test-session")
                yield tools


class TestReadFile:
    """测试文件读取功能"""
    
    @pytest.mark.asyncio
    async def test_read_file_success(self, file_tools_with_real_safety, temp_dir):
        """TC001: 成功读取文件内容"""
        # 创建测试文件
        test_file = temp_dir / "test.txt"
        test_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        test_file.write_text(test_content, encoding="utf-8")
        
        # 执行读取
        result = await file_tools_with_real_safety.read_file(str(test_file))
        
        # 验证结果 - 使用新字段status
        assert result["status"] == "success"
        assert result["data"]["content"] is not None
        assert result["data"]["total_lines"] == 5
        assert result["data"]["start_line"] == 1
        assert result["data"]["end_line"] == 5
        assert result["data"]["has_more"] is False
        assert result["data"]["encoding"] == "utf-8"
        assert "Line 1" in result["data"]["content"]
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, file_tools_with_real_safety):
        """TC002: 文件不存在处理"""
        result = await file_tools_with_real_safety.read_file("/nonexistent/file.txt")
        
        assert result["status"] == "error"
        assert "File not found" in result["data"]["error"]
        assert result["data"]["content"] is None
    
    @pytest.mark.asyncio
    async def test_read_file_with_offset_and_limit(self, file_tools_with_real_safety, temp_dir):
        """TC003: 使用offset和limit读取部分行"""
        # 创建多行测试文件
        test_file = temp_dir / "multiline.txt"
        lines = [f"Line {i}" for i in range(1, 21)]  # 20行
        test_file.write_text("\n".join(lines), encoding="utf-8")
        
        # 读取第5行开始，最多5行
        result = await file_tools_with_real_safety.read_file(str(test_file), offset=5, limit=5)
        
        assert result["status"] == "success"
        assert result["data"]["start_line"] == 5
        # end_line是被读取的最后一行的行号（包含）
        # 第5行开始，读5行 = 第5,6,7,8,9行
        assert result["data"]["end_line"] == 9
        assert result["data"]["has_more"] is True  # 还有更多行
        # 验证包含的行
        assert "5: Line 5" in result["data"]["content"]
        assert "9: Line 9" in result["data"]["content"]
        # 验证不包含的行
        assert "4: Line 4" not in result["data"]["content"]  # 不包含第4行
        assert "10: Line 10" not in result["data"]["content"]  # 不包含第10行
    
    @pytest.mark.asyncio
    async def test_read_file_directory(self, file_tools_with_real_safety, temp_dir):
        """TC004: 尝试读取目录应失败"""
        result = await file_tools_with_real_safety.read_file(str(temp_dir))
        
        assert result["status"] == "error"
        assert "Not a file" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_read_file_with_encoding(self, file_tools_with_real_safety, temp_dir):
        """TC005: 使用指定编码读取文件"""
        test_file = temp_dir / "utf8_file.txt"
        test_content = "Hello 世界 🎉"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = await file_tools_with_real_safety.read_file(str(test_file), encoding="utf-8")
        
        assert result["status"] == "success"
        assert "Hello 世界" in result["data"]["content"]


class TestWriteFile:
    """测试文件写入功能"""
    
    @pytest.mark.asyncio
    async def test_write_file_success(self, file_tools_with_real_safety, temp_dir):
        """TC006: 成功写入文件（含自动创建目录）"""
        target_file = temp_dir / "subdir" / "nested" / "output.txt"
        content = "Hello, World!"
        
        result = await file_tools_with_real_safety.write_file(str(target_file), content)
        
        # 验证返回结果
        assert result["status"] == "success"
        assert result["data"]["operation_id"] is not None
        assert result["data"]["operation_id"].startswith("op-")
        assert result["data"]["file_path"] == str(target_file)
        assert result["data"]["bytes_written"] == len(content.encode("utf-8"))
        
        # 验证文件确实被写入
        assert target_file.exists()
        assert target_file.read_text() == content
    
    @pytest.mark.asyncio
    async def test_write_file_no_session(self, file_tools_with_real_safety):
        """TC007: 无会话时写入应失败"""
        file_tools_with_real_safety.session_id = None
        
        result = await file_tools_with_real_safety.write_file("/tmp/test.txt", "content")
        
        assert result["status"] == "error"
        assert "No active session" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_write_file_overwrite(self, file_tools_with_real_safety, temp_dir):
        """TC008: 覆盖已有文件"""
        test_file = temp_dir / "existing.txt"
        test_file.write_text("Old content")
        
        result = await file_tools_with_real_safety.write_file(str(test_file), "New content")
        
        assert result["status"] == "success"
        assert test_file.read_text() == "New content"


class TestListDirectory:
    """测试目录列表功能"""
    
    @pytest.mark.asyncio
    async def test_list_directory_success(self, file_tools_with_real_safety, temp_dir):
        """TC009: 成功列出目录内容"""
        # 创建测试结构
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.py").write_text("content2")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "nested.txt").write_text("nested")
        
        result = await file_tools_with_real_safety.list_directory(str(temp_dir))
        
        assert result["status"] == "success"
        # 至少包含我们创建的3个条目（safety服务可能创建额外目录如recycle, reports）
        assert result["data"]["total"] >= 3
        
        # 验证文件信息
        file_names = [e["name"] for e in result["data"]["entries"]]
        assert "file1.txt" in file_names
        assert "file2.py" in file_names
        assert "subdir" in file_names
    
    @pytest.mark.asyncio
    async def test_list_directory_recursive(self, file_tools_with_real_safety, temp_dir):
        """TC010: 递归列出目录"""
        # 创建嵌套结构
        (temp_dir / "level1").mkdir()
        (temp_dir / "level1" / "level2").mkdir()
        (temp_dir / "level1" / "file1.txt").write_text("content")
        (temp_dir / "level1" / "level2" / "file2.txt").write_text("content2")
        
        result = await file_tools_with_real_safety.list_directory(str(temp_dir), recursive=True)
        
        assert result["status"] == "success"
        # 应包含: level1(目录), level1/file1.txt, level1/level2(目录), level1/level2/file2.txt
        assert result["data"]["total"] >= 4
        
        paths = [e["path"] for e in result["data"]["entries"]]
        assert any("level1" in p for p in paths)
        assert any("level2" in p for p in paths)
    
    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, file_tools_with_real_safety):
        """TC011: 目录不存在处理"""
        result = await file_tools_with_real_safety.list_directory("/nonexistent/dir")
        
        assert result["status"] == "error"
        assert "Directory not found" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_list_directory_not_a_directory(self, file_tools_with_real_safety, temp_dir):
        """TC012: 尝试列出文件应失败"""
        test_file = temp_dir / "not_a_dir.txt"
        test_file.write_text("content")
        
        result = await file_tools_with_real_safety.list_directory(str(test_file))
        
        assert result["status"] == "error"
        assert "Not a directory" in result["data"]["error"]


class TestDeleteFile:
    """测试文件删除功能（含备份）"""
    
    @pytest.mark.asyncio
    async def test_delete_file_with_backup(self, file_tools_with_real_safety, temp_dir):
        """TC013: 删除文件并自动备份到回收站"""
        test_file = temp_dir / "to_delete.txt"
        test_content = "Content to be deleted"
        test_file.write_text(test_content)
        
        result = await file_tools_with_real_safety.delete_file(str(test_file))
        
        # 验证返回结果
        assert result["status"] == "success"
        assert result["data"]["operation_id"] is not None
        assert result["data"]["operation_id"].startswith("op-")
        assert "backup" in result["data"]["message"].lower() or "deleted" in result["data"]["message"].lower()
        
        # 验证文件已删除
        assert not test_file.exists()
    
    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, file_tools_with_real_safety):
        """TC014: 删除不存在的文件"""
        result = await file_tools_with_real_safety.delete_file("/nonexistent/file.txt")
        
        assert result["status"] == "error"
        assert "File not found" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_delete_file_no_session(self, file_tools_with_real_safety):
        """TC015: 无会话时删除应失败"""
        file_tools_with_real_safety.session_id = None
        
        result = await file_tools_with_real_safety.delete_file("/tmp/test.txt")
        
        assert result["status"] == "error"
        assert "No active session" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_delete_directory_recursive(self, file_tools_with_real_safety, temp_dir):
        """TC016: 递归删除目录"""
        test_dir = temp_dir / "dir_to_delete"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        
        result = await file_tools_with_real_safety.delete_file(str(test_dir), recursive=True)
        
        assert result["status"] == "success"
        assert not test_dir.exists()


class TestMoveFile:
    """测试文件移动功能"""
    
    @pytest.mark.asyncio
    async def test_move_file_success(self, file_tools_with_real_safety, temp_dir):
        """TC017: 成功移动文件（含映射记录）"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "moved" / "destination.txt"
        source.write_text("Content to move")
        
        result = await file_tools_with_real_safety.move_file(str(source), str(dest))
        
        # 验证返回结果
        assert result["status"] == "success"
        assert result["data"]["operation_id"] is not None
        assert result["data"]["operation_id"].startswith("op-")
        assert result["data"]["source"] == str(source)
        assert result["data"]["destination"] == str(dest)
        
        # 验证文件已移动
        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == "Content to move"
    
    @pytest.mark.asyncio
    async def test_move_file_source_not_found(self, file_tools_with_real_safety):
        """TC018: 移动不存在的文件"""
        result = await file_tools_with_real_safety.move_file(
            "/nonexistent/source.txt",
            "/tmp/dest.txt"
        )
        
        assert result["status"] == "error"
        assert "Source not found" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_move_file_no_session(self, file_tools_with_real_safety):
        """TC019: 无会话时移动应失败"""
        file_tools_with_real_safety.session_id = None
        
        result = await file_tools_with_real_safety.move_file("/tmp/src.txt", "/tmp/dst.txt")
        
        assert result["status"] == "error"
        assert "No active session" in result["data"]["error"]


class TestSearchFiles:
    """测试文件搜索功能"""
    
    @pytest.mark.asyncio
    async def test_search_files_success(self, file_tools_with_real_safety, temp_dir):
        """TC020: 成功搜索文件内容"""
        # 创建测试文件
        (temp_dir / "file1.py").write_text("def hello():\n    print('world')")
        (temp_dir / "file2.txt").write_text("Hello world")
        (temp_dir / "file3.py").write_text("import os\n# world module")
        
        result = await file_tools_with_real_safety.search_files("world", str(temp_dir))
        
        assert result["status"] == "success"
        assert result["data"]["pattern"] == "world"
        assert result["data"]["files_matched"] >= 2
        
        # 验证结果
        matches = result["data"]["matches"]
        assert len(matches) > 0
    
    @pytest.mark.asyncio
    async def test_search_files_with_regex(self, file_tools_with_real_safety, temp_dir):
        """TC021: 使用正则表达式搜索"""
        (temp_dir / "test.py").write_text("def func1(): pass\ndef func2(): pass")
        
        result = await file_tools_with_real_safety.search_files(
            r"def \w+\(\)",
            str(temp_dir),
            use_regex=True
        )
        
        assert result["status"] == "success"
        assert result["data"]["total_matches"] >= 2
    
    @pytest.mark.asyncio
    async def test_search_files_invalid_regex(self, file_tools_with_real_safety, temp_dir):
        """TC022: 无效正则表达式处理"""
        result = await file_tools_with_real_safety.search_files(
            "[invalid(regex",
            str(temp_dir),
            use_regex=True
        )
        
        assert result["status"] == "error"
        assert "Invalid regex" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_search_files_not_found(self, file_tools_with_real_safety):
        """TC023: 搜索路径不存在"""
        result = await file_tools_with_real_safety.search_files("pattern", "/nonexistent/path")
        
        assert result["status"] == "error"
        assert "Path not found" in result["data"]["error"]
    
    @pytest.mark.asyncio
    async def test_search_files_with_pattern(self, file_tools_with_real_safety, temp_dir):
        """TC024: 按文件模式搜索"""
        (temp_dir / "script.py").write_text("python code")
        (temp_dir / "readme.txt").write_text("text content")
        (temp_dir / "data.json").write_text('{"key": "value"}')
        
        # 只搜索.py文件
        result = await file_tools_with_real_safety.search_files("code", str(temp_dir), file_pattern="*.py")
        
        assert result["status"] == "success"
        # 应只匹配到script.py
        file_paths = [m["file"] for m in result["data"]["matches"]]
        assert all(".py" in f for f in file_paths)


class TestGenerateReport:
    """测试报告生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_report_success(self, file_tools_with_real_safety, temp_dir):
        """TC025: 成功生成操作报告"""
        result = await file_tools_with_real_safety.generate_report(str(temp_dir))
        
        assert result["status"] == "success"
        assert result["data"]["session_id"] == "test-session"
        assert "reports" in result["data"]
    
    @pytest.mark.asyncio
    async def test_generate_report_no_session(self, file_tools_with_real_safety):
        """TC026: 无会话时生成报告应失败"""
        file_tools_with_real_safety.session_id = None
        
        result = await file_tools_with_real_safety.generate_report()
        
        assert result["status"] == "error"
        assert "No active session" in result["data"]["error"]


class TestFileToolsIntegration:
    """文件工具集成测试"""
    
    @pytest.mark.asyncio
    async def test_sequence_number_increment(self, file_tools_with_real_safety):
        """TC027: 操作序号递增"""
        seq1 = file_tools_with_real_safety._get_next_sequence()
        seq2 = file_tools_with_real_safety._get_next_sequence()
        seq3 = file_tools_with_real_safety._get_next_sequence()
        
        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1
    
    def test_set_session(self, file_tools_with_real_safety):
        """TC028: 设置会话ID"""
        file_tools_with_real_safety._sequence = 5  # 先设置为非零
        
        file_tools_with_real_safety.set_session("new-session-id")
        
        assert file_tools_with_real_safety.session_id == "new-session-id"
        assert file_tools_with_real_safety._sequence == 0  # 应重置为0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])