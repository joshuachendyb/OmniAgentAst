# -*- coding: utf-8 -*-
"""
read_media_file 工具全面测试

测试范围:
  1. 正常功能测试 - 图片、音频、视频文件读取
  2. MIME类型测试 - 各种媒体文件扩展名映射
  3. 边界条件测试 - 空文件、小文件、大文件
  4. 错误处理测试 - 文件不存在、路径无效、PDF拒绝
  5. 安全性测试 - 路径越权、文件大小限制
  6. Base64编码测试 - 编码正确性、特殊字符

创建时间: 2026-06-22 04:50:00
编写人: 小欧
"""

import asyncio
import base64
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
from app.tools.file.read_media_file import (
    read_media_file,
    _validate_path,
    _build_read_media_file_llm_data,
    _MIME_MAP,
)
from app.tools.tool_constants import MAX_MEDIA_READ_SIZE


# ============================================================
# 测试夹具
# ============================================================

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_image_file(temp_dir):
    """创建示例图片文件"""
    file_path = temp_dir / "sample.png"
    # 写入一些二进制数据（模拟PNG文件头）
    file_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01')
    return file_path


@pytest.fixture
def sample_jpg_file(temp_dir):
    """创建示例JPG文件"""
    file_path = temp_dir / "sample.jpg"
    # 写入JPG文件头
    file_path.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00')
    return file_path


@pytest.fixture
def sample_gif_file(temp_dir):
    """创建示例GIF文件"""
    file_path = temp_dir / "sample.gif"
    # 写入GIF文件头
    file_path.write_bytes(b'GIF89a\x01\x00\x01\x00')
    return file_path


@pytest.fixture
def sample_mp3_file(temp_dir):
    """创建示例MP3文件"""
    file_path = temp_dir / "sample.mp3"
    # 写入MP3文件头
    file_path.write_bytes(b'\xff\xfb\x90\x00\x00\x00\x00\x00')
    return file_path


@pytest.fixture
def sample_wav_file(temp_dir):
    """创建示例WAV文件"""
    file_path = temp_dir / "sample.wav"
    # 写入WAV文件头
    file_path.write_bytes(b'RIFF$\x00\x00\x00WAVEfmt ')
    return file_path


@pytest.fixture
def sample_mp4_file(temp_dir):
    """创建示例MP4文件"""
    file_path = temp_dir / "sample.mp4"
    # 写入MP4文件头
    file_path.write_bytes(b'\x00\x00\x00\x1cftypisom')
    return file_path


@pytest.fixture
def sample_pdf_file(temp_dir):
    """创建示例PDF文件"""
    file_path = temp_dir / "sample.pdf"
    file_path.write_text("%PDF-1.4\n", encoding="utf-8")
    return file_path


@pytest.fixture
def empty_file(temp_dir):
    """创建空文件"""
    file_path = temp_dir / "empty.png"
    file_path.write_bytes(b"")
    return file_path


@pytest.fixture
def large_file(temp_dir):
    """创建大文件（超过MAX_MEDIA_READ_SIZE）"""
    file_path = temp_dir / "large.png"
    # 创建一个略大于MAX_MEDIA_READ_SIZE的文件
    content = b'\x89PNG' + b'\x00' * (MAX_MEDIA_READ_SIZE + 1024)
    file_path.write_bytes(content)
    return file_path


@pytest.fixture
def nested_dirs_file(temp_dir):
    """创建嵌套目录中的文件"""
    nested_dir = temp_dir / "level1" / "level2" / "level3"
    nested_dir.mkdir(parents=True)
    file_path = nested_dir / "nested.png"
    file_path.write_bytes(b'\x89PNG\r\n\x1a\n')
    return file_path


@pytest.fixture
def unicode_filename_file(temp_dir):
    """创建Unicode文件名的文件"""
    file_path = temp_dir / "测试文件_unicode.png"
    file_path.write_bytes(b'\x89PNG\r\n\x1a\n')
    return file_path


# ============================================================
# 1. 正常功能测试
# ============================================================

class TestReadMediaFileNormalFunction:
    """正常功能测试"""

    @pytest.mark.asyncio
    async def test_read_png_file(self, sample_image_file):
        """测试读取PNG文件"""
        result = await read_media_file(str(sample_image_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.png"
        assert result["data"]["mime_type"] == "image/png"
        assert result["data"]["file_size"] > 0
        assert result["data"]["base64_data"] is not None
        assert len(result["data"]["base64_data"]) > 0

    @pytest.mark.asyncio
    async def test_read_jpg_file(self, sample_jpg_file):
        """测试读取JPG文件"""
        result = await read_media_file(str(sample_jpg_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.jpg"
        assert result["data"]["mime_type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_read_gif_file(self, sample_gif_file):
        """测试读取GIF文件"""
        result = await read_media_file(str(sample_gif_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.gif"
        assert result["data"]["mime_type"] == "image/gif"

    @pytest.mark.asyncio
    async def test_read_mp3_file(self, sample_mp3_file):
        """测试读取MP3文件"""
        result = await read_media_file(str(sample_mp3_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.mp3"
        assert result["data"]["mime_type"] == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_read_wav_file(self, sample_wav_file):
        """测试读取WAV文件"""
        result = await read_media_file(str(sample_wav_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.wav"
        assert result["data"]["mime_type"] == "audio/wav"

    @pytest.mark.asyncio
    async def test_read_mp4_file(self, sample_mp4_file):
        """测试读取MP4文件"""
        result = await read_media_file(str(sample_mp4_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "sample.mp4"
        assert result["data"]["mime_type"] == "video/mp4"

    @pytest.mark.asyncio
    async def test_read_nested_file(self, nested_dirs_file):
        """测试读取嵌套目录中的文件"""
        result = await read_media_file(str(nested_dirs_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_name"] == "nested.png"
        assert result["data"]["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_read_unicode_filename(self, unicode_filename_file):
        """测试读取Unicode文件名的文件"""
        result = await read_media_file(str(unicode_filename_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert "unicode.png" in result["data"]["file_name"]


# ============================================================
# 2. MIME类型测试
# ============================================================

class TestReadMediaFileMIMEType:
    """MIME类型测试"""

    def test_image_mime_types(self):
        """测试图片MIME类型映射"""
        image_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".ico": "image/x-icon",
            ".heic": "image/heic",
            ".heif": "image/heif",
        }

        for ext, expected_mime in image_types.items():
            assert _MIME_MAP[ext] == expected_mime, f"MIME类型映射错误: {ext}"

    def test_audio_mime_types(self):
        """测试音频MIME类型映射"""
        audio_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".wma": "audio/x-ms-wma",
            ".mid": "audio/midi",
            ".midi": "audio/midi",
        }

        for ext, expected_mime in audio_types.items():
            assert _MIME_MAP[ext] == expected_mime, f"MIME类型映射错误: {ext}"

    def test_video_mime_types(self):
        """测试视频MIME类型映射"""
        video_types = {
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
            ".wmv": "video/x-ms-wmv",
        }

        for ext, expected_mime in video_types.items():
            assert _MIME_MAP[ext] == expected_mime, f"MIME类型映射错误: {ext}"

    def test_unknown_extension_fallback(self):
        """测试未知扩展名回退到application/octet-stream"""
        unknown_extensions = [".xyz", ".abc", ".custom", ".unknown"]

        for ext in unknown_extensions:
            mime_type = _MIME_MAP.get(ext, "application/octet-stream")
            assert mime_type == "application/octet-stream"


# ============================================================
# 3. 边界条件测试
# ============================================================

class TestReadMediaFileBoundaryConditions:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_read_empty_file(self, empty_file):
        """测试读取空文件"""
        result = await read_media_file(str(empty_file))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_size"] == 0
        # 空文件的base64编码应该是空字符串
        assert result["data"]["base64_data"] == ""

    @pytest.mark.asyncio
    async def test_read_single_byte_file(self, temp_dir):
        """测试读取单字节文件"""
        file_path = temp_dir / "single_byte.png"
        file_path.write_bytes(b'\x89')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_size"] == 1
        # 验证base64编码正确
        expected_b64 = base64.b64encode(b'\x89').decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64

    @pytest.mark.asyncio
    async def test_read_small_file(self, temp_dir):
        """测试读取小文件"""
        file_path = temp_dir / "small.png"
        content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        file_path.write_bytes(content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["file_size"] == len(content)
        # 验证base64编码正确
        expected_b64 = base64.b64encode(content).decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64

    @pytest.mark.asyncio
    async def test_read_file_with_special_content(self, temp_dir):
        """测试读取包含特殊内容的文件"""
        file_path = temp_dir / "special.png"
        # 包含所有可能的字节值
        content = bytes(range(256))
        file_path.write_bytes(content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证base64编码正确
        expected_b64 = base64.b64encode(content).decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64


# ============================================================
# 4. 错误处理测试
# ============================================================

class TestReadMediaFileErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        """测试文件不存在"""
        file_path = temp_dir / "nonexistent.png"

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "文件不存在" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_path_is_directory(self, temp_dir):
        """测试路径是目录"""
        result = await read_media_file(str(temp_dir))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "路径不是文件" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_file_too_large(self, large_file):
        """测试文件过大"""
        result = await read_media_file(str(large_file))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "媒体文件过大" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_pdf_file_rejection(self, sample_pdf_file):
        """测试PDF文件被拒绝"""
        result = await read_media_file(str(sample_pdf_file))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "PDF" in result["data"]["error_detail"]
        assert "read_document" in result["data"]["error_detail"]

    @pytest.mark.asyncio
    async def test_invalid_path_format(self):
        """测试无效路径格式"""
        result = await read_media_file("")

        assert result["llm_data"]["status"]["exec_code"] == "error"

    @pytest.mark.asyncio
    async def test_permission_denied(self, temp_dir):
        """测试权限拒绝（模拟）"""
        file_path = temp_dir / "no_permission.png"
        file_path.write_bytes(b'\x89PNG')

        # 模拟权限错误
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = await read_media_file(str(file_path))

            assert result["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 5. 安全性测试
# ============================================================

class TestReadMediaFileSecurity:
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
            result = await read_media_file(path)
            # 路径验证或文件系统操作会失败
            has_error = (result["llm_data"]["status"]["exec_code"] == "error" or 
                        result.get("data", {}).get("error_detail") is not None)
            assert has_error

    @pytest.mark.asyncio
    async def test_path_validation_called(self, temp_dir):
        """测试路径验证被正确调用"""
        file_path = temp_dir / "validation_test.png"
        file_path.write_bytes(b'\x89PNG')

        with patch("app.tools.file.read_media_file._validate_path") as mock_validate:
            mock_validate.return_value = (False, "路径不允许访问")
            result = await read_media_file(str(file_path))

            assert result["llm_data"]["status"]["exec_code"] == "error"
            assert "路径不允许访问" in result["data"]["error_detail"]
            mock_validate.assert_called_once_with(str(file_path))

    @pytest.mark.asyncio
    async def test_file_size_limit_enforced(self, temp_dir):
        """测试文件大小限制被强制执行"""
        file_path = temp_dir / "oversized.png"
        # 创建一个超过限制的文件
        content = b'\x89PNG' + b'\x00' * (MAX_MEDIA_READ_SIZE + 1)
        file_path.write_bytes(content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "error"
        assert "媒体文件过大" in result["data"]["error_detail"]


# ============================================================
# 6. Base64编码测试
# ============================================================

class TestReadMediaFileBase64:
    """Base64编码测试"""

    @pytest.mark.asyncio
    async def test_base64_encoding_correctness(self, temp_dir):
        """测试Base64编码正确性"""
        file_path = temp_dir / "b64_test.png"
        original_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        file_path.write_bytes(original_content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证base64编码正确
        expected_b64 = base64.b64encode(original_content).decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64

    @pytest.mark.asyncio
    async def test_base64_encoding_with_binary_data(self, temp_dir):
        """测试二进制数据的Base64编码"""
        file_path = temp_dir / "binary_test.png"
        # 创建包含各种字节值的二进制数据
        original_content = bytes(range(256)) * 10
        file_path.write_bytes(original_content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证base64编码正确
        expected_b64 = base64.b64encode(original_content).decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64

    @pytest.mark.asyncio
    async def test_base64_encoding_empty_file(self, temp_dir):
        """测试空文件的Base64编码"""
        file_path = temp_dir / "empty_b64.png"
        file_path.write_bytes(b'')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["base64_data"] == ""

    @pytest.mark.asyncio
    async def test_base64_encoding_large_file(self, temp_dir):
        """测试大文件的Base64编码"""
        file_path = temp_dir / "large_b64.png"
        # 创建一个1MB的文件
        original_content = b'\x89PNG' + b'\x00' * (1024 * 1024)
        file_path.write_bytes(original_content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        # 验证base64编码正确
        expected_b64 = base64.b64encode(original_content).decode('utf-8')
        assert result["data"]["base64_data"] == expected_b64


# ============================================================
# 7. LLM Data构建测试
# ============================================================

class TestReadMediaFileLLMData:
    """LLM Data构建测试"""

    def test_build_success_llm_data(self):
        """测试成功响应的LLM Data构建"""
        llm_data = _build_read_media_file_llm_data(
            "success", 100,
            file_path="test.png",
            file_name="test.png",
            mime_type="image/png",
            file_size=1024,
        )

        assert llm_data["status"]["exec_code"] == "success"
        assert "test.png" in llm_data["summary"]
        assert "image/png" in llm_data["summary"]
        assert llm_data["duration_ms"] == 100
        assert llm_data["metrics"]["file_size"]["value"] == 1024

    def test_build_error_llm_data(self):
        """测试错误响应的LLM Data构建"""
        llm_data = _build_read_media_file_llm_data(
            "error", 50,
            file_path="test.png",
            detail="读取失败",
        )

        assert llm_data["status"]["exec_code"] == "error"
        assert "读取失败" in llm_data["summary"]
        assert llm_data["duration_ms"] == 50
        assert "读取失败" in llm_data["status"]["detail"]


# ============================================================
# 8. 辅助函数测试
# ============================================================

class TestReadMediaFileHelpers:
    """辅助函数测试"""

    def test_validate_path_valid(self, temp_dir):
        """测试有效路径验证"""
        file_path = str(temp_dir / "test.png")
        is_valid, error_msg = _validate_path(file_path)
        assert is_valid is True
        assert error_msg is None


# ============================================================
# 9. 并发测试
# ============================================================

class TestReadMediaFileConcurrency:
    """并发测试"""

    @pytest.mark.asyncio
    async def test_concurrent_reads_different_files(self, temp_dir):
        """测试并发读取不同文件"""
        files = []
        for i in range(5):
            file_path = temp_dir / f"concurrent_{i}.png"
            file_path.write_bytes(b'\x89PNG' + str(i).encode())
            files.append(file_path)

        tasks = [read_media_file(str(f)) for f in files]
        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for i, result in enumerate(results):
            assert result["llm_data"]["status"]["exec_code"] == "success"
            assert result["data"]["file_name"] == f"concurrent_{i}.png"

    @pytest.mark.asyncio
    async def test_concurrent_reads_same_file(self, sample_image_file):
        """测试并发读取同一文件"""
        tasks = [read_media_file(str(sample_image_file)) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # 所有结果都应该成功
        for result in results:
            assert result["llm_data"]["status"]["exec_code"] == "success"
            assert result["data"]["file_name"] == "sample.png"


# ============================================================
# 10. 性能测试
# ============================================================

class TestReadMediaFilePerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_read_time_measurement(self, sample_image_file):
        """测试读取时间测量"""
        result = await read_media_file(str(sample_image_file))

        assert "duration_ms" in result["llm_data"]
        assert result["llm_data"]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_large_file_read_performance(self, temp_dir):
        """测试大文件读取性能"""
        file_path = temp_dir / "perf_test.png"
        # 创建一个1MB的文件
        content = b'\x89PNG' + b'\x00' * (1024 * 1024)
        file_path.write_bytes(content)

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["llm_data"]["duration_ms"] < 5000  # 应该在5秒内完成


# ============================================================
# 11. 文件类型扩展名测试
# ============================================================

class TestReadMediaFileExtensions:
    """文件类型扩展名测试"""

    @pytest.mark.asyncio
    async def test_webp_extension(self, temp_dir):
        """测试WebP扩展名"""
        file_path = temp_dir / "test.webp"
        file_path.write_bytes(b'RIFF\x00\x00\x00\x00WEBPVP8 ')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "image/webp"

    @pytest.mark.asyncio
    async def test_svg_extension(self, temp_dir):
        """测试SVG扩展名"""
        file_path = temp_dir / "test.svg"
        file_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "image/svg+xml"

    @pytest.mark.asyncio
    async def test_ogg_extension(self, temp_dir):
        """测试OGG扩展名"""
        file_path = temp_dir / "test.ogg"
        file_path.write_bytes(b'OggS\x00\x02\x00\x00')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "audio/ogg"

    @pytest.mark.asyncio
    async def test_flac_extension(self, temp_dir):
        """测试FLAC扩展名"""
        file_path = temp_dir / "test.flac"
        file_path.write_bytes(b'fLaC\x00\x00\x00\x22')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "audio/flac"

    @pytest.mark.asyncio
    async def test_avi_extension(self, temp_dir):
        """测试AVI扩展名"""
        file_path = temp_dir / "test.avi"
        file_path.write_bytes(b'RIFF\x00\x00\x00\x00AVI ')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "video/x-msvideo"

    @pytest.mark.asyncio
    async def test_mkv_extension(self, temp_dir):
        """测试MKV扩展名"""
        file_path = temp_dir / "test.mkv"
        file_path.write_bytes(b'\x1a\x45\xdf\xa3\x00\x00\x00\x00')

        result = await read_media_file(str(file_path))

        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert result["data"]["mime_type"] == "video/x-matroska"


# ============================================================
# 12. 集成测试
# ============================================================

class TestReadMediaFileIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_read_after_write_image(self, temp_dir):
        """测试写入图片后读取"""
        from app.tools.file.write_text_file import write_text_file
        from app.services.context_vars import _current_task_id

        file_path = temp_dir / "integration_image.png"
        # 创建一个简单的PNG文件
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'

        # 使用write_text_file写入（虽然不推荐，但可以测试）
        # 实际应该直接写入二进制文件
        token = _current_task_id.set("test_task_integration")
        try:
            # 直接写入二进制文件
            file_path.write_bytes(png_content)

            # 读取文件
            read_result = await read_media_file(str(file_path))
            assert read_result["llm_data"]["status"]["exec_code"] == "success"
            assert read_result["data"]["file_name"] == "integration_image.png"
            assert read_result["data"]["mime_type"] == "image/png"
        finally:
            _current_task_id.reset(token)

    @pytest.mark.asyncio
    async def test_multiple_media_types(self, temp_dir):
        """测试读取多种媒体类型"""
        files = [
            ("test.png", b'\x89PNG', "image/png"),
            ("test.jpg", b'\xff\xd8\xff', "image/jpeg"),
            ("test.mp3", b'\xff\xfb', "audio/mpeg"),
            ("test.mp4", b'\x00\x00\x00\x1c', "video/mp4"),
        ]

        for filename, content, expected_mime in files:
            file_path = temp_dir / filename
            file_path.write_bytes(content)

            result = await read_media_file(str(file_path))
            assert result["llm_data"]["status"]["exec_code"] == "success"
            assert result["data"]["mime_type"] == expected_mime
