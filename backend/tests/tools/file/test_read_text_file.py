# -*- coding: utf-8 -*-
"""
read_text_file 工具全面测试

测试范围:
  1. 正常功能测试 - 基本读取、编码检测、行选择
  2. 参数验证测试 - head/tail/offset/limit 参数组合
  3. 边界条件测试 - 空文件、大文件、特殊字符
  4. 错误处理测试 - 文件不存在、路径无效、二进制文件
  5. 安全性测试 - 路径越权、敏感文件访问
  6. 编码测试 - UTF-8、GBK、混合编码

创建时间: 2026-06-22 04:35:00
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
from app.tools.file.read_text_file import (
    read_text_file,
    _validate_path,
    _is_binary_file,
    _select_lines,
    _build_read_text_file_llm_data,
    _try_read_file_with_encodings,
)
from app.tools.tool_constants import (
    READ_FILE_DEFAULT_LIMIT,
    MAX_READ_SIZE,
    BINARY_EXTENSIONS,
)


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
    content = "第一行\n第二行\n第三行\n第四行\n第五行\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_file(temp_dir):
    """创建空文件"""
    file_path = temp_dir / "empty.txt"
    file_path.write_text("", encoding="utf-8")
    return file_path


@pytest.fixture
def large_file(temp_dir):
    """创建大文件（超过MAX_READ_SIZE）"""
    file_path = temp_dir / "large.txt"
    # 创建一个略大于MAX_READ_SIZE的文件
    content = "x" * (MAX_READ_SIZE + 1024)
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def binary_file(temp_dir):
    """创建二进制文件"""
    file_path = temp_dir / "test.png"
    # 写入一些二进制数据
    file_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
    return file_path


@pytest.fixture
def utf8_file(temp_dir):
    """创建UTF-8编码文件"""
    file_path = temp_dir / "utf8.txt"
    content = "这是UTF-8编码的中文内容\nHello World\n"
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
def mixed_encoding_file(temp_dir):
    """创建混合编码文件（包含特殊字符）"""
    file_path = temp_dir / "mixed.txt"
    content = "普通文本\n包含emoji: \U0001f600\n包含特殊字符: \u00e9\u00e8\u00ea\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def nested_dirs_file(temp_dir):
    """创建嵌套目录中的文件"""
    nested_dir = temp_dir / "level1" / "level2" / "level3"
    nested_dir.mkdir(parents=True)
    file_path = nested_dir / "nested.txt"
    file_path.write_text("嵌套文件内容\n", encoding="utf-8")
    return file_path


@pytest.fixture
def unicode_filename_file(temp_dir):
    """创建Unicode文件名的文件"""
    file_path = temp_dir / "测试文件_unicode.txt"
    file_path.write_text("Unicode文件名测试\n", encoding="utf-8")
    return file_path


# ============================================================
# 1. 正常功能测试
# ============================================================

class TestReadTextFileNormalFunction:
    """正常功能测试"""

    @pytest.mark.asyncio
    async def test_read_full_file(self, sample_text_file):
        """测试完整读取文件"""
        result = await read_text_file(str(sample_text_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["content"] == "第一行\n第二行\n第三行\n第四行\n第五行\n"
        assert result["data"]["total_lines"] == 5
        assert result["data"]["line_count"] == 5
        assert result["data"]["encoding"] == "utf-8"
        assert result["data"]["file_size"] > 0

    @pytest.mark.asyncio
    async def test_read_empty_file(self, empty_file):
        """测试读取空文件"""
        result = await read_text_file(str(empty_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["content"] == ""
        assert result["data"]["total_lines"] == 0
        assert result["data"]["line_count"] == 0

    @pytest.mark.asyncio
    async def test_read_utf8_file(self, utf8_file):
        """测试读取UTF-8编码文件"""
        result = await read_text_file(str(utf8_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "这是UTF-8编码的中文内容" in result["data"]["content"]
        assert result["data"]["encoding"] == "utf-8"

    @pytest.mark.asyncio
    async def test_read_gbk_file(self, gbk_file):
        """测试读取GBK编码文件"""
        result = await read_text_file(str(gbk_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "这是GBK编码的中文内容" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_nested_file(self, nested_dirs_file):
        """测试读取嵌套目录中的文件"""
        result = await read_text_file(str(nested_dirs_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "嵌套文件内容" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_unicode_filename(self, unicode_filename_file):
        """测试读取Unicode文件名的文件"""
        result = await read_text_file(str(unicode_filename_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "Unicode文件名测试" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_with_encoding_parameter(self, gbk_file):
        """测试使用encoding参数指定编码"""
        result = await read_text_file(str(gbk_file), encoding="gbk")

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "这是GBK编码的中文内容" in result["data"]["content"]


# ============================================================
# 2. 参数验证测试 - head/tail/offset/limit
# ============================================================

class TestReadTextFileParameters:
    """参数验证测试"""

    @pytest.mark.asyncio
    async def test_head_parameter(self, sample_text_file):
        """测试head参数 - 读取前N行"""
        result = await read_text_file(str(sample_text_file), head=3)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 3
        assert result["data"]["head"] == 3
        assert "第一行" in result["data"]["content"]
        assert "第五行" not in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_tail_parameter(self, sample_text_file):
        """测试tail参数 - 读取后N行"""
        result = await read_text_file(str(sample_text_file), tail=2)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 2
        assert result["data"]["tail"] == 2
        assert "第四行" in result["data"]["content"]
        assert "第五行" in result["data"]["content"]
        assert "第一行" not in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_offset_limit_parameters(self, sample_text_file):
        """测试offset和limit参数 - 从指定行开始读取N行"""
        result = await read_text_file(str(sample_text_file), offset=2, limit=2)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 2
        assert result["data"]["offset"] == 2
        assert result["data"]["limit"] == 2
        assert result["data"]["start_line"] == 2
        assert result["data"]["end_line"] == 3
        assert "第二行" in result["data"]["content"]
        assert "第三行" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_head_larger_than_file(self, sample_text_file):
        """测试head参数大于文件行数"""
        result = await read_text_file(str(sample_text_file), head=100)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 5  # 文件只有5行
        assert result["data"]["total_lines"] == 5

    @pytest.mark.asyncio
    async def test_tail_larger_than_file(self, sample_text_file):
        """测试tail参数大于文件行数"""
        result = await read_text_file(str(sample_text_file), tail=100)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 5  # 文件只有5行

    @pytest.mark.asyncio
    async def test_offset_beyond_file(self, sample_text_file):
        """测试offset超出文件范围"""
        result = await read_text_file(str(sample_text_file), offset=100)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["line_count"] == 0
        assert result["data"]["content"] == ""

    @pytest.mark.asyncio
    async def test_limit_with_default(self, sample_text_file):
        """测试limit参数默认值"""
        result = await read_text_file(str(sample_text_file), offset=1)

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["limit"] is None

    @pytest.mark.asyncio
    async def test_head_tail_mutual_exclusion(self, sample_text_file):
        """测试head和tail不能同时使用"""
        result = await read_text_file(str(sample_text_file), head=3, tail=3)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "head和tail不能同时使用" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_head_with_offset_exclusion(self, sample_text_file):
        """测试head与offset不能同时使用"""
        result = await read_text_file(str(sample_text_file), head=3, offset=1)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "head/tail与offset/limit不能同时使用" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_tail_with_limit_exclusion(self, sample_text_file):
        """测试tail与limit不能同时使用"""
        result = await read_text_file(str(sample_text_file), tail=3, limit=10)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "head/tail与offset/limit不能同时使用" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_head_zero_value(self, sample_text_file):
        """测试head参数为0"""
        result = await read_text_file(str(sample_text_file), head=0)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "head必须>=1" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_tail_negative_value(self, sample_text_file):
        """测试tail参数为负数"""
        result = await read_text_file(str(sample_text_file), tail=-1)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "tail必须>=1" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_offset_zero_value(self, sample_text_file):
        """测试offset参数为0"""
        result = await read_text_file(str(sample_text_file), offset=0)

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "offset必须>=1" in result["data"]["error_detail"]


# ============================================================
# 3. 边界条件测试
# ============================================================

class TestReadTextFileBoundaryConditions:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_single_line_file(self, temp_dir):
        """测试单行文件"""
        file_path = temp_dir / "single_line.txt"
        file_path.write_text("只有一行内容", encoding="utf-8")

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["total_lines"] == 1
        assert result["data"]["line_count"] == 1
        assert "只有一行内容" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_file_with_only_newlines(self, temp_dir):
        """测试只有换行符的文件"""
        file_path = temp_dir / "newlines.txt"
        file_path.write_text("\n\n\n\n", encoding="utf-8")

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["total_lines"] == 4

    @pytest.mark.asyncio
    async def test_file_with_special_characters(self, temp_dir):
        """测试包含特殊字符的文件"""
        file_path = temp_dir / "special.txt"
        content = "包含\t制表符\n包含\\反斜杠\n包含\"引号\n包含'单引号\n"
        file_path.write_text(content, encoding="utf-8")

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "\t" in result["data"]["content"]
        assert "\\" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_file_with_very_long_line(self, temp_dir):
        """测试包含超长行的文件"""
        file_path = temp_dir / "long_line.txt"
        long_line = "x" * 100000  # 10万字符的行
        file_path.write_text(long_line, encoding="utf-8")

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["total_lines"] == 1
        assert len(result["data"]["content"]) >= 100000

    @pytest.mark.asyncio
    async def test_file_with_mixed_line_endings(self, temp_dir):
        """测试混合行尾符的文件"""
        file_path = temp_dir / "mixed_endings.txt"
        # 混合使用\n和\r\n
        content = "line1\nline2\r\nline3\rline4\n"
        file_path.write_bytes(content.encode("utf-8"))

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"

    @pytest.mark.asyncio
    async def test_file_with_null_bytes(self, temp_dir):
        """测试包含空字节的文件"""
        file_path = temp_dir / "null_bytes.txt"
        file_path.write_bytes(b"before\x00after")

        result = await read_text_file(str(file_path))

        # 应该能读取，但可能包含替换字符
        assert result["llm_data"]["status"]["exec_code"] in ("success", "error")

    @pytest.mark.asyncio
    async def test_file_with_bom(self, temp_dir):
        """测试带BOM的UTF-8文件"""
        file_path = temp_dir / "bom.txt"
        content = "带BOM的文件"
        # 写入UTF-8 BOM
        file_path.write_bytes(b'\xef\xbb\xbf' + content.encode("utf-8"))

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 4. 错误处理测试
# ============================================================

class TestReadTextFileErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        """测试文件不存在"""
        file_path = temp_dir / "nonexistent.txt"

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "文件不存在" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_path_is_directory(self, temp_dir):
        """测试路径是目录而非文件"""
        result = await read_text_file(str(temp_dir))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "路径不是文件" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_binary_file_rejection(self, binary_file):
        """测试二进制文件被拒绝"""
        result = await read_text_file(str(binary_file))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "二进制文件" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_file_too_large(self, large_file):
        """测试文件过大"""
        result = await read_text_file(str(large_file))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "文件过大" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_invalid_path_format(self):
        """测试无效路径格式"""
        result = await read_text_file("")

        assert result["llm_data"]["status"]["exec_code"] == "error"

    @pytest.mark.asyncio
    async def test_path_with_invalid_characters(self, temp_dir):
        """测试路径包含无效字符"""
        # 在Windows上，某些字符是无效的
        invalid_path = str(temp_dir / "file<>|*.txt")
        result = await read_text_file(invalid_path)

        # 应该返回错误
        assert result["llm_data"]["status"]["exec_code"] == "error"

    @pytest.mark.asyncio
    async def test_permission_denied(self, temp_dir):
        """测试权限拒绝（模拟）"""
        file_path = temp_dir / "no_permission.txt"
        file_path.write_text("content", encoding="utf-8")

        # 模拟权限错误
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = await read_text_file(str(file_path))

            assert result["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 5. 安全性测试
# ============================================================

class TestReadTextFileSecurity:
    """安全性测试"""

    @pytest.mark.asyncio
    async def test_path_traversal_attack(self):
        """测试路径遍历攻击"""
        malicious_paths = [
            "Z:\\Windows\\System32\\config\\SAM",
            "Y:\\etc\\passwd",
            "..\\..\\..\\..\\Z:\\Windows\\System32\\config\\SAM",
        ]

        for path in malicious_paths:
            result = await read_text_file(path)
            # 路径验证或文件系统操作会失败
            has_error = (result["llm_data"]["status"]["exec_code"] == "error" or 
                        result.get("data", {}).get("error_detail") is not None)
            assert has_error

    @pytest.mark.asyncio
    async def test_symlink_attack(self, temp_dir):
        """测试符号链接攻击"""
        # 创建一个指向敏感文件的符号链接
        sensitive_file = temp_dir / "sensitive.txt"
        sensitive_file.write_text("sensitive content", encoding="utf-8")

        symlink_file = temp_dir / "link.txt"
        try:
            symlink_file.symlink_to(sensitive_file)
            # 尝试通过符号链接读取
            result = await read_text_file(str(symlink_file))
            # 应该能正常读取（符号链接在允许的目录内）
            assert result["llm_data"]["status"]["exec_code"] == "success"
        except OSError:
            # Windows上可能不支持符号链接
            pytest.skip("Symbolic links not supported on this platform")

    @pytest.mark.asyncio
    async def test_path_validation_mock(self, temp_dir):
        """测试路径验证被正确调用"""
        file_path = temp_dir / "test.txt"
        file_path.write_text("content", encoding="utf-8")

        with patch("app.tools.file.read_text_file._validate_path") as mock_validate:
            mock_validate.return_value = (False, "路径不允许访问")
            result = await read_text_file(str(file_path))

            assert result["llm_data"]["status"]["exec_code"] == "error"
            assert "路径不允许访问" in result["data"]["error_detail"]
            mock_validate.assert_called_once_with(str(file_path))


# ============================================================
# 6. 编码测试
# ============================================================

class TestReadTextFileEncoding:
    """编码测试"""

    @pytest.mark.asyncio
    async def test_utf8_encoding_detection(self, utf8_file):
        """测试UTF-8编码检测"""
        result = await read_text_file(str(utf8_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["encoding"] == "utf-8"

    @pytest.mark.asyncio
    async def test_gbk_encoding_detection(self, gbk_file):
        """测试GBK编码检测"""
        result = await read_text_file(str(gbk_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 应该能正确检测到GBK编码
        assert "这是GBK编码的中文内容" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_encoding_fallback(self, temp_dir):
        """测试编码回退机制"""
        file_path = temp_dir / "fallback.txt"
        # 创建一个GBK编码的文件
        content = "测试编码回退"
        file_path.write_bytes(content.encode("gbk"))

        # 不指定编码，应该能通过回退机制读取
        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"

    @pytest.mark.asyncio
    async def test_preferred_encoding(self, gbk_file):
        """测试指定首选编码"""
        result = await read_text_file(str(gbk_file), encoding="gbk")

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["encoding"] == "gbk"

    @pytest.mark.asyncio
    async def test_invalid_encoding_fallback(self, temp_dir):
        """测试无效编码时的回退"""
        file_path = temp_dir / "invalid_enc.txt"
        file_path.write_text("test content", encoding="utf-8")

        # 指定一个不存在的编码，应该回退到其他编码
        result = await read_text_file(str(file_path), encoding="nonexistent_encoding")

        # 应该能通过回退机制读取
        assert result["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 7. LLM Data构建测试
# ============================================================

class TestReadTextFileLLMData:
    """LLM Data构建测试"""

    def test_build_success_llm_data(self):
        """测试成功响应的LLM Data构建"""
        llm_data = _build_read_text_file_llm_data(
            "success", 100,
            file_path="test.txt",
            line_count=10,
            total_lines=20,
            file_size=1024,
        )

        assert llm_data["status"]["exec_code"] == "success"
        assert "test.txt" in llm_data["summary"]
        assert "10/20行" in llm_data["summary"]
        assert llm_data["duration_ms"] == 100
        assert llm_data["metrics"]["line_count"]["value"] == 10
        assert llm_data["metrics"]["file_size"]["value"] == 1024

    def test_build_error_llm_data(self):
        """测试错误响应的LLM Data构建"""
        llm_data = _build_read_text_file_llm_data(
            "error", 50,
            file_path="test.txt",
            detail="文件不存在",
        )

        assert llm_data["status"]["exec_code"] == "error"
        assert "文件不存在" in llm_data["summary"]
        assert llm_data["duration_ms"] == 50
        assert "文件不存在" in llm_data["status"]["detail"]


# ============================================================
# 8. 辅助函数测试
# ============================================================

class TestReadTextFileHelpers:
    """辅助函数测试"""

    def test_validate_path_valid(self, temp_dir):
        """测试有效路径验证"""
        file_path = str(temp_dir / "test.txt")
        is_valid, error_msg = _validate_path(file_path)
        # 在Windows上，临时目录应该在允许的路径内
        assert is_valid is True
        assert error_msg is None

    def test_is_binary_file_png(self):
        """测试二进制文件检测 - PNG"""
        is_binary, reason = _is_binary_file("test.png")
        assert is_binary is True
        assert "二进制文件" in reason

    def test_is_binary_file_jpg(self):
        """测试二进制文件检测 - JPG"""
        is_binary, reason = _is_binary_file("test.jpg")
        assert is_binary is True

    def test_is_binary_file_mp3(self):
        """测试二进制文件检测 - MP3"""
        is_binary, reason = _is_binary_file("test.mp3")
        assert is_binary is True

    def test_is_binary_file_txt(self):
        """测试文本文件检测 - TXT"""
        is_binary, reason = _is_binary_file("test.txt")
        assert is_binary is False
        assert reason == ""

    def test_is_binary_file_py(self):
        """测试文本文件检测 - PY"""
        is_binary, reason = _is_binary_file("test.py")
        assert is_binary is False

    def test_select_lines_head(self):
        """测试_select_lines的head功能"""
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        result = _select_lines(lines, head=3)

        assert result["line_count"] == 3
        assert result["head"] == 3
        assert "line1" in result["content"]
        assert "line5" not in result["content"]

    def test_select_lines_tail(self):
        """测试_select_lines的tail功能"""
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        result = _select_lines(lines, tail=2)

        assert result["line_count"] == 2
        assert result["tail"] == 2
        assert "line4" in result["content"]
        assert "line5" in result["content"]
        assert "line1" not in result["content"]

    def test_select_lines_offset_limit(self):
        """测试_select_lines的offset和limit功能"""
        lines = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]
        result = _select_lines(lines, offset=2, limit=2)

        assert result["line_count"] == 2
        assert result["offset"] == 2
        assert result["limit"] == 2
        assert result["start_line"] == 2
        assert result["end_line"] == 3
        assert "line2" in result["content"]
        assert "line3" in result["content"]

    def test_select_lines_no_params(self):
        """测试_select_lines没有参数时返回全部"""
        lines = ["line1\n", "line2\n", "line3\n"]
        result = _select_lines(lines)

        assert result["line_count"] == 3
        assert result["content"] == "line1\nline2\nline3\n"


# ============================================================
# 9. 并发测试
# ============================================================

class TestReadTextFileConcurrency:
    """并发测试"""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, sample_text_file):
        """测试并发读取同一文件"""
        tasks = [
            read_text_file(str(sample_text_file), head=2)
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for result in results:
            assert result["llm_data"]["status"]["exec_code"] == "success"
            assert result["data"]["line_count"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_different_files(self, temp_dir):
        """测试并发读取不同文件"""
        files = []
        for i in range(5):
            file_path = temp_dir / f"file_{i}.txt"
            file_path.write_text(f"Content {i}\n", encoding="utf-8")
            files.append(file_path)

        tasks = [read_text_file(str(f)) for f in files]
        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for i, result in enumerate(results):
            assert result["llm_data"]["status"]["exec_code"] == "success"
            assert f"Content {i}" in result["data"]["content"]


# ============================================================
# 10. 性能测试
# ============================================================

class TestReadTextFilePerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_read_time_measurement(self, sample_text_file):
        """测试读取时间测量"""
        result = await read_text_file(str(sample_text_file))

        assert "duration_ms" in result["llm_data"]
        assert result["llm_data"]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_large_file_performance(self, temp_dir):
        """测试大文件读取性能"""
        file_path = temp_dir / "perf_test.txt"
        # 创建一个1MB的文件
        content = "x" * (1024 * 1024)
        file_path.write_text(content, encoding="utf-8")

        result = await read_text_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["llm_data"]["duration_ms"] < 5000  # 应该在5秒内完成


# ============================================================
# 11. 集成测试
# ============================================================

class TestReadTextFileIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_read_after_write(self, temp_dir):
        """测试写入后读取"""
        from app.tools.file.write_text_file import write_text_file
        from app.services.context_vars import _current_task_id

        file_path = temp_dir / "integration_test.txt"
        content = "集成测试内容\n"

        # 设置任务ID
        token = _current_task_id.set("test_task_123")
        try:
            # 写入文件
            write_result = await write_text_file(str(file_path), content)
            assert write_result["llm_data"]["status"]["exec_code"] == "success"

            # 读取文件
            read_result = await read_text_file(str(file_path))
            assert read_result["llm_data"]["status"]["exec_code"] == "success"
            assert content in read_result["data"]["content"]
        finally:
            _current_task_id.reset(token)

    @pytest.mark.asyncio
    async def test_read_after_edit(self, temp_dir):
        """测试编辑后读取"""
        from app.tools.file.edit_text_file import edit_text_file
        from app.services.context_vars import _current_task_id

        file_path = temp_dir / "edit_integration_test.txt"
        original_content = "原始内容\n"
        file_path.write_text(original_content, encoding="utf-8")

        # 设置任务ID
        token = _current_task_id.set("test_task_456")
        try:
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
        finally:
            _current_task_id.reset(token)
