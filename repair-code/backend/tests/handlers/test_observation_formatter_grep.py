# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-03 小欧 测试对齐 07-20 observation_formatter 重构: _format_matches 单参(matches), 无 tool 层 _truncated 分支;
#            截断两态(⚠ 已截断 + 截断情况行 / ✓ 无截断-完整), 单行超宽用 [:max_chars] 直接截断(无 ...(截断) 标记);
#            context 命中行样式为 "  >  file:line: [matched] content"
from app.services.agent import observation_formatter as of

from app.tools.tool_constants import OBS_GREP_MAX_ROWS, OBS_GREP_MAX_ROW_CHARS


def _match(file, line, content, matched=None, before=None, after=None):
    m = {"file": file, "line": line, "content": content}
    m["matched"] = matched or [content]
    if before:
        m["before"] = before
    if after:
        m["after"] = after
    return m


def test_grep_format_non_truncated():
    """小样本: 全量保留 + 末行 ✓ 无截断-完整"""
    ms = [_match("f%d.py" % i, i, "x") for i in range(50)]
    out = of._format_matches(ms)
    assert out.endswith("✓ 无截断-完整"), out[-40:]
    assert "f0.py" in out and "f49.py" in out


def test_grep_format_truncated():
    """超 200 条: 截断到 OBS_GREP_MAX_ROWS + ⚠ 已截断 + 截断情况行"""
    ms = [_match("f%d.py" % i, i, "x") for i in range(300)]
    out = of._format_matches(ms)
    lines = out.split("\n")
    assert lines[-2] == "⚠ 已截断", lines[-2]
    assert "保留%d行" % OBS_GREP_MAX_ROWS in lines[-1], lines[-1]
    assert "截断 %d 行" % (300 - OBS_GREP_MAX_ROWS) in lines[-1]


def test_grep_format_no_tool_truncated_branch():
    """07-20 重构后无 tool 层 _truncated 分支: 小样本不受 _truncated 字段影响, 仅按显示域收口"""
    ms = [_match("f%d.py" % i, i, "x") for i in range(50)]
    out = of._format_matches(ms)
    assert out.endswith("✓ 无截断-完整"), out[-40:]
    assert "tool 层截断" not in out


def test_grep_format_dual_truncated():
    """双重触发(数量超 + 内容超宽): 截断到行数上限 + 超宽计数计入截断情况行"""
    ms = [_match("f%d.py" % i, i, "x" * (OBS_GREP_MAX_ROW_CHARS + 100)) for i in range(300)]
    out = of._format_matches(ms)
    lines = out.split("\n")
    assert lines[-2] == "⚠ 已截断", lines[-2]
    assert "保留%d行" % OBS_GREP_MAX_ROWS in lines[-1]
    assert "超宽" in lines[-1]


def test_grep_format_overwide_content():
    """单行 content 超 OBS_GREP_MAX_ROW_CHARS: 按 [:max_chars] 直接截断, 不追加 ...(截断) 标记"""
    long = "x" * (OBS_GREP_MAX_ROW_CHARS + 100)
    ms = [_match("f.py", 1, long)]
    out = of._format_matches(ms)
    assert out.endswith("✓ 无截断-完整"), out[-40:]
    assert len(out) < len(long) + 100, "输出应被截断"
    assert "...(截断)" not in out, "新版单行截断无 ...(截断) 标记"


def test_grep_format_empty():
    """空 matches 返回空字符串"""
    assert of._format_matches([]) == ""


def test_grep_format_context_lines():
    """带 before/after 上下文行: 命中行带 > 标记, 上下文行在其前后"""
    ctx = [{"line": i, "text": "ctx %d" % i} for i in range(3)]
    ms = [_match("f.py", 5, "main()", before=ctx, after=ctx)]
    out = of._format_matches(ms)
    assert out.endswith("✓ 无截断-完整"), out[-40:]
    assert ">  f.py:5: [main()]" in out, out
    for i in range(3):
        assert "ctx %d" % i in out


def test_grep_format_context_overwide():
    """上下文 text 超 OBS_GREP_MAX_ROW_CHARS: 按 [:max_chars] 直接截断"""
    long = "x" * (OBS_GREP_MAX_ROW_CHARS + 50)
    ctx = [{"line": 1, "text": long}]
    ms = [_match("f.py", 5, "main()", before=ctx)]
    out = of._format_matches(ms)
    assert long not in out
    assert out.endswith("✓ 无截断-完整"), out[-40:]
