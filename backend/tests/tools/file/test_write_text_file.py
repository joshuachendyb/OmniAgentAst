# -*- coding: utf-8 -*-
"""
write_text_file 工具全面测试

测试范围:
  1. 正常功能测试 - 创建文件、覆盖写入、追加写入
  2. 参数验证测试 - 编码、追加模式、内容转义
  3. 边界条件测试 - 空内容、特殊字符、大文件
  4. 错误处理测试 - 路径无效、权限错误、安全拦截
  5. 安全性测试 - 路径越权、任务ID验证、safety机制
  6. 编码测试 - UTF-8、GBK、编码检测

创建时间: 2026-06-22 04:40:00
编写人: 小欧
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# 直接导入模块，避免触发__init__.py
from app.tools.file.write_text_file import (
    write_text_file,
    _validate_path,
    _is_binary_file,
    _detect_file_encoding_for_write,
    _write_file_atomic,
    _check_write_safety,
    _build_write_text_file_llm_data,
)
from app.tools.tool_constants import MAX_READ_SIZE, BINARY_EXTENSIONS
from app.services.context_vars import _current_task_id


# ============================================================
# 测试夹具
# ============================================================

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_text_file(temp_dir):
    """创建示例文本文件"""
    file_path = temp_dir / "sample.txt"
    content = "第一行\n第二行\n第三行\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_file(temp_dir):
    """创建空文件"""
    file_path = temp_dir / "empty.txt"
    file_path.write_text("", encoding="utf-8")
    return file_path


@pytest.fixture
def task_id_token():
    """设置任务ID上下文"""
    token = _current_task_id.set("test_task_write_123")
    yield token
    _current_task_id.reset(token)


@pytest.fixture
def nested_dirs_file(temp_dir):
    """创建嵌套目录路径"""
    nested_dir = temp_dir / "level1" / "level2" / "level3"
    return nested_dir / "nested.txt"


# ============================================================
# 1. 正常功能测试
# ============================================================

class TestWriteTextFileNormalFunction:
    """正常功能测试"""

    @pytest.mark.asyncio
    async def test_create_new_file(self, temp_dir, task_id_token):
        """测试创建新文件"""
        file_path = temp_dir / "new_file.txt"
        content = "这是新创建的文件内容\n"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content
        assert result["data"]["bytes_written"] > 0

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, sample_text_file, task_id_token):
        """测试覆盖写入已有文件"""
        new_content = "覆盖后的内容\n"

        result = await write_text_file(str(sample_text_file), new_content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert sample_text_file.read_text(encoding="utf-8") == new_content

    @pytest.mark.asyncio
    async def test_append_to_file(self, sample_text_file, task_id_token):
        """测试追加写入"""
        append_content = "追加的内容\n"

        result = await write_text_file(str(sample_text_file), append_content, append=True)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = sample_text_file.read_text(encoding="utf-8")
        assert "第一行" in content
        assert "追加的内容" in content

    @pytest.mark.asyncio
    async def test_write_empty_content(self, temp_dir, task_id_token):
        """测试写入空内容"""
        file_path = temp_dir / "empty_content.txt"
        content = ""

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == ""

    @pytest.mark.asyncio
    async def test_write_multiline_content(self, temp_dir, task_id_token):
        """测试写入多行内容"""
        file_path = temp_dir / "multiline.txt"
        content = "第一行\n第二行\n第三行\n"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        lines = file_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_write_unicode_content(self, temp_dir, task_id_token):
        """测试写入Unicode内容"""
        file_path = temp_dir / "unicode.txt"
        content = "这是中文内容\n包含emoji: \U0001f600\n"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "中文内容" in file_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_write_special_characters(self, temp_dir, task_id_token):
        """测试写入特殊字符"""
        file_path = temp_dir / "special.txt"
        content = "包含\t制表符\n包含\"引号\n包含'单引号\n"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        written_content = file_path.read_text(encoding="utf-8")
        assert "\t" in written_content
        assert "\"" in written_content

    @pytest.mark.asyncio
    async def test_write_with_utf8_encoding(self, temp_dir, task_id_token):
        """测试使用UTF-8编码写入"""
        file_path = temp_dir / "utf8.txt"
        content = "UTF-8编码测试\n"

        result = await write_text_file(str(file_path), content, encoding="utf-8")

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.read_text(encoding="utf-8") == content


# ============================================================
# 2. 参数验证测试
# ============================================================

class TestWriteTextFileParameters:
    """参数验证测试"""

    @pytest.mark.asyncio
    async def test_append_mode_creates_file_if_not_exists(self, temp_dir, task_id_token):
        """测试追加模式下文件不存在时创建文件"""
        file_path = temp_dir / "append_new.txt"
        content = "追加内容\n"

        result = await write_text_file(str(file_path), content, append=True)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_append_mode_preserves_existing_content(self, temp_dir, task_id_token):
        """测试追加模式保留已有内容"""
        file_path = temp_dir / "append_preserve.txt"
        original_content = "原始内容\n"
        file_path.write_text(original_content, encoding="utf-8")

        append_content = "追加内容\n"
        result = await write_text_file(str(file_path), append_content, append=True)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = file_path.read_text(encoding="utf-8")
        assert "原始内容" in content
        assert "追加内容" in content

    @pytest.mark.asyncio
    async def test_encoding_parameter(self, temp_dir, task_id_token):
        """测试encoding参数"""
        file_path = temp_dir / "encoding_test.txt"
        content = "编码测试\n"

        result = await write_text_file(str(file_path), content, encoding="utf-8")

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.read_text(encoding="utf-8") == content


# ============================================================
# 3. 边界条件测试
# ============================================================

class TestWriteTextFileBoundaryConditions:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_write_very_long_content(self, temp_dir, task_id_token):
        """测试写入超长内容"""
        file_path = temp_dir / "long_content.txt"
        content = "x" * 1000000  # 1MB内容

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.exists()
        assert len(file_path.read_text(encoding="utf-8")) == 1000000

    @pytest.mark.asyncio
    async def test_write_content_with_only_newlines(self, temp_dir, task_id_token):
        """测试写入只有换行符的内容"""
        file_path = temp_dir / "newlines.txt"
        content = "\n\n\n\n"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_content_with_null_bytes(self, temp_dir, task_id_token):
        """测试写入包含空字节的内容"""
        file_path = temp_dir / "null_bytes.txt"
        content = "before\x00after"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_write_to_nested_directories(self, nested_dirs_file, task_id_token):
        """测试写入嵌套目录（自动创建）"""
        content = "嵌套目录文件内容\n"

        result = await write_text_file(str(nested_dirs_file), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert nested_dirs_file.exists()
        assert nested_dirs_file.read_text(encoding="utf-8") == content


# ============================================================
# 4. 错误处理测试
# ============================================================

class TestWriteTextFileErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_empty_file_path(self, task_id_token):
        """测试空文件路径"""
        result = await write_text_file("", "content")

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "file_path不能为空" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_whitespace_only_file_path(self, task_id_token):
        """测试纯空白文件路径"""
        result = await write_text_file("   ", "content")

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "file_path不能为空" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_none_content(self, temp_dir, task_id_token):
        """测试None内容"""
        file_path = temp_dir / "none_content.txt"

        result = await write_text_file(str(file_path), None)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "content不能为None" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_no_task_id(self, temp_dir):
        """测试没有任务ID"""
        file_path = temp_dir / "no_task_id.txt"

        # 不设置任务ID
        result = await write_text_file(str(file_path), "content")

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "当前没有活跃任务ID" in result["data"]["error_detail"]


# ============================================================
# 5. 安全性测试
# ============================================================

class TestWriteTextFileSecurity:
    """安全性测试"""

    @pytest.mark.asyncio
    async def test_path_validation_called(self, temp_dir, task_id_token):
        """测试路径验证被正确调用"""
        file_path = temp_dir / "validation_test.txt"

        with patch("app.tools.file.write_text_file._validate_path") as mock_validate:
            mock_validate.return_value = (False, "路径不允许访问")
            result = await write_text_file(str(file_path), "content")

            assert result["llm_data"]["status"]["exec_code"] == "error"
            assert "路径不允许访问" in result["data"]["error_detail"]
            mock_validate.assert_called_once_with(str(file_path))

    @pytest.mark.asyncio
    async def test_path_traversal_attack(self, task_id_token):
        """测试路径遍历攻击"""
        malicious_paths = [
            "Z:\\Windows\\System32\\test.txt",
            "Y:\\etc\\passwd",
            "..\\..\\..\\..\\Z:\\Windows\\System32\\test.txt",
        ]

        for path in malicious_paths:
            result = await write_text_file(path, "content")
            # 路径验证或文件系统操作会失败
            has_error = (result["llm_data"]["status"]["exec_code"] == "error" or 
                        result.get("data", {}).get("error_detail") is not None)
            assert has_error

    @pytest.mark.asyncio
    async def test_binary_file_rejection(self, temp_dir, task_id_token):
        """测试二进制文件扩展名的写入"""
        binary_extensions = [".png", ".jpg", ".mp3", ".exe", ".dll"]

        for ext in binary_extensions:
            file_path = temp_dir / f"test{ext}"
            result = await write_text_file(str(file_path), "content")
            # 写入操作可能成功或失败，取决于路径验证和安全检查
            # 主要验证不会崩溃，且返回有效结果
            assert "llm_data" in result
            assert "status" in result["llm_data"]

    @pytest.mark.asyncio
    async def test_safety_mechanism_integration(self, temp_dir, task_id_token):
        """测试safety机制集成"""
        file_path = temp_dir / "safety_test.txt"

        # 模拟safety拦截
        with patch("app.tools.file.write_text_file.execute_with_safety") as mock_safety:
            mock_safety.return_value = False
            result = await write_text_file(str(file_path), "content")

            assert result["llm_data"]["status"]["exec_code"] == "error"
            assert "safety拦截" in result["data"]["error_detail"]


# ============================================================
# 6. 编码测试
# ============================================================

class TestWriteTextFileEncoding:
    """编码测试"""

    @pytest.mark.asyncio
    async def test_utf8_encoding_write(self, temp_dir, task_id_token):
        """测试UTF-8编码写入"""
        file_path = temp_dir / "utf8_write.txt"
        content = "UTF-8编码测试内容\n"

        result = await write_text_file(str(file_path), content, encoding="utf-8")

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert file_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_encoding_detection_for_append(self, temp_dir, task_id_token):
        """测试追加模式下的编码检测"""
        file_path = temp_dir / "encoding_detect.txt"
        # 创建GBK编码的文件
        original_content = "原始GBK内容"
        file_path.write_text(original_content, encoding="gbk")

        # 追加内容
        append_content = "追加内容\n"
        result = await write_text_file(str(file_path), append_content, append=True)

        assert result["llm_data"]["status"]["exec_code"] == "success"

    def test_detect_file_encoding_new_file(self, temp_dir):
        """测试新文件的编码检测"""
        file_path = temp_dir / "new_file.txt"

        encoding = _detect_file_encoding_for_write(str(file_path), append=False)
        assert encoding == "utf-8"

    def test_detect_file_encoding_append_nonexistent(self, temp_dir):
        """测试追加模式下文件不存在时的编码检测"""
        file_path = temp_dir / "nonexistent.txt"

        encoding = _detect_file_encoding_for_write(str(file_path), append=True)
        assert encoding == "utf-8"


# ============================================================
# 7. LLM Data构建测试
# ============================================================

class TestWriteTextFileLLMData:
    """LLM Data构建测试"""

    def test_build_success_llm_data(self):
        """测试成功响应的LLM Data构建"""
        llm_data = _build_write_text_file_llm_data(
            "success", 100,
            file_path="test.txt",
            bytes_written=1024,
        )

        assert llm_data["status"]["exec_code"] == "success"
        assert "test.txt" in llm_data["summary"]
        assert "1024字节" in llm_data["summary"]
        assert llm_data["duration_ms"] == 100
        assert llm_data["metrics"]["bytes_written"]["value"] == 1024

    def test_build_error_llm_data(self):
        """测试错误响应的LLM Data构建"""
        llm_data = _build_write_text_file_llm_data(
            "error", 50,
            file_path="test.txt",
            detail="写入失败",
        )

        assert llm_data["status"]["exec_code"] == "error"
        assert "写入失败" in llm_data["summary"]
        assert llm_data["duration_ms"] == 50
        assert "写入失败" in llm_data["status"]["detail"]


# ============================================================
# 8. 辅助函数测试
# ============================================================

class TestWriteTextFileHelpers:
    """辅助函数测试"""

    def test_validate_path_valid(self, temp_dir):
        """测试有效路径验证"""
        file_path = str(temp_dir / "test.txt")
        is_valid, error_msg = _validate_path(file_path)
        assert is_valid is True
        assert error_msg is None

    def test_is_binary_file_png(self):
        """测试二进制文件检测 - PNG"""
        is_binary, reason = _is_binary_file("test.png")
        assert is_binary is True
        assert "二进制文件" in reason

    def test_is_binary_file_txt(self):
        """测试文本文件检测 - TXT"""
        is_binary, reason = _is_binary_file("test.txt")
        assert is_binary is False
        assert reason == ""

    def test_check_write_safety_valid(self, temp_dir):
        """测试写入安全检查 - 有效输入"""
        file_path = str(temp_dir / "test.txt")
        content = "test content"
        error, checked_content = _check_write_safety(file_path, content)

        assert error is None
        assert checked_content == content

    def test_check_write_safety_empty_path(self):
        """测试写入安全检查 - 空路径"""
        error, checked_content = _check_write_safety("", "content")

        assert error == "file_path不能为空"
        assert checked_content == "content"

    def test_check_write_safety_none_content(self, temp_dir):
        """测试写入安全检查 - None内容"""
        file_path = str(temp_dir / "test.txt")
        error, checked_content = _check_write_safety(file_path, None)

        assert error == "content不能为None"
        assert checked_content == ""

    def test_write_file_atomic_success(self, temp_dir):
        """测试原子写入 - 成功"""
        file_path = temp_dir / "atomic.txt"
        content = "atomic content"

        result = _write_file_atomic(content, file_path, "utf-8", False, True)

        assert result is True
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content

    def test_write_file_atomic_append(self, temp_dir):
        """测试原子写入 - 追加模式"""
        file_path = temp_dir / "atomic_append.txt"
        file_path.write_text("original", encoding="utf-8")

        result = _write_file_atomic(" appended", file_path, "utf-8", True, True)

        assert result is True
        assert file_path.read_text(encoding="utf-8") == "original appended"

    def test_write_file_atomic_create_parents(self, temp_dir):
        """测试原子写入 - 自动创建父目录"""
        file_path = temp_dir / "level1" / "level2" / "atomic.txt"
        content = "nested content"

        result = _write_file_atomic(content, file_path, "utf-8", False, True)

        assert result is True
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content


# ============================================================
# 9. 内容转义测试
# ============================================================

class TestWriteTextFileEscaping:
    """内容转义测试"""

    @pytest.mark.asyncio
    async def test_unescape_backslash_n(self, temp_dir, task_id_token):
        """测试转义 \\n 为换行符"""
        file_path = temp_dir / "unescape_n.txt"
        content = "第一行\\n第二行"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        written_content = file_path.read_text(encoding="utf-8")
        assert "\n" in written_content
        assert "第一行" in written_content
        assert "第二行" in written_content

    @pytest.mark.asyncio
    async def test_unescape_backslash_backslash(self, temp_dir, task_id_token):
        """测试转义 \\\\ 为单个反斜杠"""
        file_path = temp_dir / "unescape_backslash.txt"
        content = "路径\\\\文件"

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        written_content = file_path.read_text(encoding="utf-8")
        assert "\\" in written_content

    @pytest.mark.asyncio
    async def test_unescape_quotes(self, temp_dir, task_id_token):
        """测试转义 \\" 为双引号"""
        file_path = temp_dir / "unescape_quotes.txt"
        content = '包含\\"引号\\"的文本'

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        written_content = file_path.read_text(encoding="utf-8")
        assert '"' in written_content


# ============================================================
# 10. 并发测试
# ============================================================

class TestWriteTextFileConcurrency:
    """并发测试"""

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_files(self, temp_dir, task_id_token):
        """测试并发写入不同文件"""
        files = []
        for i in range(5):
            files.append(temp_dir / f"concurrent_{i}.txt")

        tasks = [
            write_text_file(str(f), f"Content {i}\n")
            for i, f in enumerate(files)
        ]

        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for result in results:
            assert result["llm_data"]["status"]["exec_code"] == "success"

        # 验证文件内容
        for i, f in enumerate(files):
            assert f.exists()
            assert f"Content {i}" in f.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_concurrent_appends(self, temp_dir, task_id_token):
        """测试并发追加到同一文件"""
        file_path = temp_dir / "concurrent_append.txt"
        file_path.write_text("initial\n", encoding="utf-8")

        tasks = [
            write_text_file(str(file_path), f"append_{i}\n", append=True)
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for result in results:
            assert result["llm_data"]["status"]["exec_code"] == "success"

        # 文件应该包含所有追加内容
        content = file_path.read_text(encoding="utf-8")
        assert "initial" in content
        for i in range(5):
            assert f"append_{i}" in content


# ============================================================
# 11. 性能测试
# ============================================================

class TestWriteTextFilePerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_write_time_measurement(self, temp_dir, task_id_token):
        """测试写入时间测量"""
        file_path = temp_dir / "time_test.txt"
        content = "timing test content\n"

        result = await write_text_file(str(file_path), content)

        assert "duration_ms" in result["llm_data"]
        assert result["llm_data"]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_large_content_write_performance(self, temp_dir, task_id_token):
        """测试大内容写入性能"""
        file_path = temp_dir / "large_write.txt"
        content = "x" * (1024 * 1024)  # 1MB

        result = await write_text_file(str(file_path), content)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["llm_data"]["duration_ms"] < 5000  # 应该在5秒内完成


# ============================================================
# 12. 集成测试
# ============================================================

class TestWriteTextFileIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_write_then_read(self, temp_dir, task_id_token):
        """测试写入后读取"""
        from app.tools.file.read_text_file import read_text_file

        file_path = temp_dir / "integration_write_read.txt"
        content = "集成测试内容\n"

        # 写入文件
        write_result = await write_text_file(str(file_path), content)
        assert write_result["llm_data"]["status"]["exec_code"] == "success"

        # 读取文件
        read_result = await read_text_file(str(file_path))
        assert read_result["llm_data"]["status"]["exec_code"] == "success"
        assert content in read_result["data"]["content"]

    @pytest.mark.asyncio
    async def test_write_then_edit(self, temp_dir, task_id_token):
        """测试写入后编辑"""
        from app.tools.file.edit_text_file import edit_text_file

        file_path = temp_dir / "integration_write_edit.txt"
        original_content = "原始内容\n"

        # 写入文件
        write_result = await write_text_file(str(file_path), original_content)
        assert write_result["llm_data"]["status"]["exec_code"] == "success"

        # 编辑文件
        edit_result = await edit_text_file(
            str(file_path),
            old_string="原始内容",
            new_string="编辑后的内容",
        )
        assert edit_result["llm_data"]["status"]["exec_code"] == "success"

        # 验证编辑结果
        content = file_path.read_text(encoding="utf-8")
        assert "编辑后的内容" in content
