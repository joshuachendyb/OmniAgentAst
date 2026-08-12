# -*- coding: utf-8 -*-
"""shell observation 行×列回归测试 — 小欧 2026-07-20
# 2026-08-03 小欧 测试对齐 07-20 重构: 截断时 ⚠ 已截断在倒2行、截断情况行在末行;
#           tool 层 _truncated 分支已移除(_truncated 字段被忽略), 显示域行×列统一收口

验证 execute_shell_command(章6.4) 落地后:
1. Tool 输出零限制(stdout/stderr 全量返回, 无 SHELL_OUTPUT_MAX_CHARS 截断)
2. observation_formatter._format_shell_result 行×列(200行/1000字符)+ 两态说明行
"""
import os

import pytest

from app.services.agent import observation_formatter as of
from app.tools.fundamental import execute_shell_command as esc


def _llm(returncode=0):
    return {"metrics": {"exit_code": {"value": returncode}}}


def test_shell_format_non_truncated():
    """小输出: 全量保留 + 末行 ✓ 无截断-完整"""
    stdout = "\n".join("line%d payload" % i for i in range(50))
    stderr = "\n".join("err%d warn" % i for i in range(10))
    out = of._format_shell_result(
        {"stdout": stdout, "stderr": stderr, "shell_type": "ps7", "duration_ms": 123},
        _llm(),
    )
    assert out.endswith("✓ 无截断-完整"), out[-30:]
    assert stdout in out, "stdout 应全量保留"
    assert "⚠ err0 warn" in out, "stderr 应带 ⚠ 前缀"


def test_shell_format_truncated():
    """超 200 行: body 截断到 200 行 + ⚠ 已截断(倒2) + 截断情况行(末行)"""
    big = "\n".join("line%d " % i + ("x" * 1500) for i in range(300))
    out = of._format_shell_result(
        {"stdout": big, "stderr": "", "shell_type": "cmd", "duration_ms": 9},
        _llm(),
    )
    lines = out.split("\n")
    assert lines[-2] == "⚠ 已截断", lines[-2]
    assert "保留200行" in lines[-1], lines[-1]
    assert "截断 %d 行" % (300 - 200) in lines[-1]
    body = lines[:-2]
    assert len(body) == 200, "body 应截断到 200 行, 实际 %d" % len(body)


def test_shell_format_no_tool_truncated_branch():
    """07-20 重构后无 tool 层 _truncated 分支: _truncated 字段被忽略, 仅按显示域行×列收口"""
    data = {"stdout": "some output", "stderr": "", "_truncated": True}
    out = of._format_shell_result(data, _llm())
    assert "some output" in out
    assert "⚠ 输出已截断" not in out, "tool 层截断标记已移除"
    assert out.endswith("✓ 无截断-完整"), out[-30:]


def test_shell_format_overwide_single_line():
    """单行超宽: 截到 1000 字符, 不触发行截断, 仍 ✓ 无截断-完整"""
    one = "A" * 5000
    out = of._format_shell_result(
        {"stdout": one, "stderr": "", "shell_type": "pwsh", "duration_ms": 5},
        _llm(),
    )
    assert out.endswith("✓ 无截断-完整"), out[-30:]
    assert "A" * 1000 in out and "A" * 1001 not in out, "超宽应截到 1000"


def test_shell_tool_no_output_truncation():
    """Tool 层去除 SHELL_OUTPUT_MAX_CHARS 运行期引用(历史注释可保留)"""
    src = open(os.path.join(os.path.dirname(esc.__file__), "execute_shell_command.py"), encoding="utf-8").read()
    # 仅检查非注释代码行(历史注释中的提及允许保留)
    code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    assert "SHELL_OUTPUT_MAX_CHARS" not in "\n".join(code_lines), "运行期代码体仍残留 SHELL_OUTPUT_MAX_CHARS"


