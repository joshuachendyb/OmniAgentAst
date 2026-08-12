# -*- coding: utf-8 -*-
# 测试 observation_formatter 对 fetchpage 结果(网页正文)的行×列截断 + 两态说明
# 对齐: 门限治理规范 doc 章10.4 / 章9 httpget 测试
# 小欧 2026-07-20 新增(本地验证用, 不提交)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.agent.observation_formatter import (
    _format_fetchpage_result,
    format_data_detail,
    OBS_FETCHPAGE_MAX_ROWS,
    OBS_FETCHPAGE_MAX_ROW_CHARS,
)


def _llm(tool="fetchpage", url="http://example.com", fmt="markdown"):
    return {"action": {"tool": tool, "target": url, "params": {"extract_format": fmt}}}


def test_small_no_truncate():
    """小样本: 全量保留 + 末行 ✓ 无截断-完整"""
    content = "第一章\n第二章\n第三章\n"
    out = _format_fetchpage_result(content, _llm())
    assert "── 网页正文 ── http://example.com" in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_over_rows_truncated():
    """超 200 行: 截断到 OBS_FETCHPAGE_MAX_ROWS + ⚠ 已截断 + 还有 N 行明细"""
    content = ("行内容\n" * (OBS_FETCHPAGE_MAX_ROWS + 50)).rstrip("\n")
    out = _format_fetchpage_result(content, _llm())
    lines = out.split("\n")
    assert lines[-1] == "⚠ 已截断"
    assert f"还有 {50} 行" in out


def test_over_chars_truncated():
    """单行超宽: 截到 OBS_FETCHPAGE_MAX_ROW_CHARS + ...(截断) + ⚠ 已截断"""
    content = "a" * (OBS_FETCHPAGE_MAX_ROW_CHARS + 200)
    out = _format_fetchpage_result(content, _llm())
    assert "...(截断)" in out
    assert "⚠ 已截断" in out


def test_dispatch_fetchpage_via_format_data_detail():
    """经 format_data_detail 命中 fetchpage 专属 handler(unittest: #2-fetchpage 分流)"""
    content = "网页正文内容行\n" * 5
    out = format_data_detail({"content": content}, _llm(tool="fetchpage"))
    assert "── 网页正文 ── http://example.com" in out
    assert "✓ 无截断-完整" in out


def test_empty_content():
    """空正文: 头部保留 + ✓ 无截断-完整, 无异常"""
    out = _format_fetchpage_result("", _llm())
    assert "── 网页正文" in out
    assert "✓ 无截断-完整" in out
