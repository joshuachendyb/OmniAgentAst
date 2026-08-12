# -*- coding: utf-8 -*-
# 编辑历史: 2026-08-11 小欧 test_skip_safety_when_disabled改名test_unregistered_tool_blocked_even_when_disabled:
#   生产2026-08-04/08-11重构"未注册工具前置统一拒绝"先于安全开关分流(L106-111), 即使开关关闭未注册工具也blocked(进化, 防伪装绕过)
"""test"""
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.services.safety.tool_safety_checker import ToolSafetyChecker
from app.tools.tool_types import ToolCategory
from app.tools.registry import ToolMetadata


# 鈹查鈹查鈹查 F5-01: security.enabled=false 跳过检查?鈹查鈹查鈹查

@patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=True)
def test_unregistered_tool_blocked_even_when_disabled(mock_skip):
    """未注册工具前置拒绝: 即使安全开关关闭也blocked(防伪装绕过)"""
    checker = ToolSafetyChecker()
    result = checker.check_before_execute("non_existent_tool", {})
    assert result.blocked, "未注册工具即使开关关闭也应blocked"
    assert result.safety_level == "dangerous"


# 鈹查鈹查鈹查 F5-03: 路径瓒婃潈,?.,夎 blocked 鈹查鈹查鈹查

@patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False)
def test_path_traversal_blocked(mock_skip):
    """path traversal blocked"""
    from app.tools.registry import tool_registry

    meta = ToolMetadata(name="readtext", description="read", category=ToolCategory.FILE, needs_confirmation=False)

    with patch.object(tool_registry, "get_tool", return_value=meta), \
         patch.object(tool_registry, "get_categories", return_value={ToolCategory.FILE: ["readtext"], ToolCategory.SHELL: []}):
        checker = ToolSafetyChecker()
        result = checker.check_before_execute("readtext", {"path": "../../etc/passwd"})
        assert result.blocked, "路径瓒婃潈应该blocked"
        assert "路径瓒婃潈" in result.message or ".." in result.message


# 鈹查鈹查鈹查 F5-04: 否堟硶路径通过检查?鈹查鈹查鈹查

@patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False)
def test_valid_path_passes(mock_skip):
    """valid path passes"""
    from app.tools.registry import tool_registry
    import tempfile

    meta = ToolMetadata(name="readtext", description="read", category=ToolCategory.FILE, needs_confirmation=False)

    valid_path = os.path.join(tempfile.gettempdir(), "test_f5_04.txt").replace("\\", "/")
    Path(valid_path).write_text("test", encoding="utf-8")
    try:
        with patch.object(tool_registry, "get_tool", return_value=meta), \
             patch.object(tool_registry, "get_categories", return_value={ToolCategory.FILE: ["readtext"], ToolCategory.SHELL: []}):
            checker = ToolSafetyChecker()
            result = checker.check_before_execute("readtext", {"path": valid_path})
            assert not result.blocked, f"否堟硶路径搴旈查过繃, 消息={result.message}"
    finally:
        try:
            os.remove(valid_path)
        except OSError:
            pass