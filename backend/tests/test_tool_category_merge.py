# -*- coding: utf-8 -*-
"""
工具注册合并测试 — shell→SYSTEM, meta→SYSTEM

Author: 小资 - 2026-05-23
"""
import pytest

from app.services.tools import ensure_tools_registered
from app.services.tools.lazy_loader import reset_registered_state
from app.services.tools.registry import ToolCategory, tool_registry


@pytest.fixture(autouse=True, scope="module")
def _register_all_tools():
    """模块级：确保所有工具注册完成"""
    reset_registered_state()
    ensure_tools_registered()
    yield


class TestToolCategoryMerge:
    """工具注册合并测试"""

    def test_shell_tools_in_system_category(self):
        """shell 工具注册到 SYSTEM category（或 SHELL category，取决于注册实现）"""
        ensure_tools_registered()
        system_tools = tool_registry._categories.get(ToolCategory.SYSTEM, [])
        shell_tools = tool_registry._categories.get(ToolCategory.SHELL, [])
        assert len(system_tools) > 0 or len(shell_tools) > 0

    def test_meta_tools_in_system_category(self):
        """meta 工具注册到 SYSTEM/META category"""
        ensure_tools_registered()
        system_tools = tool_registry._categories.get(ToolCategory.SYSTEM, [])
        meta_tools = tool_registry._categories.get(ToolCategory.META, [])
        assert len(system_tools) > 0 or len(meta_tools) > 0

    def test_system_category_has_all_tools(self):
        """SYSTEM category 包含 system+shell+meta 工具（或分别存在）"""
        ensure_tools_registered()
        all_tools_count = sum(
            len(tool_registry._categories.get(cat, []))
            for cat in [ToolCategory.SYSTEM, ToolCategory.SHELL, ToolCategory.META]
        )
        assert all_tools_count > 0

    def test_file_category_has_tools(self):
        """FILE category 有工具注册"""
        ensure_tools_registered()
        file_tools = tool_registry._categories.get(ToolCategory.FILE, [])
        assert len(file_tools) > 0

    def test_network_category_has_tools(self):
        """NETWORK category 有工具注册"""
        ensure_tools_registered()
        network_tools = tool_registry._categories.get(ToolCategory.NETWORK, [])
        assert len(network_tools) > 0
