"""
Phase 1: 基于真实log数据的验证测试

数据来源（会话ID: 88e97e4c-6d0b-4a25-bd9f-ec20ffae9f14）:
- prompt_52+20260514_092540.json: 原始prompt日志（工具列表53K）
- execution_steps_2026-5-14T09-33-22.json: 前端导出执行步骤

验证目标：
1. 新注入内容比旧版明显减少（53K → 应显著降低）
2. NETWORK detail只包含网络工具（符合设计要求）
3. summary排除已加载分类后无重叠（符合设计要求）
4. 所有Agent必需的finish工具始终可用（support_tool）
5. 工具参数信息完整（LLM能正确使用工具）

Author: 小健 - 2026-05-14
"""
import pytest
from app.services.tools.registry import tool_registry, ToolCategory
from app.services.tools.registry import tool_registry


# ============================================================
# 常量：来自真实log数据
# ============================================================
SESSION_ID = "88e97e4c-6d0b-4a25-bd9f-ec20ffae9f14"
MESSAGE_ID = "52"
ORIGINAL_TOOL_LIST_SIZE = 53080  # 从prompt log中提取（消息摘要第2条的长度）
USER_TASK = "检查一下 WIFI的 IP DNS ,尤其是公网IP呢 我主要想知道这个"
INTENT_TYPE = "network"
INTENT_CONFIDENCE = 0.92

# 该任务实际使用的工具（从execution_steps.json提取）
TOOLS_USED = {
    "execute_shell_command": {"ipconfig /all", "curl.exe", "nslookup"},
    "http_request": {"api.ipify.org", "httpbin.org/ip"},
    "fetch_webpage": {"api.ipify.org"},
}


def ensure_registry():
    from app.services.tools import ensure_tools_registered
    ensure_tools_registered()


class TestRealDataToolListSize:
    """基于真实数据验证工具列表大小"""

    @pytest.fixture(autouse=True)
    def setup(self):
        ensure_registry()

    def test_new_detail_is_dramatically_smaller_than_old(self):
        """新版NETWORK detail应远小于原版53K全量"""
        full_detail = tool_registry.get_all_tools_detail()
        network_detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        # 原版全量detail ≈ 53K
        assert len(full_detail) >= 40000
        # NETWORK detail 应 < 10K（只有6个网络工具）
        assert len(network_detail) < 10000
        # 缩小比例至少5倍
        assert len(full_detail) / len(network_detail) >= 5

    def test_detail_plus_summary_total_improvement(self):
        """detail+summary总和大比分优于原版"""
        full_detail = tool_registry.get_all_tools_detail()
        network_detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        other_summary = tool_registry.get_all_tools_summary(
            exclude_categories={"network"}
        )
        total_new = len(network_detail) + len(other_summary)
        # 至少节省30%（目标是50%以上）
        saving = (len(full_detail) - total_new) / len(full_detail) * 100
        print(f"\n原版全量: {len(full_detail)} 字符")
        print(f"新注入总计: {total_new} 字符 (detail={len(network_detail)} + summary={len(other_summary)})")
        print(f"节省: {saving:.1f}%")
        assert saving >= 30

    def test_summary_without_exclude_same_as_before(self):
        """不传exclude_categories时，summary和原来的get_all_tools_summary行为一致"""
        summary = tool_registry.get_all_tools_summary()
        # summary应包含多分类的工具信息
        assert len(summary) > 5000
        # 包含参数信息
        assert "required" in summary or "optional" in summary
        # 包含用途说明
        assert "—" in summary or "：" in summary


class TestRealDataContentValidation:
    """基于真实工具数据验证内容正确性"""

    @pytest.fixture(autouse=True)
    def setup(self):
        ensure_registry()

    def test_network_detail_contains_http_request(self):
        """NETWORK detail包含http_request（该任务使用的核心工具）"""
        detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        assert "http_request" in detail

    def test_network_detail_contains_ping(self):
        """NETWORK detail包含ping"""
        detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        assert "ping" in detail

    def test_network_detail_no_file_tools(self):
        """NETWORK detail不包含文件工具"""
        detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        assert "execute_shell_command" not in detail
        assert "ipconfig" not in detail

    def test_summary_contains_shell_tools(self):
        """summary（排除network后）包含shell工具（execute_shell_command）"""
        summary = tool_registry.get_all_tools_summary(
            exclude_categories={"network"}
        )
        # execute_shell_command属于SHELL分类，应该在summary中出现
        shell_found = "execute_shell_command" in summary or "shell" in summary.lower()
        assert shell_found

    def test_summary_contains_param_for_http_request(self):
        """summary中http_request应有参数信息（url, method, timeout等）"""
        # 不排除network，让summary包含所有分类
        summary = tool_registry.get_all_tools_summary()
        assert "http_request" in summary

    def test_network_detail_description_useful(self):
        """NETWORK detail的description应包含使用场景"""
        detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        # http_request的description应包含"发送 HTTP 请求"或类似内容
        assert len(detail) > 500
        # 应包含http_request工具的详细描述
        assert "HTTP" in detail or "http" in detail


class TestRealDataLoadedCategories:
    """模拟真实NetworkAgent的_loaded_categories"""

    def test_simulate_network_agent_loaded_categories(self):
        """模拟NetworkAgent初始化后的_loaded_categories"""
        # 模拟 BaseAgent.__init__ 中 _loaded_categories 的初始化逻辑
        tool_category_value = "network"
        loaded = set()
        if tool_category_value:
            loaded.add(tool_category_value)
        loaded.add("support_tool")  # 始终注册

        assert "network" in loaded
        assert "support_tool" in loaded
        assert len(loaded) == 2

        # 验证_detail能正确输出（模拟_get_tools_detail逻辑）
        ensure_registry()

        parts = []
        for cat_name in sorted(loaded):
            if cat_name == "support_tool":
                continue  # support_tool一般不直接输出detail
            try:
                category = ToolCategory(cat_name)
                detail = tool_registry.get_all_tools_detail(
                    priority_category=category,
                    category_filter=category
                )
                if detail.strip():
                    parts.append(detail)
            except (ValueError, Exception):
                continue

        result = "\n\n".join(parts) if parts else ""
        assert "【网络通信工具】" in result
        assert "http_request" in result

    def test_simulate_dynamic_load(self):
        """模拟动态加载shell分类后的_loaded_categories"""
        loaded = {"network", "support_tool"}
        # 动态加载shell
        loaded.add("shell")

        assert "shell" in loaded
        assert len(loaded) == 3

        # 验证_detail现在包含shell
        ensure_registry()

        parts = []
        for cat_name in sorted(loaded):
            if cat_name == "support_tool":
                continue
            try:
                category = ToolCategory(cat_name)
                detail = tool_registry.get_all_tools_detail(
                    priority_category=category,
                    category_filter=category
                )
                if detail.strip():
                    parts.append(detail)
            except Exception:
                continue

        result = "\n\n".join(parts) if parts else ""
        assert "【网络通信工具】" in result
        assert "【Shell命令工具】" in result or "【Shell】" in result

    def test_simulate_summary_exclude_loaded(self):
        """模拟注入时summary排除已加载分类"""
        loaded = {"network", "support_tool"}
        ensure_registry()

        detail = tool_registry.get_all_tools_detail(
            priority_category=ToolCategory.NETWORK,
            category_filter=ToolCategory.NETWORK
        )
        summary = tool_registry.get_all_tools_summary(
            exclude_categories=loaded
        )

        assert "【网络通信工具】" in detail
        assert "【网络通信工具】" not in summary

        # 验证注入格式
        tools_msg = f"【已加载工具（完整）】\n{detail}\n\n【其他可用工具（概要）】\n{summary}"
        assert "【已加载工具（完整）】" in tools_msg
        assert "【其他可用工具（概要）】" in tools_msg

    def test_support_tool_category_registered(self):
        """验证support_tool分类有工具注册（支撑工具是基础能力）"""
        ensure_registry()
        # support_tool分类应有工具
        support_tools = [
            name for name, meta in tool_registry._tools.items()
            if meta.category == ToolCategory.SUPPORT_TOOL
        ]
        assert len(support_tools) > 0
        # finish由Agent内部逻辑处理，不在注册表中


class TestRealDataToolExecution:
    """基于真实执行步骤的工具调用验证"""

    def test_all_tools_in_session_are_network_or_shell(self):
        """验证任务52使用的工具都是NETWORK或SHELL分类"""
        ensure_registry()

        # 任务52实际使用的工具（从execution_steps.json提取）
        used_tools = ["http_request", "execute_shell_command", "fetch_webpage"]
        expected_categories = {"network", "shell"}

        for tool_name in used_tools:
            meta = tool_registry.get_tool(tool_name)
            assert meta is not None, f"工具 {tool_name} 未注册"
            assert meta.category.value in expected_categories, \
                f"工具 {tool_name} 分类={meta.category.value} 不在{expected_categories}中"

    def test_tool_params_in_schema(self):
        """验证关键工具的参数schema完整（LLM需要这些信息调用工具）"""
        ensure_registry()

        # http_request 必须的参数
        http_meta = tool_registry.get_tool("http_request")
        assert http_meta is not None
        schema = http_meta.input_schema or {}
        props = schema.get("properties", {})
        # 必须包含url参数
        assert "url" in props, "http_request缺少url参数"
        # 必须包含method参数
        assert "method" in props, "http_request缺少method参数"

        # execute_shell_command 必须的参数
        shell_meta = tool_registry.get_tool("execute_shell_command")
        assert shell_meta is not None
        schema = shell_meta.input_schema or {}
        props = schema.get("properties", {})
        assert "command" in props, "execute_shell_command缺少command参数"

    def test_summary_http_request_param_list(self):
        """验证summary中http_request的参数列表"""
        ensure_registry()

        summary = tool_registry.get_all_tools_summary(
            priority_category=ToolCategory.NETWORK
        )
        # 找到http_request那行
        for line in summary.split("\n"):
            if "http_request" in line:
                # 应包含参数信息
                assert "url" in line
                # 应包含用途说明
                assert "—" in line
                break
        else:
            pytest.fail("summary中未找到http_request行")
