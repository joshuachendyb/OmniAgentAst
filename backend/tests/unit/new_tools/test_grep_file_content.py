"""
grep_file_content 工具测试 - 小健

【创建时间】2026-04-29 小健
"""

import os
import pytest
import tempfile
from pathlib import Path


class TestGrepFileContentTool:
    """测试 grep_file_content 工具"""
    
    @pytest.fixture
    def mock_file_tools(self):
        from app.services.tools.file.file_tools import FileTools
        tool = FileTools()
        return tool
    
    @pytest.fixture
    def test_dir(self):
        """使用系统临时目录，避免硬编码路径"""
        tmp = Path(tempfile.mkdtemp(prefix="grep_test_"))
        yield tmp
        # cleanup
        import shutil
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    
    @pytest.fixture
    def sample_files(self, test_dir):
        test_dir.mkdir(exist_ok=True)
        files = {
            "test.py": "def hello():\n    print('hello world')\n    return 'hello'",
            "util.py": "def util():\n    return 'utils'",
            "readme.md": "# Test\nThis is a test file",
        }
        for name, content in files.items():
            (test_dir / name).write_text(content)
        return test_dir

    @pytest.mark.asyncio
    async def test_simple_pattern(self, mock_file_tools, sample_files):
        """测试简单模式"""
        result = await mock_file_tools.grep_file_content(
            pattern="hello",
            search_dir=str(sample_files)
        )
        
        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_ignore_case(self, mock_file_tools, sample_files):
        """测试忽略大小写"""
        result = await mock_file_tools.grep_file_content(
            pattern="HELLO",
            search_dir=str(sample_files),
            ignore_case=True
        )

        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_output_count(self, mock_file_tools, sample_files):
        """测试输出计数"""
        result = await mock_file_tools.grep_file_content(
            pattern="def",
            search_dir=str(sample_files),
            output_mode="count"
        )

        assert result["code"] == "SUCCESS"
        assert "matches" in result["data"]
        assert result["data"]["output_mode"] == "count"

    @pytest.mark.asyncio
    async def test_output_files_with_matches(self, mock_file_tools, sample_files):
        """测试输出匹配文件"""
        result = await mock_file_tools.grep_file_content(
            pattern="def",
            search_dir=str(sample_files),
            output_mode="files_with_matches"
        )

        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_filter_by_type(self, mock_file_tools, sample_files):
        """测试按类型过滤"""
        result = await mock_file_tools.grep_file_content(
            pattern="def",
            search_dir=str(sample_files),
            glob="*.py"
        )

        assert result["code"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_show_line_numbers(self, mock_file_tools, sample_files):
        """测试显示行号（默认包含行号）"""
        result = await mock_file_tools.grep_file_content(
            pattern="hello",
            search_dir=str(sample_files)
        )

        assert result["code"] == "SUCCESS"
        # 验证返回的匹配结果包含行号信息
        if result["data"].get("matches"):
            for match in result["data"]["matches"]:
                if match.get("matches"):
                    assert "line" in match["matches"][0]

    @pytest.mark.asyncio
    async def test_no_matches(self, mock_file_tools, sample_files):
        """测试无匹配"""
        result = await mock_file_tools.grep_file_content(
            pattern="nonexistent_pattern_xyz",
            search_dir=str(sample_files)
        )

        assert result["code"] == "SUCCESS"
        assert result["data"]["matches"] == []

    @pytest.mark.asyncio
    async def test_invalid_regex(self, mock_file_tools, sample_files):
        """测试无效正则"""
        result = await mock_file_tools.grep_file_content(
            pattern="[invalid",
            search_dir=str(sample_files)
        )

        assert result["code"] == "ERR_FILE_CONTENT_SEARCH_FAILED"

    @pytest.mark.asyncio
    async def test_empty_pattern(self, mock_file_tools, sample_files):
        """测试空模式"""
        result = await mock_file_tools.grep_file_content(
            pattern="",
            search_dir=str(sample_files)
        )

        assert result["code"] == "ERR_PARAM_INVALID"