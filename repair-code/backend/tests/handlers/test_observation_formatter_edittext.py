# -*- coding: utf-8 -*-
# 测试 observation_formatter 对 edittext 结果(编辑差异 diff)的行×列截断 + 两态说明
# 对齐: 门限治理规范 doc 章12.4 / 章11 readtext 测试 / 章10 fetchpage 测试
# 小欧 2026-07-20 新增(本地验证用, 不提交)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.agent.observation_formatter import (
    _format_edittext_result,
    format_data_detail,
    OBS_EDITTEXT_MAX_ROWS,
    OBS_EDITTEXT_MAX_ROW_CHARS,
)


def _llm(tool="edittext", path="/tmp/b.txt"):
    return {"action": {"tool": tool, "target": path, "params": {}}}


def test_small_no_truncate():
    """小样本: 全量保留 + 末行 ✓ 无截断-完整"""
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"
    out = _format_edittext_result(diff, _llm())
    assert "── 编辑差异 ── /tmp/b.txt" in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_over_rows_truncated():
    """超 200 行: 截断到 OBS_EDITTEXT_MAX_ROWS + ⚠ 已截断 + 还有 N 行明细"""
    diff = ("+修改行\n" * (OBS_EDITTEXT_MAX_ROWS + 50)).rstrip("\n")
    out = _format_edittext_result(diff, _llm())
    lines = out.split("\n")
    assert lines[-1] == "⚠ 已截断"
    assert f"还有 {50} 行" in out


def test_over_chars_truncated():
    """单行超宽: 截到 OBS_EDITTEXT_MAX_ROW_CHARS + ...(截断) + ⚠ 已截断"""
    diff = "a" * (OBS_EDITTEXT_MAX_ROW_CHARS + 200)
    out = _format_edittext_result(diff, _llm())
    assert "...(截断)" in out
    assert "⚠ 已截断" in out


def test_dispatch_edittext_via_format_data_detail():
    """经 format_data_detail 命中 edittext 专属 handler(#24 分流, 不走 #21 fallback)"""
    diff = ("+内容行\n" * 5)
    out = format_data_detail({"diff": diff}, _llm(tool="edittext"))
    assert "── 编辑差异 ── /tmp/b.txt" in out
    assert "✓ 无截断-完整" in out


def test_empty_diff():
    """空 diff: 头部保留 + (无差异) + ✓ 无截断-完整, 无异常"""
    out = _format_edittext_result("", _llm())
    assert "── 编辑差异" in out
    assert "(无差异)" in out
    assert "✓ 无截断-完整" in out
