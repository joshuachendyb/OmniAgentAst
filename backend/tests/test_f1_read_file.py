# -*- coding: utf-8 -*-
"""F1 read_file 深度测试 — 小沈 2026-05-19

注意：read_file 返回结果经过 _to_unified_format 包装，
实际数据在 result["data"] 中。
"""

import pytest
import tempfile
from pathlib import Path


def _make_file(content: str, suffix: str = ".txt") -> str:
    path = Path(tempfile.mktemp(suffix=suffix))
    path.write_text(content, encoding="utf-8")
    return str(path)


def _make_gbk_file(content: str) -> str:
    path = Path(tempfile.mktemp(suffix=".txt"))
    path.write_bytes(content.encode("gbk"))
    return str(path)


def _ok(d: dict) -> dict:
    """获取 _to_unified_format 包装后的 data 字段"""
    return d.get("data", d)


# ============================================================
# 1. 基本功能测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_single_full():
    """F1-001: 单文件全部读取"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("line1\nline2\nline3\n")
    result = await ft.read_file(file_paths=[path])
    data = _ok(result)
    assert data["success"] is True, f"失败: {data.get('error')}"
    assert data["content"] == "line1\nline2\nline3\n"
    assert data["total_lines"] == 3
    assert data["line_count"] == 3


@pytest.mark.asyncio
async def test_read_file_single_head():
    """F1-002: 单文件取前N行"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\nc\nd\ne\n")
    result = await ft.read_file(file_paths=[path], head=2)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 2
    assert "a\nb\n" in data["content"]


@pytest.mark.asyncio
async def test_read_file_single_tail():
    """F1-003: 单文件取后N行"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\nc\nd\ne\n")
    result = await ft.read_file(file_paths=[path], tail=2)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 2


@pytest.mark.asyncio
async def test_read_file_single_offset_limit():
    """F1-004: 单文件offset+limit分页"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("L1\nL2\nL3\nL4\nL5\n")
    result = await ft.read_file(file_paths=[path], offset=2, limit=2)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 2
    assert "L2\nL3\n" in data["content"]
    assert data["start_line"] == 2
    assert data["end_line"] == 3


# ============================================================
# 2. 编码测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_utf8():
    """F1-005: UTF-8文件正常读取"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("你好世界\nHello World\n")
    result = await ft.read_file(file_paths=[path])
    data = _ok(result)
    assert data["success"] is True
    assert "你好世界" in data["content"]


@pytest.mark.asyncio
async def test_read_file_gbk_auto_detect():
    """F1-006: GBK文件自动编码检测"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_gbk_file("你好世界\nGBK测试\n")
    result = await ft.read_file(file_paths=[path])
    data = _ok(result)
    assert data["success"] is True
    assert "你好世界" in data["content"]
    assert data["encoding"] == "gbk"


@pytest.mark.asyncio
async def test_read_file_specified_encoding():
    """F1-007: 指定编码读取"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_gbk_file("GBK内容\n")
    result = await ft.read_file(file_paths=[path], encoding="gbk")
    data = _ok(result)
    assert data["success"] is True
    assert "GBK内容" in data["content"]


# ============================================================
# 3. 异常场景测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_not_found():
    """F1-008: 文件不存在"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_file(file_paths=["Z:/nonexistent_file_xyz.txt"])
    data = _ok(result)
    assert data["success"] is False
    assert data.get("content") is None


@pytest.mark.asyncio
async def test_read_file_binary():
    """F1-009: 二进制文件被拒绝"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = Path(tempfile.mktemp(suffix=".png"))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    result = await ft.read_file(file_paths=[str(path)])
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_read_file_path_not_file():
    """F1-010: 路径是目录而非文件"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    dirpath = tempfile.mkdtemp()
    result = await ft.read_file(file_paths=[dirpath])
    data = _ok(result)
    assert data["success"] is False


# ============================================================
# 4. P17互斥校验测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_empty_paths():
    """F1-011: file_paths空列表被拒绝"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_file(file_paths=[])
    data = _ok(result)
    assert data["success"] is False
    assert "为空" in data.get("error", "") or "至少" in data.get("error", "")


@pytest.mark.asyncio
async def test_read_file_mutual_exclusion_head_and_tail():
    """F1-012: head和tail互斥"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\nc\n")
    result = await ft.read_file(file_paths=[path], head=1, tail=1)
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_read_file_mutual_exclusion_head_and_offset():
    """F1-013: head/tail与offset/limit互斥"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\nc\n")
    result = await ft.read_file(file_paths=[path], head=1, offset=1)
    data = _ok(result)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_read_file_neither_path_nor_paths():
    """F1-014: file_paths为空列表被拒绝"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_file(file_paths=[])
    data = _ok(result)
    assert data["success"] is False


# ============================================================
# 5. 批量模式测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_batch_multiple():
    """F1-015: 批量读取多个文件"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    p1 = _make_file("content1\n")
    p2 = _make_file("content2\n")
    result = await ft.read_file(file_paths=[p1, p2])
    data = _ok(result)
    assert data["success"] is True
    assert data["total"] == 2
    assert data["success_count"] == 2


@pytest.mark.asyncio
async def test_read_file_batch_empty_list():
    """F1-016: 空列表被拒绝"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    result = await ft.read_file(file_paths=[])
    data = _ok(result)
    assert data["success"] is False


# ============================================================
# 6. 边界测试
# ============================================================

@pytest.mark.asyncio
async def test_read_file_empty_file():
    """F1-017: 读取空文件"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("")
    result = await ft.read_file(file_paths=[path])
    data = _ok(result)
    assert data["success"] is True


@pytest.mark.asyncio
async def test_read_file_head_exceeds_lines():
    """F1-018: head超过总行数"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\n")
    result = await ft.read_file(file_paths=[path], head=100)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 2


@pytest.mark.asyncio
async def test_read_file_tail_exceeds_lines():
    """F1-019: tail超过总行数返回全部"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\n")
    result = await ft.read_file(file_paths=[path], tail=100)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 2


@pytest.mark.asyncio
async def test_read_file_offset_exceeds_lines():
    """F1-020: offset超过总行数返回空"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("a\nb\n")
    result = await ft.read_file(file_paths=[path], offset=100)
    data = _ok(result)
    assert data["success"] is True
    assert data["line_count"] == 0


@pytest.mark.asyncio
async def test_read_file_capabilities():
    """F1-021: 验证capabilities_used字段"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("test\n")
    result = await ft.read_file(file_paths=[path])
    data = _ok(result)
    assert "capabilities_used" in data
    assert "文件IO" in data["capabilities_used"]


@pytest.mark.asyncio
async def test_read_file_next_actions():
    """F1-022: 验证next_actions注入"""
    from app.services.tools.file.file_tools import FileTools
    ft = FileTools()
    path = _make_file("test\n")
    result = await ft.read_file(file_paths=[path])
    assert result["status"] == "success"
    assert "next_actions" in result
