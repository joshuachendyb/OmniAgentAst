# -*- coding: utf-8 -*-
"""observation_formatter target 为非str(Path)的回归测试 — 欧阳 2026-07-12

对应《问题分析记录-欧阳-2026-07-12.01.md》第七节遗留项:
构造 action.target 为 WindowsPath(或任意非str), 断言 format_llm_observation
不抛 TypeError(object of type 'WindowsPath' has no len())。
根因为文档工具曾把 WindowsPath 写入 action.target, 被 observation_formatter
的 len(target) 截断逻辑踩中崩溃(commit 8946a36da9, 2026-07-10)。
"""

import pytest
from pathlib import Path

from app.services.agent.observation_formatter import format_llm_observation


def _llm_data_with_target(target):
    return {
        "summary": "ok",
        "action": {"tool": "read_xlsx", "tool_zh": "读取Excel", "target": target, "params": {}},
        "status": {"exec_code": "success", "message": "", "code": "", "detail": "", "hint": ""},
        "duration_ms": 10,
        "metrics": {},
    }


def test_target_windows_path_not_crash():
    """回归: action.target 为 WindowsPath 时不得抛 TypeError"""
    target = Path("E:/test_dir/a.xlsx")
    llm_data = _llm_data_with_target(target)
    text = format_llm_observation({"rows": 1}, llm_data)
    assert isinstance(text, str)
    # Windows 上 str(WindowsPath) 为反斜杠, 做斜杠无关比较
    assert str(target).replace("\\", "/") in text.replace("\\", "/")


def test_target_long_path_truncated_no_crash():
    """回归: 超长 Path target 走 >200 截断分支亦不得崩溃"""
    long_path = Path("C:/" + ("a" * 250) + ".xlsx")
    llm_data = _llm_data_with_target(long_path)
    text = format_llm_observation({}, llm_data)
    assert isinstance(text, str)
    assert len(text) > 0


def test_target_none_fallback():
    """target 为 None 时回退为空串, 不崩溃"""
    llm_data = _llm_data_with_target(None)
    text = format_llm_observation({}, llm_data)
    assert isinstance(text, str)


def test_target_str_normal():
    """正常字符串 target 行为不变"""
    llm_data = _llm_data_with_target("E:/test_dir/a.xlsx")
    text = format_llm_observation({}, llm_data)
    assert isinstance(text, str)
    assert "E:/test_dir/a.xlsx" in text
