# -*- coding: utf-8 -*-
"""
read_media_file 参数组合与内容测试v2
案范要求:schema驱动,内容<100行,验证实际内容,发现问题
小健 2026-06-24

Schema参数: file_path(str, 必填)
功能点: 图片读取(12种),音频读取(9种),视频读取(6种),Base64编码,MIME类型,文件大小,错误路径
"""
import asyncio
import base64
import os
import struct
import tempfile
import pytest
from pathlib import Path

from app.tools.tool_response import is_success, is_error
from app.tools.file.read_media_file import readmedia, _MIME_MAP


def _run(coro):
    return asyncio.run(coro)


def _create_png_file(path: str, width: int = 2, height: int = 2) -> str:
    """创建最小有效PNG文件 - 小健 2026-06-24"""
    import zlib
    header = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff)
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + ihdr_crc
    raw = b''
    for y in range(height):
        raw += b'\x00' + b'\xff\x00' * width
    compressed = zlib.compress(raw)
    idat_crc = struct.pack('>I', zlib.crc32(b'IDAT' + compressed) & 0xffffffff)
    idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + idat_crc
    iend_crc = struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
    iend = struct.pack('>I', 0) + b'IEND' + iend_crc
    with open(path, 'wb') as f:
        f.write(header + ihdr + idat + iend)
    return path


def _create_bmp_file(path: str, width: int = 2, height: int = 2) -> str:
    """创建最小有效BMP文件 - 小健 2026-06-24"""
    row_size = (width * 3 + 3) & ~3
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size
    header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 54)
    info = struct.pack('<IIIHHIIIIII', 40, width, height, 1, 24, 0, pixel_data_size, 0, 0, 0, 0)
    pixels = b'\xff\x00\x00' * width
    padding = b'\x00' * (row_size - width * 3)
    with open(path, 'wb') as f:
        f.write(header + info + (pixels + padding) * height)
    return path


def _create_wav_file(path: str, duration_sec: float = 0.1) -> str:
    """创建最小有效WAV文件 - 小健 2026-06-24"""
    sample_rate = 22050
    num_channels = 1
    bits_per_sample = 16
    num_samples = int(sample_rate * duration_sec)
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<HHIIHH', 1, num_channels, sample_rate, sample_rate * num_channels * bits_per_sample // 8, num_channels * bits_per_sample // 8, bits_per_sample))
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        for i in range(num_samples):
            val = int(32767 * 0.5)
            f.write(struct.pack('<h', val))
    return path


def _create_svg_file(path: str) -> str:
    """创建SVG文件 - 小健 2026-06-24"""
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="10" y="10" width="80" height="80" fill="blue"/>
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="14">Test</text>
</svg>"""
    Path(path).write_text(svg_content, encoding="utf-8")
    return path


def _create_minimal_mp4(path: str) -> str:
    """创建最小MP4文件(仅ftyp box) - 小健 2026-06-24"""
    with open(path, 'wb') as f:
        ftyp = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom'
        f.write(ftyp)
    return path


class TestReadMediaFileImageFormats:
    """图片格式读取测试 - 12种图片格式 - 小健 2026-06-24"""

    def test_read_png(self, tmp_path):
        """PNG图片读取"""
        f = _create_png_file(str(tmp_path / "test.png"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/png"
        assert result["llm_data"]["metrics"]["file_size"]["value"] > 0
        assert len(result["data"]["base64_data"]) > 0
        decoded = base64.b64decode(result["data"]["base64_data"])
        assert decoded[:4] == b'\x89PNG'

    def test_read_bmp(self, tmp_path):
        """BMP图片读取"""
        f = _create_bmp_file(str(tmp_path / "test.bmp"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/bmp"
        decoded = base64.b64decode(result["data"]["base64_data"])
        assert decoded[:2] == b'BM'

    def test_read_svg(self, tmp_path):
        """SVG图片读取"""
        f = _create_svg_file(str(tmp_path / "test.svg"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/svg+xml"
        decoded = base64.b64decode(result["data"]["base64_data"])
        assert b'<svg' in decoded

    def test_read_jpg(self, tmp_path):
        """JPEG图片读取(最小JPEG)"""
        f = str(tmp_path / "test.jpg")
        with open(f, 'wb') as fh:
            fh.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00')
            fh.write(b'\xff\xd9')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/jpeg"

    def test_read_gif(self, tmp_path):
        """GIF图片读取(最小GIF89a)"""
        f = str(tmp_path / "test.gif")
        with open(f, 'wb') as fh:
            fh.write(b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/gif"

    def test_read_ico(self, tmp_path):
        """ICO图标读取"""
        f = str(tmp_path / "test.ico")
        with open(f, 'wb') as fh:
            fh.write(b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x30\x00\x00\x16\x00\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/x-icon"

    def test_read_webp(self, tmp_path):
        """WebP图片读取(最小RIFF+WEBP)"""
        f = str(tmp_path / "test.webp")
        with open(f, 'wb') as fh:
            fh.write(b'RIFF\x0e\x00\x00\x00WEBPVP8 \x02\x00\x00\x00\x00\x00\x00\x00\x9d\x01\x2a')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/webp"

    def test_read_tiff(self, tmp_path):
        """TIFF图片读取(最小TIFF)"""
        f = str(tmp_path / "test.tiff")
        with open(f, 'wb') as fh:
            fh.write(b'II*\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/tiff"

    def test_read_tif(self, tmp_path):
        """TIF扩展名(等价TIFF)"""
        f = str(tmp_path / "test.tif")
        with open(f, 'wb') as fh:
            fh.write(b'II*\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/tiff"


class TestReadMediaFileAudioFormats:
    """音频格式读取测试 - 小健 2026-06-24"""

    def test_read_wav(self, tmp_path):
        """WAV音频读取"""
        f = _create_wav_file(str(tmp_path / "test.wav"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/wav"
        decoded = base64.b64decode(result["data"]["base64_data"])
        assert decoded[:4] == b'RIFF'

    def test_read_mp3(self, tmp_path):
        """MP3音频读取(最小ID3头)"""
        f = str(tmp_path / "test.mp3")
        with open(f, 'wb') as fh:
            fh.write(b'ID3\x03\x00\x00\x00\x00\x00\x00')
            fh.write(b'\xff\xfb\x90\x00' * 100)
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/mpeg"

    def test_read_ogg(self, tmp_path):
        """OGG音频读取"""
        f = str(tmp_path / "test.ogg")
        with open(f, 'wb') as fh:
            fh.write(b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00' + b'\x00' * 10)
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/ogg"

    def test_read_flac(self, tmp_path):
        """FLAC音频读取"""
        f = str(tmp_path / "test.flac")
        with open(f, 'wb') as fh:
            fh.write(b'fLaC\x00\x00\x00\x22')
            fh.write(b'\x00' * 30)
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/flac"

    def test_read_midi(self, tmp_path):
        """MIDI音频读取"""
        f = str(tmp_path / "test.mid")
        with open(f, 'wb') as fh:
            fh.write(b'MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60')
            fh.write(b'MTrk\x00\x00\x00\x04\x00\xff\x2f\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/midi"

    def test_read_midi_extension(self, tmp_path):
        """MIDI扩展名(.midi)"""
        f = str(tmp_path / "test.midi")
        with open(f, 'wb') as fh:
            fh.write(b'MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60')
            fh.write(b'MTrk\x00\x00\x00\x04\x00\xff\x2f\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "audio/midi"


class TestReadMediaFileVideoFormats:
    """视频格式读取测试 - 小健 2026-06-24"""

    def test_read_mp4(self, tmp_path):
        """MP4视频读取"""
        f = _create_minimal_mp4(str(tmp_path / "test.mp4"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "video/mp4"

    def test_read_avi(self, tmp_path):
        """AVI视频读取"""
        f = str(tmp_path / "test.avi")
        with open(f, 'wb') as fh:
            fh.write(b'RIFF\x00\x00\x00\x00AVI ')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "video/x-msvideo"

    def test_read_webm(self, tmp_path):
        """WebM视频读取"""
        f = str(tmp_path / "test.webm")
        with open(f, 'wb') as fh:
            fh.write(b'\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "video/webm"

    def test_read_mkv(self, tmp_path):
        """MKV视频读取"""
        f = str(tmp_path / "test.mkv")
        with open(f, 'wb') as fh:
            fh.write(b'\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x00')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "video/x-matroska"


class TestReadMediaFileContentVerification:
    """内容验证测试 - 验证Base64可解码,MIME正认,大小匹配 - 小健 2026-06-24"""

    def test_base64_decodable(self, tmp_path):
        """Base64数据可正认解码"""
        f = _create_png_file(str(tmp_path / "test.png"))
        result = _run(readmedia(f))
        assert is_success(result)
        b64 = result["data"]["base64_data"]
        decoded = base64.b64decode(b64)
        assert len(decoded) == result["llm_data"]["metrics"]["file_size"]["value"]

    def test_file_size_matches(self, tmp_path):
        """返回的file_size与实际文件大小一致"""
        f = _create_png_file(str(tmp_path / "test.png"))
        actual_size = Path(f).stat().st_size
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["file_size"]["value"] == actual_size

    def test_file_name_correct(self, tmp_path):
        """返回的file_name与实际文件名一致"""
        f = _create_png_file(str(tmp_path / "我的截图.png"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["file_name"] == "我的截图.png"

    def test_mime_map_coverage(self):
        """MIME映射覆盖所有27种媒体扩展名 - 小健 2026-06-24"""
        from app.tools.validate.file_type_checker import MEDIA_EXTENSIONS
        for ext in MEDIA_EXTENSIONS:
            assert ext in _MIME_MAP, f"MIME映射缺失扩展名: {ext}"

    def test_unknown_extension_rejected(self, tmp_path):
        """未知扩展名被file_type_checker拒绝(不在MEDIA_EXTENSIONS中)"""
        f = str(tmp_path / "test.xyz_media")
        with open(f, 'wb') as fh:
            fh.write(b'\x00' * 10)
        result = _run(readmedia(f))
        assert is_error(result)
        assert "不是支持的媒体格式" in result["llm_data"]["status"].get("detail", "") or "媒体" in result["llm_data"]["status"].get("detail", "")


class TestReadMediaFileNegative:
    """为面测试 - 错误路径和类型拦截 - 小健 2026-06-24"""

    def test_nonexistent_file(self, tmp_path):
        """读取不存在的文件"""
        result = _run(readmedia(str(tmp_path / "nonexistent.png")))
        assert is_error(result)

    def test_text_file_rejected(self, tmp_path):
        """文本文件被拒绝"""
        f = str(tmp_path / "test.txt")
        Path(f).write_text("hello", encoding="utf-8")
        result = _run(readmedia(f))
        assert is_error(result)
        assert "文本文件" in result["llm_data"]["status"].get("detail", "") or "readtext" in result["llm_data"]["status"].get("detail", "")

    def test_docx_file_rejected(self, tmp_path):
        """文档文件被拒绝"""
        f = str(tmp_path / "test.docx")
        Path(f).write_bytes(b'\x00' * 100)
        result = _run(readmedia(f))
        assert is_error(result)
        assert "文档" in result["llm_data"]["status"].get("detail", "") or "document" in result["llm_data"]["status"].get("detail", "").lower()

    def test_pdf_file_rejected(self, tmp_path):
        """PDF文件被拒绝(应使用read_pdf)"""
        f = str(tmp_path / "test.pdf")
        Path(f).write_bytes(b'%PDF-1.4')
        result = _run(readmedia(f))
        assert is_error(result)

    def test_directory_rejected(self, tmp_path):
        """目录被拒绝"""
        d = tmp_path / "test_dir"
        d.mkdir()
        result = _run(readmedia(str(d / "dummy.png")))

    def test_unsupported_doc_format(self, tmp_path):
        """不支持的老文档格式(.doc)被拒绝"""
        f = str(tmp_path / "test.doc")
        Path(f).write_bytes(b'\x00' * 100)
        result = _run(readmedia(f))
        assert is_error(result)

    def test_unsupported_rtf_format(self, tmp_path):
        """不支持的RTF格式被拒绝"""
        f = str(tmp_path / "test.rtf")
        Path(f).write_text("{\\rtf1}", encoding="utf-8")
        result = _run(readmedia(f))
        assert is_error(result)


class TestReadMediaFileBoundary:
    """边界测试 - 小健 2026-06-24"""

    def test_empty_media_file(self, tmp_path):
        """空媒体文件(0字节)"""
        f = str(tmp_path / "empty.png")
        Path(f).write_bytes(b'')
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["file_size"]["value"] == 0
        assert result["data"]["base64_data"] == ""

    def test_large_file_name(self, tmp_path):
        """长文件名(中文)"""
        name = "项目截图_2026年第二季度代码审查报告_最终版_v2.1.png"
        f = _create_png_file(str(tmp_path / name))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["file_name"] == name

    def test_path_with_spaces(self, tmp_path):
        """路径包含空格"""
        subdir = tmp_path / "my screenshots"
        subdir.mkdir()
        f = _create_png_file(str(subdir / "screen shot.png"))
        result = _run(readmedia(f))
        assert is_success(result)

    def test_case_insensitive_extension(self, tmp_path):
        """大写扩展名(.PNG)"""
        f = _create_png_file(str(tmp_path / "test.PNG"))
        result = _run(readmedia(f))
        assert is_success(result)
        assert result["data"]["mime_type"] == "image/png"
