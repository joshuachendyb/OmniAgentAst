# -*- coding: utf-8 -*-
"""
edit_text_file 工具全面测试

测试范围:
  1. 正常功能测试 - 单次替换、全部替换、大小写敏感
  2. 参数验证测试 - old_string、new_string、replace_all
  3. 边界条件测试 - 空字符串、特殊字符、多次匹配
  4. 错误处理测试 - 文件不存在、未找到匹配、二进制文件
  5. 安全性测试 - 路径越权、任务ID验证、safety机制
  6. 编码测试 - UTF-8、GBK、编码保持

创建时间: 2026-06-22 04:45:00
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
from app.tools.file.edit_text_file import (
    edit_text_file,
    _validate_path,
    _is_binary_file,
    _apply_replacement,
    _build_edit_text_file_llm_data,
    _try_read_file_with_encodings,
    _precise_replace_in_file,
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
    content = "Hello World\nPython is great\nHello Python\n"
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
    token = _current_task_id.set("test_task_edit_123")
    yield token
    _current_task_id.reset(token)


@pytest.fixture
def unicode_file(temp_dir):
    """创建包含Unicode内容的文件"""
    file_path = temp_dir / "unicode.txt"
    content = "这是中文内容\n包含emoji: \U0001f600\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def gbk_file(temp_dir):
    """创建GBK编码文件"""
    file_path = temp_dir / "gbk.txt"
    content = "这是GBK编码的中文内容\n"
    file_path.write_text(content, encoding="gbk")
    return file_path


@pytest.fixture
def large_file(temp_dir):
    """创建大文件"""
    file_path = temp_dir / "large.txt"
    content = "x" * (MAX_READ_SIZE + 1024)
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def binary_file(temp_dir):
    """创建二进制文件"""
    file_path = temp_dir / "test.png"
    file_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
    return file_path


# ============================================================
# 1. 正常功能测试
# ============================================================

class TestEditTextFileNormalFunction:
    """正常功能测试"""

    @pytest.mark.asyncio
    async def test_single_replacement(self, sample_text_file, task_id_token):
        """测试单次替换"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="World",
            new_string="Python",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["applied_edits"] == 1
        content = sample_text_file.read_text(encoding="utf-8")
        assert "Hello Python" in content
        assert "Hello World" not in content

    @pytest.mark.asyncio
    async def test_replace_all_occurrences(self, sample_text_file, task_id_token):
        """测试全部替换"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="Hello",
            new_string="Hi",
            replace_all=True,
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["applied_edits"] == 2
        content = sample_text_file.read_text(encoding="utf-8")
        assert "Hi World" in content
        assert "Hi Python" in content
        assert "Hello" not in content

    @pytest.mark.asyncio
    async def test_replace_with_empty_string(self, sample_text_file, task_id_token):
        """测试替换为空字符串（删除）"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="World",
            new_string="",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = sample_text_file.read_text(encoding="utf-8")
        assert "Hello " in content
        assert "World" not in content

    @pytest.mark.asyncio
    async def test_replace_multiline_content(self, temp_dir, task_id_token):
        """测试替换多行内容"""
        file_path = temp_dir / "multiline.txt"
        content = "第一行\n第二行\n第三行\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="第二行",
            new_string="新第二行",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        new_content = file_path.read_text(encoding="utf-8")
        assert "新第二行" in new_content
        assert "第一行" in new_content
        assert "第三行" in new_content

    @pytest.mark.asyncio
    async def test_replace_special_characters(self, temp_dir, task_id_token):
        """测试替换特殊字符"""
        file_path = temp_dir / "special.txt"
        content = "包含\t制表符和\"引号\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="\t制表符",
            new_string="空格",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = file_path.read_text(encoding="utf-8")
        assert "空格" in content

    @pytest.mark.asyncio
    async def test_replace_unicode_content(self, unicode_file, task_id_token):
        """测试替换Unicode内容"""
        result = await edit_text_file(
            str(unicode_file),
            old_string="中文内容",
            new_string="English content",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = unicode_file.read_text(encoding="utf-8")
        assert "English content" in content

    @pytest.mark.asyncio
    async def test_replace_preserves_file_encoding(self, gbk_file, task_id_token):
        """测试替换保持文件编码"""
        result = await edit_text_file(
            str(gbk_file),
            old_string="GBK编码",
            new_string="UTF-8编码",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证文件仍然可以正确读取
        content = gbk_file.read_text(encoding="gbk")
        assert "UTF-8编码" in content


# ============================================================
# 2. 参数验证测试
# ============================================================

class TestEditTextFileParameters:
    """参数验证测试"""

    @pytest.mark.asyncio
    async def test_empty_old_string(self, temp_dir, task_id_token):
        """测试空old_string"""
        file_path = temp_dir / "test.txt"
        file_path.write_text("content", encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="",
            new_string="new",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "old_string不能为空" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_new_string_defaults_to_empty(self, sample_text_file, task_id_token):
        """测试new_string默认为空字符串"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="World",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = sample_text_file.read_text(encoding="utf-8")
        assert "World" not in content

    @pytest.mark.asyncio
    async def test_replace_all_false(self, sample_text_file, task_id_token):
        """测试replace_all=False（默认只替换第一个）"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="Hello",
            new_string="Hi",
            replace_all=False,
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["applied_edits"] == 1
        content = sample_text_file.read_text(encoding="utf-8")
        # 只有第一个Hello被替换
        assert "Hi World" in content
        assert "Hello Python" in content

    @pytest.mark.asyncio
    async def test_replace_all_true(self, sample_text_file, task_id_token):
        """测试replace_all=True（替换所有匹配）"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="Hello",
            new_string="Hi",
            replace_all=True,
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["applied_edits"] == 2
        content = sample_text_file.read_text(encoding="utf-8")
        assert "Hello" not in content


# ============================================================
# 3. 边界条件测试
# ============================================================

class TestEditTextFileBoundaryConditions:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_replace_in_empty_file(self, empty_file, task_id_token):
        """测试在空文件中替换"""
        result = await edit_text_file(
            str(empty_file),
            old_string="anything",
            new_string="something",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "未找到匹配内容" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_replace_nonexistent_string(self, sample_text_file, task_id_token):
        """测试替换不存在的字符串"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="NonexistentString",
            new_string="replacement",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "未找到匹配内容" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_replace_with_same_string(self, sample_text_file, task_id_token):
        """测试替换为相同的字符串"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="Hello",
            new_string="Hello",
        )

        # 应该成功，但内容不变
        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = sample_text_file.read_text(encoding="utf-8")
        assert content.count("Hello") == 2

    @pytest.mark.asyncio
    async def test_replace_multiple_lines(self, temp_dir, task_id_token):
        """测试替换多行内容"""
        file_path = temp_dir / "multi_line.txt"
        content = "line1\nline2\nline3\nline4\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="line2\nline3",
            new_string="new_line2\nnew_line3",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        new_content = file_path.read_text(encoding="utf-8")
        assert "new_line2" in new_content
        assert "new_line3" in new_content

    @pytest.mark.asyncio
    async def test_replace_at_file_start(self, temp_dir, task_id_token):
        """测试在文件开头替换"""
        file_path = temp_dir / "start.txt"
        content = "Start of file\nMiddle\nEnd of file\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="Start",
            new_string="Beginning",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        new_content = file_path.read_text(encoding="utf-8")
        assert new_content.startswith("Beginning")

    @pytest.mark.asyncio
    async def test_replace_at_file_end(self, temp_dir, task_id_token):
        """测试在文件末尾替换"""
        file_path = temp_dir / "end.txt"
        content = "Start\nMiddle\nEnd of file\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="End",
            new_string="Finish",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        new_content = file_path.read_text(encoding="utf-8")
        assert "Finish" in new_content

    @pytest.mark.asyncio
    async def test_replace_adjacent_content(self, temp_dir, task_id_token):
        """测试替换相邻内容"""
        file_path = temp_dir / "adjacent.txt"
        content = "AAABBBCCC\n"
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="BBB",
            new_string="XXX",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        new_content = file_path.read_text(encoding="utf-8")
        assert "AAAXXXCCC" in new_content


# ============================================================
# 4. 错误处理测试
# ============================================================

class TestEditTextFileErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir, task_id_token):
        """测试文件不存在"""
        file_path = temp_dir / "nonexistent.txt"

        result = await edit_text_file(
            str(file_path),
            old_string="content",
            new_string="replacement",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "文件不存在" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_path_is_directory(self, temp_dir, task_id_token):
        """测试路径是目录"""
        result = await edit_text_file(
            str(temp_dir),
            old_string="content",
            new_string="replacement",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"

    @pytest.mark.asyncio
    async def test_binary_file_rejection(self, binary_file, task_id_token):
        """测试二进制文件被拒绝"""
        result = await edit_text_file(
            str(binary_file),
            old_string="content",
            new_string="replacement",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "二进制文件" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_file_too_large(self, large_file, task_id_token):
        """测试文件过大"""
        result = await edit_text_file(
            str(large_file),
            old_string="x",
            new_string="y",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "文件过大" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_no_task_id(self, temp_dir):
        """测试没有任务ID"""
        file_path = temp_dir / "no_task.txt"
        file_path.write_text("content", encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="content",
            new_string="replacement",
        )

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "当前没有活跃任务ID" in result["data"]["error_detail"]


# ============================================================
# 5. 安全性测试
# ============================================================

class TestEditTextFileSecurity:
    """安全性测试"""

    @pytest.mark.asyncio
    async def test_path_validation_called(self, temp_dir, task_id_token):
        """测试路径验证被正确调用"""
        file_path = temp_dir / "validation_test.txt"
        file_path.write_text("content", encoding="utf-8")

        with patch("app.tools.file.edit_text_file._validate_path") as mock_validate:
            mock_validate.return_value = (False, "路径不允许访问")
            result = await edit_text_file(
                str(file_path),
                old_string="content",
                new_string="replacement",
            )

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
            result = await edit_text_file(
                path,
                old_string="content",
                new_string="replacement",
            )
            # 路径验证或文件系统操作会失败
            has_error = (result["llm_data"]["status"]["exec_code"] == "error" or 
                        result.get("data", {}).get("error_detail") is not None)
            assert has_error

    @pytest.mark.asyncio
    async def test_safety_mechanism_integration(self, temp_dir, task_id_token):
        """测试safety机制集成"""
        file_path = temp_dir / "safety_test.txt"
        file_path.write_text("content", encoding="utf-8")

        # 模拟safety拦截
        with patch("app.tools.file.edit_text_file.execute_with_safety") as mock_safety:
            mock_safety.return_value = False
            result = await edit_text_file(
                str(file_path),
                old_string="content",
                new_string="replacement",
            )

            assert result["llm_data"]["status"]["exec_code"] == "error"

    @pytest.mark.asyncio
    async def test_operation_record_created(self, temp_dir, task_id_token):
        """测试操作记录被创建"""
        file_path = temp_dir / "operation_test.txt"
        file_path.write_text("content", encoding="utf-8")

        with patch("app.tools.file.edit_text_file.record_operation") as mock_record:
            mock_record.return_value = "op_123"
            result = await edit_text_file(
                str(file_path),
                old_string="content",
                new_string="replacement",
            )

            # 应该调用record_operation
            mock_record.assert_called_once()


# ============================================================
# 6. 编码测试
# ============================================================

class TestEditTextFileEncoding:
    """编码测试"""

    @pytest.mark.asyncio
    async def test_utf8_encoding_edit(self, unicode_file, task_id_token):
        """测试UTF-8编码编辑"""
        result = await edit_text_file(
            str(unicode_file),
            old_string="中文",
            new_string="English",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        content = unicode_file.read_text(encoding="utf-8")
        assert "English" in content

    @pytest.mark.asyncio
    async def test_gbk_encoding_edit(self, gbk_file, task_id_token):
        """测试GBK编码编辑"""
        result = await edit_text_file(
            str(gbk_file),
            old_string="GBK",
            new_string="UTF8",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证文件仍然可以正确读取
        content = gbk_file.read_bytes()
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_encoding_preserved_after_edit(self, temp_dir, task_id_token):
        """测试编辑后编码保持不变"""
        file_path = temp_dir / "encoding_preserve.txt"
        # 创建GBK编码文件
        original_content = "原始GBK内容"
        file_path.write_text(original_content, encoding="gbk")

        # 编辑文件
        result = await edit_text_file(
            str(file_path),
            old_string="原始",
            new_string="修改后",
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证文件仍然可以用GBK编码读取
        content = file_path.read_text(encoding="gbk")
        assert "修改后" in content


# ============================================================
# 7. _apply_replacement 函数测试
# ============================================================

class TestApplyReplacement:
    """_apply_replacement函数测试"""

    def test_single_replacement(self):
        """测试单次替换"""
        content = "Hello World Hello Python"
        new_content, count = _apply_replacement(
            content, "Hello", "Hi", ignore_case=False, replace_all=False
        )

        assert count == 1
        assert new_content == "Hi World Hello Python"

    def test_replace_all(self):
        """测试全部替换"""
        content = "Hello World Hello Python"
        new_content, count = _apply_replacement(
            content, "Hello", "Hi", ignore_case=False, replace_all=True
        )

        assert count == 2
        assert new_content == "Hi World Hi Python"

    def test_case_insensitive_single(self):
        """测试大小写不敏感的单次替换"""
        content = "hello World HELLO Python"
        new_content, count = _apply_replacement(
            content, "hello", "Hi", ignore_case=True, replace_all=False
        )

        assert count == 1
        assert "Hi World" in new_content

    def test_case_insensitive_replace_all(self):
        """测试大小写不敏感的全部替换"""
        content = "hello World HELLO Python"
        new_content, count = _apply_replacement(
            content, "hello", "Hi", ignore_case=True, replace_all=True
        )

        assert count == 2
        assert "Hi World Hi Python" in new_content

    def test_no_match(self):
        """测试没有匹配"""
        content = "Hello World"
        new_content, count = _apply_replacement(
            content, "Nonexistent", "replacement", ignore_case=False, replace_all=False
        )

        assert count == 0
        assert new_content == "Hello World"

    def test_replace_empty_string(self):
        """测试替换为空字符串"""
        content = "Hello World"
        new_content, count = _apply_replacement(
            content, "World", "", ignore_case=False, replace_all=False
        )

        assert count == 1
        assert new_content == "Hello "

    def test_replace_with_special_regex_chars(self):
        """测试替换包含正则表达式特殊字符的内容"""
        content = "Price is $10.00 (tax included)"
        new_content, count = _apply_replacement(
            content, "$10.00", "$15.00", ignore_case=False, replace_all=False
        )

        assert count == 1
        assert "$15.00" in new_content

    def test_multiline_replacement(self):
        """测试多行替换"""
        content = "Line1\nLine2\nLine3\n"
        new_content, count = _apply_replacement(
            content, "Line2", "NewLine2", ignore_case=False, replace_all=False
        )

        assert count == 1
        assert "NewLine2" in new_content


# ============================================================
# 8. LLM Data构建测试
# ============================================================

class TestEditTextFileLLMData:
    """LLM Data构建测试"""

    def test_build_success_llm_data(self):
        """测试成功响应的LLM Data构建"""
        llm_data = _build_edit_text_file_llm_data(
            "success", 100,
            file_path="test.txt",
            applied=5,
            total=10,
        )

        assert llm_data["status"]["exec_code"] == "success"
        assert "test.txt" in llm_data["summary"]
        assert "5/10处" in llm_data["summary"]
        assert llm_data["duration_ms"] == 100
        assert llm_data["metrics"]["applied"]["value"] == 5

    def test_build_error_llm_data(self):
        """测试错误响应的LLM Data构建"""
        llm_data = _build_edit_text_file_llm_data(
            "error", 50,
            file_path="test.txt",
            detail="编辑失败",
        )

        assert llm_data["status"]["exec_code"] == "error"
        assert "编辑失败" in llm_data["summary"]
        assert llm_data["duration_ms"] == 50
        assert "编辑失败" in llm_data["status"]["detail"]


# ============================================================
# 9. 辅助函数测试
# ============================================================

class TestEditTextFileHelpers:
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


# ============================================================
# 10. 并发测试
# ============================================================

class TestEditTextFileConcurrency:
    """并发测试"""

    @pytest.mark.asyncio
    async def test_concurrent_edits_different_files(self, temp_dir, task_id_token):
        """测试并发编辑不同文件"""
        files = []
        for i in range(5):
            file_path = temp_dir / f"concurrent_{i}.txt"
            file_path.write_text(f"Original content {i}\n", encoding="utf-8")
            files.append(file_path)

        tasks = [
            edit_text_file(
                str(f),
                old_string=f"Original content {i}",
                new_string=f"Modified content {i}",
            )
            for i, f in enumerate(files)
        ]

        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for result in results:
            assert result["llm_data"]["status"]["exec_code"] == "success"

        # 验证文件内容
        for i, f in enumerate(files):
            content = f.read_text(encoding="utf-8")
            assert f"Modified content {i}" in content


# ============================================================
# 11. 性能测试
# ============================================================

class TestEditTextFilePerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_edit_time_measurement(self, sample_text_file, task_id_token):
        """测试编辑时间测量"""
        result = await edit_text_file(
            str(sample_text_file),
            old_string="Hello",
            new_string="Hi",
        )

        assert "duration_ms" in result["llm_data"]
        assert result["llm_data"]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_large_file_edit_performance(self, temp_dir, task_id_token):
        """测试大文件编辑性能"""
        file_path = temp_dir / "large_edit.txt"
        # 创建一个1MB的文件
        content = "x" * (1024 * 1024)
        file_path.write_text(content, encoding="utf-8")

        result = await edit_text_file(
            str(file_path),
            old_string="x",
            new_string="y",
            replace_all=True,
        )

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["llm_data"]["duration_ms"] < 10000  # 应该在10秒内完成


# ============================================================
# 12. 集成测试
# ============================================================

class TestEditTextFileIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_edit_then_read(self, temp_dir, task_id_token):
        """测试编辑后读取"""
        from app.tools.file.read_text_file import read_text_file

        file_path = temp_dir / "integration_edit_read.txt"
        original_content = "原始内容\n"
        file_path.write_text(original_content, encoding="utf-8")

        # 编辑文件
        edit_result = await edit_text_file(
            str(file_path),
            old_string="原始内容",
            new_string="编辑后的内容",
        )
        assert edit_result["llm_data"]["status"]["exec_code"] == "success"

        # 读取文件
        read_result = await read_text_file(str(file_path))
        assert read_result["llm_data"]["status"]["exec_code"] == "success"
        assert "编辑后的内容" in read_result["data"]["content"]

    @pytest.mark.asyncio
    async def test_multiple_edits(self, temp_dir, task_id_token):
        """测试多次编辑"""
        file_path = temp_dir / "multiple_edits.txt"
        content = "AAA BBB CCC DDD\n"
        file_path.write_text(content, encoding="utf-8")

        # 第一次编辑
        result1 = await edit_text_file(
            str(file_path),
            old_string="AAA",
            new_string="111",
        )
        assert result1["llm_data"]["status"]["exec_code"] == "success"

        # 第二次编辑
        result2 = await edit_text_file(
            str(file_path),
            old_string="BBB",
            new_string="222",
        )
        assert result2["llm_data"]["status"]["exec_code"] == "success"

        # 第三次编辑
        result3 = await edit_text_file(
            str(file_path),
            old_string="CCC",
            new_string="333",
        )
        assert result3["llm_data"]["status"]["exec_code"] == "success"

        # 验证最终内容
        content = file_path.read_text(encoding="utf-8")
        assert "111" in content
        assert "222" in content
        assert "333" in content

    @pytest.mark.asyncio
    async def test_edit_after_write(self, temp_dir, task_id_token):
        """测试写入后编辑"""
        from app.tools.file.write_text_file import write_text_file

        file_path = temp_dir / "write_then_edit.txt"
        original_content = "写入的内容\n"

        # 写入文件
        write_result = await write_text_file(str(file_path), original_content)
        assert write_result["llm_data"]["status"]["exec_code"] == "success"

        # 编辑文件
        edit_result = await edit_text_file(
            str(file_path),
            old_string="写入",
            new_string="编辑后",
        )
        assert edit_result["llm_data"]["status"]["exec_code"] == "success"

        # 验证编辑结果
        content = file_path.read_text(encoding="utf-8")
        assert "编辑后" in content
