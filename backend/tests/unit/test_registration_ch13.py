# -*- coding: utf-8 -*-
"""
13.1 注册验证测试 — 分类完整性 & 工具计数
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.1节
验证内容:
  1. ToolCategory 枚举包含正确分类
  2. 全量注册无错误
  3. 各分类工具数量合理
  4. 按 Category+action 规则注册（desktop/system统一入口）

注意:
  - 本测试直接调用 ensure_tools_registered() 触发全量注册
  - 使用 reset_registered_state() 隔离测试环境
  - 工具计数验证当前代码状态
"""

import pytest
from app.services.tools import (
    ToolRegistry, ToolCategory, get_registered_tools, get_tool,
    ensure_tools_registered, reset_registered_state,
    _registered_categories,
)


# ============================================================
# 辅助
# ============================================================
@pytest.fixture(autouse=True)
def reset_tools():
    """每次测试前重置注册状态"""
    reset_registered_state()
    yield
    reset_registered_state()


# ============================================================
# TestToolCategory — 枚举完整性
# ============================================================
class TestToolCategory:
    """验证 ToolCategory 枚举"""

    def test_category_values(self):
        """所有分类必须存在"""
        assert ToolCategory.FILE.value == "file"
        assert ToolCategory.TIME.value == "time"
        assert ToolCategory.SHELL.value == "shell"
        assert ToolCategory.NETWORK.value == "network"
        assert ToolCategory.ENVIRONMENT.value == "environment"
        assert ToolCategory.SYSTEM.value == "system"
        assert ToolCategory.DATABASE.value == "database"
        assert ToolCategory.DESKTOP.value == "desktop"
        assert ToolCategory.DOCUMENT.value == "document"
        assert ToolCategory.SUPPORT_TOOL.value == "support_tool"
        assert ToolCategory.DATA_FORMAT.value == "data_format"
        assert ToolCategory.CODE_EXECUTION.value == "code_execution"

    def test_category_registration_no_error(self):
        """全量注册必须成功"""
        # 确保不会重复调用
        reset_registered_state()
        from app.services.tools import ensure_tools_registered
        try:
            ensure_tools_registered()
        except Exception as e:
            pytest.fail(f"全量注册失败: {e}")


# ============================================================
# TestRegistrationCount — 各分类工具计数验证
# ============================================================
class TestRegistrationCount:
    """
    验证各分类注册的工具数量

    注意: 计数基于当前代码实现, 会随 Phase 2 精简而变化
    """

    def get_tools_by_category(self, category: ToolCategory):
        """按分类获取已注册工具"""
        all_tools = get_registered_tools()
        return [
            t for t in all_tools
            if hasattr(t, "category") and t.category == category
        ]

    def test_file_tools_count(self):
        from app.services.tools import _CATEGORY_MODULES
        assert "file" in _CATEGORY_MODULES
        tools = self.get_tools_by_category(ToolCategory.FILE)
        assert len(tools) > 0

    def test_time_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.TIME)
        assert len(tools) > 0

    def test_shell_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.SHELL)
        assert len(tools) > 0

    def test_network_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.NETWORK)
        assert len(tools) > 0

    def test_environment_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.ENVIRONMENT)
        assert len(tools) > 0

    def test_system_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.SYSTEM)
        assert len(tools) > 0

    def test_database_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.DATABASE)
        assert len(tools) > 0

    def test_desktop_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.DESKTOP)
        assert len(tools) > 0

    def test_document_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.DOCUMENT)
        assert len(tools) > 0

    def test_support_tool_count(self):
        tools = self.get_tools_by_category(ToolCategory.SUPPORT_TOOL)
        assert len(tools) > 0

    def test_data_format_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.DATA_FORMAT)
        assert len(tools) > 0

    def test_code_execution_tools_count(self):
        tools = self.get_tools_by_category(ToolCategory.CODE_EXECUTION)
        assert len(tools) > 0

    def test_total_tools_exist(self):
        """验证总工具数合理"""
        all_tools = get_registered_tools()
        assert len(all_tools) >= 80
        assert len(all_tools) <= 160


# ============================================================
# TestDuplicateRegistration — 防重复注册
# ============================================================
class TestDuplicateRegistration:
    """验证重复调用 ensure_tools_registered 不会产生重复工具"""

    def test_idempotent_registration(self):
        from app.services.tools import (
            ensure_tools_registered as reg,
            reset_registered_state as reset,
        )
        reset()
        reg()
        count1 = len(get_registered_tools())
        reg()  # 第二次调用
        count2 = len(get_registered_tools())
        assert count1 == count2, f"重复注册导致工具数变化: {count1} → {count2}"

    def test_reset_re_register(self):
        """重置后重新注册应得到相同数量的工具"""
        from app.services.tools import (
            ensure_tools_registered as reg,
            reset_registered_state as reset,
        )
        reset()
        reg()
        count1 = len(get_registered_tools())
        reset()
        reg()
        count2 = len(get_registered_tools())
        assert count1 == count2


# ============================================================
# TestToolByName — 关键工具名验证
# ============================================================
class TestToolByName:
    """验证关键工具可通过名称查找"""

    def test_get_tool_by_name_exists(self):
        existing_tools = [
            "get_current_time", "read_file", "list_directory",
            "execute_command", "http_request", "query_sql",
        ]
        for name in existing_tools:
            tool = get_tool(name)
            assert tool is not None, f"工具 '{name}' 未注册"
