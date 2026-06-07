"""
Agent跨工具Prompt测试

TDD: 验证Agent system prompt包含跨工具提示
Author: 小沈 - 2026-04-30
"""
import pytest
from app.services.tools.registry import tool_registry, ToolCategory


CROSS_TOOL_HINT_FILE = (
    "除了文件操作工具，你还可以使用其他分类的工具"
)
CROSS_TOOL_HINT_TIME = (
    "除了时间日期工具，你还可以使用其他分类的工具"
)


class TestCrossToolPrompt:
    """验证跨工具提示功能"""

    def setup_method(self):
        # 确保至少有一个分类注册
        from app.services.tools import ensure_tools_registered
        ensure_tools_registered()

    def test_get_tools_summary_returns_string(self):
        """_get_tools_summary 返回非空字符串"""
        summary = tool_registry.get_all_tools_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50

    def test_summary_contains_at_least_one_category(self):
        """概要至少包含一个分类"""
        summary = tool_registry.get_all_tools_summary()
        assert "【" in summary and "】" in summary

    def test_cross_tool_hint_text_defined(self):
        """跨工具提示文本已定义"""
        assert CROSS_TOOL_HINT_FILE is not None
        assert CROSS_TOOL_HINT_TIME is not None
        assert len(CROSS_TOOL_HINT_FILE) > 10
        assert len(CROSS_TOOL_HINT_TIME) > 10

    def test_summary_with_priority_system(self):
        """priority_category=SYSTEM时系统排在FILE前面"""
        summary = tool_registry.get_all_tools_summary(priority_category=ToolCategory.SYSTEM)
        system_pos = summary.index("【系统/环境工具】")
        file_pos = summary.index("【文件操作工具】")
        assert system_pos < file_pos, "SYSTEM应在FILE之前"

    def test_summary_with_priority_network(self):
        """priority_category=NETWORK时网络排在FILE前面"""
        summary = tool_registry.get_all_tools_summary(priority_category=ToolCategory.NETWORK)
        network_pos = summary.index("【网络通信工具】")
        file_pos = summary.index("【文件操作工具】")
        assert network_pos < file_pos, "NETWORK应在FILE之前"
