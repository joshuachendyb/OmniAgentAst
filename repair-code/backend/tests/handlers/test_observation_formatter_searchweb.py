# -*- coding: utf-8 -*-
"""searchweb observation 行×列回归测试 — 小欧 2026-07-20

验证 searchweb(章8.4) 落地后:
1. Tool 输出零限制(snippet 完整返回, 无 SEARCH_SNIPPET_MAX_CHARS 截断, 3.7)
2. observation_formatter._format_items 行×列(OBS_SEARCHWEB_MAX_ROWS=100行 / OBS_SEARCHWEB_MAX_ROW_CHARS=500字符)+ 两态说明行
"""
import pytest

from app.services.agent import observation_formatter as of
from app.tools.tool_constants import OBS_SEARCHWEB_MAX_ROWS, OBS_SEARCHWEB_MAX_ROW_CHARS


def _items(n, desc_len=20):
    return [{"name": "r%d" % i, "desc": "d%d" % i, "url": "https://e.com/%d" % i} for i in range(n)]


def test_searchweb_format_non_truncated():
    """小样本: 全量保留 + 末行 ✓ 无截断-完整"""
    out = of._format_items(_items(50))
    assert out.endswith("✓ 无截断-完整"), out[-30:]
    assert "r0" in out and "r49" in out
    assert "... 还有" not in out


def test_searchweb_format_truncated_rows():
    """超 100 项: 截断到 OBS_SEARCHWEB_MAX_ROWS + ⚠ 已截断 + 明细"""
    out = of._format_items(_items(150))
    lines = out.split("\n")
    assert lines[-1] == "⚠ 已截断", lines[-1]
    assert "还有 50 项" in lines[-2], lines[-2]
    assert "r99" in out and "r100" not in out


def test_searchweb_format_overwide_desc():
    """超长 desc: 截断到 OBS_SEARCHWEB_MAX_ROW_CHARS + ...(截断)"""
    long_desc = "A" * (OBS_SEARCHWEB_MAX_ROW_CHARS + 100)
    out = of._format_items([{"name": "t", "desc": long_desc, "url": "https://e.com/t"}])
    assert "A" * OBS_SEARCHWEB_MAX_ROW_CHARS + "...(截断)" in out
    assert "URL: https://e.com/t" in out


def test_searchweb_format_url_preserved():
    """有 desc + 有 url → URL 附在 desc 下方一行(门限治理前修复的行为不退化)"""
    out = of._format_items([{"name": "p", "desc": "描述", "url": "https://e.com/p"}])
    assert "URL: https://e.com/p" in out
    assert "描述" in out


def test_searchweb_format_empty():
    """空列表 → 空字符串"""
    assert of._format_items([]) == ""
