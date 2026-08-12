# -*- coding: utf-8 -*-
# 测试 observation_formatter 对 readmedia 结果(仅元数据 + base64 字符数摘要)的渲染
# 对齐: 门限治理规范 doc 章13.4(用户裁定 base64 非可读文本, 不按文本行×列处理)
# 小欧 2026-07-20 新增(本地验证用, 不提交)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.agent.observation_formatter import (
    _format_readmedia_result,
    format_data_detail,
)


def _llm(tool="readmedia", path="/tmp/a.png"):
    return {"action": {"tool": tool, "target": path, "params": {}}}


def _data(b64, name="a.png", mime="image/png", size=None):
    return {"file_name": name, "mime_type": mime,
            "file_size": size if size is not None else len(b64), "base64_data": b64}


def test_metadata_summary():
    """小样本: 仅元数据 + base64 字符数, 不展开 base64, 无行×列/两态"""
    b64 = "A" * 500
    out = _format_readmedia_result(_data(b64), _llm())
    assert "a.png [image/png, 500 bytes] [base64: 500 chars]" in out
    assert "── 媒体文件" not in out
    assert "⚠ 已截断" not in out


def test_large_base64_no_dump():
    """超大 base64: 仍仅字符数摘要, 不按行×列展开, 无截断标记"""
    b64 = "A" * (10_000_000)
    out = _format_readmedia_result(_data(b64), _llm())
    assert "[base64: 10000000 chars]" in out
    assert "⚠ 已截断" not in out
    # base64 原文不应出现在输出中(避免爆 token)
    assert b64[:50] not in out


def test_dispatch_readmedia_via_format_data_detail():
    """经 format_data_detail 命中 readmedia 专属 handler(#13 分流)"""
    b64 = "B" * 300
    out = format_data_detail(_data(b64), _llm(tool="readmedia"))
    assert "a.png [image/png, 300 bytes] [base64: 300 chars]" in out


def test_empty_base64():
    """无 base64: 仅元数据, 不出现 [base64: ...]"""
    out = _format_readmedia_result({"file_name": "x.jpg", "mime_type": "image/jpeg", "file_size": 0}, _llm())
    assert "x.jpg [image/jpeg, 0 bytes]" in out
    assert "[base64:" not in out


def test_metadata_header():
    """头部含文件名/类型/字节数"""
    b64 = "C" * 100
    out = _format_readmedia_result(_data(b64, name="photo.jpg", mime="image/jpeg", size=1234), _llm())
    assert "photo.jpg [image/jpeg, 1234 bytes] [base64: 100 chars]" in out
