# -*- coding: utf-8 -*-
"""find observation 行×列回归测试 — 小欧 2026-07-20

验证 search_files(find, 章7.4) 落地后:
1. Tool 输出零限制(返回全部匹配, 无 MAX_SEARCH_RESULTS 收集上限 / FIND_PAGE_SIZE 分页 / max_depth 递归限制)
2. observation_formatter._format_find_results 行×列(200行/300字符)+ 两态说明行
"""
import asyncio
import os
import tempfile

import pytest

from app.services.agent import observation_formatter as of
from app.tools.file import search_files as sf
from app.tools.tool_constants import OBS_FIND_MAX_ROWS, OBS_FIND_MAX_ROW_CHARS


def _matches(n):
    return [{"name": "f%d.txt" % i, "type": "file", "size": 10, "path": "/p/f%d.txt" % i} for i in range(n)]


def test_find_format_non_truncated():
    """小样本: 全量保留 + 末行 ✓ 无截断-完整"""
    out = of._format_find_results(_matches(50))
    assert out.endswith("✓ 无截断-完整"), out[-30:]
    assert "f0.txt" in out and "f49.txt" in out
    assert "... 还有" not in out


def test_find_format_truncated():
    """超 200 项: 截断到 OBS_FIND_MAX_ROWS + ⚠ 已截断 + 明细"""
    out = of._format_find_results(_matches(300))
    lines = out.split("\n")
    assert lines[-1] == "⚠ 已截断", lines[-1]
    assert "还有 100 个匹配项" in lines[-2], lines[-2]
    assert "f199.txt" in out and "f200.txt" not in out


def test_find_format_overwide_path():
    """单行 path 超宽: 截到 OBS_FIND_MAX_ROW_CHARS, 不触发行截断"""
    long_path = "x" * 1000
    out = of._format_find_results([{"name": "a.txt", "type": "file", "size": 1, "path": long_path}])
    assert out.endswith("✓ 无截断-完整"), out[-30:]
    assert "x" * OBS_FIND_MAX_ROW_CHARS in out
    assert "x" * (OBS_FIND_MAX_ROW_CHARS + 1) not in out


def test_find_tool_returns_all_matches():
    """Tool 输出零限制: find 返回全部匹配, 无收集上限/分页/递归深度限制"""
    with tempfile.TemporaryDirectory() as td:
        for i in range(260):
            open(os.path.join(td, "f%d.log" % i), "w").write("x")
        res = asyncio.run(sf.find("*.log", td))
        assert res["llm_data"]["status"]["exec_code"] == "success"
        assert len(res["data"]["matches"]) == 260, "应返回全部匹配(无分页/上限)"


def test_find_tool_no_output_limit_code():
    """运行期代码体不残留 MAX_SEARCH_RESULTS / FIND_PAGE_SIZE / max_depth 分页截断"""
    src = open(sf.__file__, encoding="utf-8").read()
    code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(code_lines)
    assert "MAX_SEARCH_RESULTS" not in body, "运行期仍残留 MAX_SEARCH_RESULTS"
    assert "FIND_PAGE_SIZE" not in body, "运行期仍残留 FIND_PAGE_SIZE"
    assert "max_depth" not in body, "运行期仍残留 max_depth 递归限制"
