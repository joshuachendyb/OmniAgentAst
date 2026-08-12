# -*- coding: utf-8 -*-
# 测试 observation_formatter 对 read_xlsx 结果(表格预览)的专属 #25 行×列截断 + 两态说明
# 对齐: 门限治理规范 doc 章15 / 章11 readtext / 章12 edittext / 章13 readmedia / 章14 writetext 测试
# 小欧 2026-07-20 新增(本地验证用, 不提交)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.agent.observation_formatter import (
    _format_xlsx_result,
    format_data_detail,
)


def _llm(tool="read_xlsx", path="/tmp/a.xlsx"):
    return {"action": {"tool": tool, "target": path, "params": {}}}


def test_small_no_truncate():
    """小表格: 全量 + 末行 ✓ 无截断-完整; 含表头"""
    data = {"headers": ["name", "age"], "rows": [["Alice", 30], ["Bob", 25]]}
    out = _format_xlsx_result(data, _llm())
    assert "── xlsx 表格预览 ── /tmp/a.xlsx" in out
    assert "name | age" in out
    assert "Alice | 30" in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_full_rows_no_format_truncation():
    """超 200 行(read_xlsx 无 offset): 显示域不截断, 全量展示, 无 '还有 N 行'"""
    rows = [["r%d" % i, i] for i in range(250)]
    data = {"headers": ["c1", "c2"], "rows": rows}
    out = _format_xlsx_result(data, _llm())
    assert "还有" not in out
    assert "...(截断)" not in out
    # 全量行都在(含最后一行)
    assert "r249" in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_no_row_char_truncation():
    """单行超宽(read_xlsx 无 offset): 显示域列不截断, 完整展示, 无 ...(截断)"""
    wide = "x" * 3000
    data = {"headers": ["c1"], "rows": [[wide]]}
    out = _format_xlsx_result(data, _llm())
    assert "...(截断)" not in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_tool_truncated_flag():
    """Tool 层置 data[truncated]=True(OUTLIMIT 触发): 显示 ⚠ 已截断 + 原因"""
    data = {"headers": ["c1"], "rows": [["a"], ["b"]], "truncated": True,
            "truncated_reason": "行数超1000"}
    out = _format_xlsx_result(data, _llm())
    assert "⚠ 已截断" in out
    assert "行数超1000" in out
    assert "✓ 无截断-完整" not in out


def test_empty_table():
    """空表(无 headers/rows): 给占位提示, 不抛异常"""
    out = _format_xlsx_result({"headers": [], "rows": []}, _llm())
    assert "(空表或无数据)" in out


def test_dispatch_read_xlsx_via_format_data_detail():
    """经 format_data_detail 命中 #25 专属 handler(action.tool==read_xlsx 且 headers+rows)"""
    data = {"headers": ["name", "age"], "rows": [["Alice", 30]]}
    out = format_data_detail(data, _llm(tool="read_xlsx"))
    assert "── xlsx 表格预览 ── /tmp/a.xlsx" in out
    assert "name | age" in out
    assert "✓ 无截断-完整" in out


def test_dispatch_not_catch_other_headers_rows():
    """非 read_xlsx 的 headers+rows 不应命中 #25(走 #2b _format_table 旧样式, 不含专属标题)"""
    data = {"headers": ["name"], "rows": [["Alice"]]}
    out = format_data_detail(data, _llm(tool="some_other_tool"))
    assert "── xlsx 表格预览" not in out
