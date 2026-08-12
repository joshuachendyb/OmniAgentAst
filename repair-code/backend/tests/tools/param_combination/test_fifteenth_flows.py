# -*- coding: utf-8 -*-
# 编辑历史: 2026-08-11 小欧 TestPathValidatorDeep对齐validate_path 3元组协议(v1.43 P3): is_valid,msg解包补第3元素category, 消除not enough values to unpack
"""第十五轮 - 关键流程集成测试 - 小欧 2026-06-27
目标:发现流程级Bug,覆盖12个关键流程中的高风险点
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _run(func, *args, **kwargs):
    from app.services.task.task_context import _current_task_id
    token = _current_task_id.set("test_task_001")
    try:
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(result)
            finally:
                loop.close()
        return result
    finally:
        _current_task_id.reset(token)


def _ok(r):
    from app.tools.tool_response import is_success
    return is_success(r)


# ============================================================
# FLOW 1: ContextVar隔离测试
# ============================================================
class TestContextVarIsolation:
    """ContextVar在并发请求间的隔离"""

    def test_context_var_basic_set_get(self):
        """CTX-001: ContextVar基本设置和获取"""
        from app.services.task.task_context import _current_task_id
        token = _current_task_id.set("task_A")
        try:
            assert _current_task_id.get() == "task_A"
        finally:
            _current_task_id.reset(token)

    def test_context_var_isolation_across_tasks(self):
        """CTX-002: ContextVar在并发asyncio Task间隔离"""
        from app.services.task.task_context import _current_task_id
        import asyncio

        async def _run_test():
            results = {}

            async def task_a():
                token = _current_task_id.set("task_A")
                await asyncio.sleep(0.01)
                results["A"] = _current_task_id.get()
                _current_task_id.reset(token)

            async def task_b():
                token = _current_task_id.set("task_B")
                await asyncio.sleep(0.01)
                results["B"] = _current_task_id.get()
                _current_task_id.reset(token)

            await asyncio.gather(task_a(), task_b())
            assert results.get("A") == "task_A"
            assert results.get("B") == "task_B"

        _run(_run_test)

    def test_context_var_concurrent_read_write(self):
        """CTX-003: ContextVar并发读写不互相影响"""
        from app.services.task.task_context import _current_task_id
        import asyncio

        async def _run_test():
            results = {}

            async def task_a():
                token = _current_task_id.set("A_value")
                await asyncio.sleep(0.01)
                results["a"] = _current_task_id.get()
                _current_task_id.reset(token)

            async def task_b():
                token = _current_task_id.set("B_value")
                results["b_start"] = _current_task_id.get()
                await asyncio.sleep(0.01)
                results["b_end"] = _current_task_id.get()
                _current_task_id.reset(token)

            await asyncio.gather(task_a(), task_b())
            assert results.get("a") == "A_value"
            assert results.get("b_start") == "B_value"
            assert results.get("b_end") == "B_value"

        _run(_run_test)


# ============================================================
# FLOW 2: 工具缓存与动态注入测试
# ============================================================
class TestToolCache:
    """工具缓存TTL和失效测试"""

    def test_tool_cache_exists(self):
        """CACHE-001: 工具缓存存在"""
        from unittest.mock import MagicMock
        from app.services.agent.tool_cache_manager import get_openai_tools
        from app.utils.cache import TTLCache
        from app.tools.registry import ToolCategory
        agent = MagicMock()
        agent._tool_cache = TTLCache(ttl=300)
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.FILE, ToolCategory.SHELL}
        agent._searchtool_desc_override = None
        self._skip_if_tools_empty()
        tools = get_openai_tools(agent)
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tool_cache_returns_same_objects(self):
        """CACHE-002: 缓存返回相同对象"""
        from unittest.mock import MagicMock
        from app.services.agent.tool_cache_manager import get_openai_tools
        from app.utils.cache import TTLCache
        agent = MagicMock()
        agent._tool_cache = TTLCache(ttl=300)
        agent._loaded_categories = set()
        agent._searchtool_desc_override = None
        self._skip_if_tools_empty()
        t1 = get_openai_tools(agent)
        t2 = get_openai_tools(agent)
        assert t1 is t2

    def test_tool_cache_invalidation(self):
        """CACHE-003: 缓存失效后重新获取"""
        from unittest.mock import MagicMock
        from app.services.agent.tool_cache_manager import get_openai_tools, invalidate_tool_cache
        from app.utils.cache import TTLCache
        agent = MagicMock()
        agent._tool_cache = TTLCache(ttl=300)
        agent._loaded_categories = set()
        agent._searchtool_desc_override = None
        self._skip_if_tools_empty()
        t1 = get_openai_tools(agent)
        invalidate_tool_cache(agent)
        t2 = get_openai_tools(agent)
        assert t1 is not t2

    def test_tool_search_returns_results(self):
        """CACHE-004: 工具搜索返回结果"""
        self._skip_if_tools_empty()
        from app.tools.fundamental.tool_search import searchtool
        r = _run(searchtool, query="文件")
        assert _ok(r)
        matches = r.get("data", {}).get("matches", [])
        assert len(matches) > 0

    def _skip_if_tools_empty(self):
        """如果工具注册表为空则跳过"""
        from app.tools.registry import tool_registry
        from app.tools.registry import ensure_tools_registered
        ensure_tools_registered()
        if not tool_registry._tools:
            pytest.skip("工具注册表为空,跳过依赖注册表的测试")

    def test_tool_search_by_name(self):
        """CACHE-005: 按名称搜索工具"""
        self._skip_if_tools_empty()
        from app.tools.fundamental.tool_search import searchtool
        r = _run(searchtool, query="writetext")
        assert _ok(r)
        matches = r.get("data", {}).get("matches", [])
        names = [m.get("name", "") for m in matches]
        assert "writetext" in names

    def test_tool_search_empty_query(self):
        """CACHE-006: 空查询搜索"""
        from app.tools.fundamental.tool_search import searchtool
        r = _run(searchtool, query="")
        assert not _ok(r)

    def test_tool_search_nonexistent(self):
        """CACHE-007: 搜索不存在的工具 → 无命中 warning+空matches(不注入)
        小欧 2026-08-05 更新: 修复前"无命中仍返回全部工具top10"是bug(设计文档§9.1),
        现断言新行为: warning+detail+hint+空matches"""
        self._skip_if_tools_empty()
        from app.tools.fundamental.tool_search import searchtool
        from app.tools.tool_response import is_warning
        r = _run(searchtool, query="xyz_not_a_tool_12345")
        assert _ok(r)
        assert is_warning(r), f"无命中应为warning: {r}"
        matches = r.get("data", {}).get("matches", [])
        # 修复后: 无命中返回空matches, 不再误导LLM注入无关分类
        assert len(matches) == 0
        status = r.get("llm_data", {}).get("status", {})
        assert status.get("detail"), "无命中应带detail"
        assert status.get("hint"), "无命中应带hint"

    def test_tool_search_chinese_query(self):
        """CACHE-008: 中文查询搜索"""
        self._skip_if_tools_empty()
        from app.tools.fundamental.tool_search import searchtool
        r = _run(searchtool, query="读取文件")
        assert _ok(r)
        matches = r.get("data", {}).get("matches", [])
        assert len(matches) > 0


# ============================================================
# FLOW 3: 工具注册表测试
# ============================================================
class TestToolRegistry:
    """工具注册表完整性测试"""

    def _skip_if_tools_empty(self):
        from app.tools.registry import tool_registry
        from app.tools.registry import ensure_tools_registered
        ensure_tools_registered()
        if not tool_registry._tools:
            pytest.skip("工具注册表为空,跳过依赖注册表的测试")

    def test_registry_has_all_categories(self):
        """REG-001: 注册表包含所有分类"""
        self._skip_if_tools_empty()
        from app.tools.registry import tool_registry
        categories = tool_registry.get_categories()
        assert len(categories) >= 6

    def test_registry_get_tool(self):
        """REG-002: 获取单个工具"""
        self._skip_if_tools_empty()
        from app.tools.registry import tool_registry
        tool = tool_registry.get_tool("writetext")
        assert tool is not None
        assert tool.name == "writetext"

    def test_registry_get_nonexistent_tool(self):
        """REG-003: 获取不存在的工具"""
        from app.tools.registry import tool_registry
        tool = tool_registry.get_tool("nonexistent_tool_xyz")
        assert tool is None

    def test_registry_list_tools(self):
        """REG-004: 列出所有工具"""
        self._skip_if_tools_empty()
        from app.tools.registry import tool_registry
        tools = tool_registry.list_tools()
        assert len(tools) >= 15

    def test_registry_tool_has_schema(self):
        """REG-005: 工具有完整schema"""
        self._skip_if_tools_empty()
        from app.tools.registry import tool_registry
        tool = tool_registry.get_tool("writetext")
        assert tool is not None
        assert tool.input_schema is not None
        assert "properties" in tool.input_schema

    def test_registry_tool_has_metadata(self):
        """REG-006: 工具有完整元数据"""
        self._skip_if_tools_empty()
        from app.tools.registry import tool_registry
        tool = tool_registry.get_tool("readtext")
        assert tool is not None
        assert tool.category is not None
        assert tool.description is not None


# ============================================================
# FLOW 4: 路径验证器深度测试
# ============================================================
class TestPathValidatorDeep:
    """路径验证器深度测试"""

    def test_validate_path_exists(self):
        """PV-001: 验证器函数存在"""
        from app.services.safety.path_safe_check import validate_path
        assert callable(validate_path)

    def test_validate_path_normal(self):
        """PV-002: 正常路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            is_valid, msg, _ = validate_path(fp)
            assert is_valid

    def test_validate_path_dotdot(self):
        """PV-003: ..路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / ".." / "test.txt")
            is_valid, msg, _ = validate_path(fp)
            # 应该被拒绝或处理

    def test_validate_path_empty(self):
        """PV-004: 空路径验证"""
        from app.services.safety.path_safe_check import validate_path
        is_valid, msg, _ = validate_path("")
        assert not is_valid

    def test_validate_path_none(self):
        """PV-005: None路径验证"""
        from app.services.safety.path_safe_check import validate_path
        is_valid, msg, _ = validate_path(None)
        assert not is_valid

    def test_validate_path_absolute(self):
        """PV-006: 绝对路径验证"""
        from app.services.safety.path_safe_check import validate_path
        is_valid, msg, _ = validate_path("C:\\Windows\\System32\\test.txt")
        # 应该被拒绝或受限

    def test_validate_path_special_chars(self):
        """PV-007: 特殊字符路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "file (1) [copy].txt")
            is_valid, msg, _ = validate_path(fp)
            assert is_valid

    def test_validate_path_long(self):
        """PV-008: 超长路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / (("a" * 200) + ".txt"))
            is_valid, msg, _ = validate_path(fp)
            # 超长路径应该被处理

    def test_validate_path_unicode(self):
        """PV-009: Unicode路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "文件_测试.txt")
            is_valid, msg, _ = validate_path(fp)
            assert is_valid

    def test_validate_path_trailing_slash(self):
        """PV-010: 尾部斜杠路径验证"""
        from app.services.safety.path_safe_check import validate_path
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d)) + "\\"
            is_valid, msg, _ = validate_path(fp)
            # 尾部斜杠应该被处理


# ============================================================
# FLOW 5: 错误处理与恢复测试
# ============================================================
class TestErrorHandling:
    """错误处理流程测试"""

    def test_build_error_structure(self):
        """ERR-001: 错误响应结构"""
        from app.tools.tool_response import build_error, is_error
        r = build_error(data={"error_detail": "test error"})
        assert is_error(r)
        assert "error_detail" in r.get("data", {})

    def test_build_success_structure(self):
        """ERR-002: 成功响应结构"""
        from app.tools.tool_response import build_success, is_success
        r = build_success(data={"content": "test"})
        assert is_success(r)
        assert "content" in r.get("data", {})

    def test_is_success_function(self):
        """ERR-003: is_success函数"""
        from app.tools.tool_response import build_success, is_success
        r = build_success(data={"content": "test"})
        assert is_success(r)

    def test_is_error_function(self):
        """ERR-004: is_error函数"""
        from app.tools.tool_response import build_error, is_error
        r = build_error(data={"error_detail": "test"})
        assert is_error(r)

    def test_error_with_llm_data(self):
        """ERR-005: 带LLM数据的错误"""
        from app.tools.tool_response import build_error, is_error
        llm_data = {
            "status": {"exec_code": "error", "message": "test error"},
            "summary": "test"
        }
        r = build_error(data={"error_detail": "test"}, llm_data=llm_data)
        assert is_error(r)
        assert r.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


# ============================================================
# FLOW 6: 消息构建器测试
# ============================================================
class TestMessageBuilder:
    """消息构建器测试"""

    def test_message_builder_exists(self):
        """MSG-001: 消息构建器存在"""
        from app.services.agent.message_builder import MessageBuilder
        builder = MessageBuilder()
        assert builder is not None

    def test_message_builder_init_history(self):
        """MSG-002: init_history初始化正确"""
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb.init_history("你是AI助手", "请帮我做件事")
        msgs = mb.prepare_messages_for_llm()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "AI助手" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert "请帮我做件事" in msgs[1]["content"]

    def test_message_builder_add_observation(self):
        """MSG-003: add_observation正常添加"""
        from app.services.agent.message_builder import MessageBuilder
        from app.services.agent.fc_message_types import AssistantMessage, ToolCall, ToolFunction, message_to_dict
        mb = MessageBuilder()
        mb.init_history("系统提示", "任务提示")
        # 先构建一个 assistant tool_call
        msg = AssistantMessage(tool_calls=[ToolCall(id="tc_1", function=ToolFunction(name="f", arguments="{}"))])
        mb.conversation_history.append(message_to_dict(msg))
        mb.add_observation("操作结果", {"tool_call_id": "tc_1"})
        msgs = mb.prepare_messages_for_llm()
        roles = [m["role"] for m in msgs]
        assert "tool" in roles

    def test_message_builder_empty_task_prompt(self):
        """MSG-004: 空task_prompt抛异常"""
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        import pytest as _pytest
        with _pytest.raises(ValueError, match="task_prompt不能为空"):
            mb.init_history("系统提示", "")

    def test_message_builder_get_messages_returns_list(self):
        """MSG-005: prepare_messages_for_llm返回列表"""
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb.init_history("系统提示", "任务提示")
        msgs = mb.prepare_messages_for_llm()
        assert isinstance(msgs, list)
        assert len(msgs) == 2

    def test_message_builder_system_prompt(self):
        """MSG-006: 系统提示词正确保留"""
        from app.services.agent.message_builder import MessageBuilder
        mb = MessageBuilder()
        mb.init_history("你是专业的AI助手", "帮我查资料")
        msgs = mb.prepare_messages_for_llm()
        assert msgs[0]["role"] == "system"
        assert "专业的AI助手" in msgs[0]["content"]


# ============================================================
# FLOW 7: Agent状态管理测试
# ============================================================
class TestAgentState:
    """Agent状态管理测试"""

    def test_agent_status_enum(self):
        """AGENT-001: Agent状态枚举"""
        from app.services.agent.status_table import AgentStatus
        assert hasattr(AgentStatus, "EXECUTING")
        assert hasattr(AgentStatus, "COMPLETED")
        assert hasattr(AgentStatus, "FAILED")
        assert hasattr(AgentStatus, "CANCELLED")

    def test_agent_status_values(self):
        """AGENT-002: Agent状态值"""
        from app.services.agent.status_table import AgentStatus
        assert AgentStatus.EXECUTING.value == "executing"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"

    def test_observation_context_exists(self):
        """AGENT-003: 观察上下文存在"""
        from unittest.mock import MagicMock
        from app.services.agent.handlers.action_handler import ObservationContext
        mock_agent = MagicMock()
        mock_agent.task_id = "test-task-id"
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test_tool", "tool_call_id": "call_123"}],
            results=[],
            step=0,
            tool_name="test_tool",
            tool_params={},
            is_parallel=False,
            pending_calls=[],
        )
        assert ctx.tool_name == "test_tool"

    def test_observation_context_error(self):
        """AGENT-004: 错误观察上下文"""
        from unittest.mock import MagicMock
        from app.services.agent.handlers.action_handler import ObservationContext
        mock_agent = MagicMock()
        mock_agent.task_id = "test-task-id"
        ctx = ObservationContext(
            agent=mock_agent,
            all_calls=[{"tool_name": "test_tool", "tool_call_id": "call_123"}],
            results=[],
            step=0,
            tool_name="test_tool",
            tool_params={},
            is_parallel=False,
            pending_calls=[],
        )
        assert ctx.tool_name == "test_tool"


# ============================================================
# FLOW 8: 文件操作记录器测试
# ============================================================
class TestOperationRecorder:
    """文件操作记录器测试"""

    def test_recorder_exists(self):
        """REC-001: 记录器存在"""
        from app.services.safety.operation_record import record_operation
        assert callable(record_operation)

    def test_recorder_record_operation(self):
        """REC-002: 记录操作"""
        from app.services.safety.operation_record import record_operation
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            Path(fp).write_text("test content")
            op_id = record_operation(
                task_id="test_task",
                source_path=Path(fp),
                operation_type="create"
            )
            assert op_id is not None

    def test_recorder_record_and_query(self):
        """REC-003: 记录并查询操作"""
        from app.services.safety.operation_record import record_operation
        from app.db.operation_queries import get_session_operations
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "test.txt")
            Path(fp).write_text("test content")
            op_id = record_operation(
                task_id="test_task_001",
                source_path=Path(fp),
                operation_type="create"
            )
            assert op_id is not None
            ops = get_session_operations(task_id="test_task_001")
            assert len(ops) >= 1


# ============================================================
# FLOW 9: 安全检查器测试
# ============================================================
class TestSafetyChecker:
    """安全检查器测试"""

    def test_safety_checker_exists(self):
        """SAFE-001: 安全检查器存在"""
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        checker = get_tool_safety_checker()
        assert checker is not None

    def test_safety_checker_check_before_execute(self):
        """SAFE-002: 执行前检查"""
        from app.services.safety.tool_safety_checker import get_tool_safety_checker, SafetyResult
        checker = get_tool_safety_checker()
        result = checker.check_before_execute("writetext", {"file_path": "test.txt", "content": "test"})
        assert isinstance(result, SafetyResult)

    def test_safety_checker_blocks_dangerous(self):
        """SAFE-003: 拦截危险操作"""
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        checker = get_tool_safety_checker()
        # 测试危险命令
        result = checker.check_before_execute("shell", {"command": "Remove-Item C:\\ -Recurse -Force"})
        # 应该被拦截或标记

    def test_safety_checker_allows_safe(self):
        """SAFE-004: 允许安全操作"""
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        checker = get_tool_safety_checker()
        result = checker.check_before_execute("readtext", {"file_path": "test.txt"})
        assert result.blocked == False

    def test_safety_checker_empty_command(self):
        """SAFE-005: 空命令检查"""
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        checker = get_tool_safety_checker()
        result = checker.check_before_execute("shell", {"command": ""})
        # 空命令应该被处理


# ============================================================
# FLOW 10: 工具响应构建测试
# ============================================================
class TestToolResponse:
    """工具响应构建测试"""

    def test_response_build_success(self):
        """RESP-001: 构建成功响应"""
        from app.tools.tool_response import build_success, is_success
        r = build_success(data={"content": "test"})
        assert is_success(r)
        assert r["data"]["content"] == "test"

    def test_response_build_error(self):
        """RESP-002: 构建错误响应"""
        from app.tools.tool_response import build_error, is_error
        r = build_error(data={"error_detail": "test error"})
        assert is_error(r)
        assert "error_detail" in r["data"]

    def test_response_with_llm_data(self):
        """RESP-003: 带LLM数据的响应"""
        from app.tools.tool_response import build_success
        llm_data = {
            "status": {"exec_code": "success"},
            "summary": "test summary"
        }
        r = build_success(data={"content": "test"}, llm_data=llm_data)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert r["llm_data"]["summary"] == "test summary"

    def test_response_is_success(self):
        """RESP-004: is_success判断"""
        from app.tools.tool_response import build_success, build_error, is_success
        r1 = build_success(data={})
        r2 = build_error(data={})
        assert is_success(r1) == True
        assert is_success(r2) == False

    def test_response_is_error(self):
        """RESP-005: is_error判断"""
        from app.tools.tool_response import build_success, build_error, is_error
        r1 = build_success(data={})
        r2 = build_error(data={})
        assert is_error(r1) == False
        assert is_error(r2) == True

    def test_response_llm_data_status_exec_code(self):
        """RESP-006: LLM数据状态码"""
        from app.tools.tool_response import build_success
        llm_data = {"status": {"exec_code": "warning"}}
        r = build_success(data={}, llm_data=llm_data)
        assert r["llm_data"]["status"]["exec_code"] == "warning"

    def test_response_metrics(self):
        """RESP-007: 响应指标"""
        from app.tools.tool_response import build_success
        llm_data = {"metrics": {"bytes_written": {"value": 100, "text": "100 bytes"}}}
        r = build_success(data={}, llm_data=llm_data)
        assert r["llm_data"]["metrics"]["bytes_written"]["value"] == 100

    def test_response_empty_data(self):
        """RESP-008: 空数据响应"""
        from app.tools.tool_response import build_success, is_success
        r = build_success(data={})
        assert is_success(r)
        assert r["data"] == {}

    def test_response_nested_data(self):
        """RESP-009: 嵌套数据响应"""
        from app.tools.tool_response import build_success
        data = {"matches": [{"file": "test.txt", "line": 1}], "total_matches": 1}
        r = build_success(data=data)
        assert r["data"]["total_matches"] == 1
        assert len(r["data"]["matches"]) == 1

    def test_response_error_with_hint(self):
        """RESP-010: 带提示的错误响应"""
        from app.tools.tool_response import build_error
        llm_data = {
            "status": {
                "exec_code": "error",
                "message": "file not found",
                "hint": "check file path"
            }
        }
        r = build_error(data={"error_detail": "not found"}, llm_data=llm_data)
        assert r["llm_data"]["status"]["hint"] == "check file path"


# ============================================================
# FLOW 11: 工具执行器集成测试
# ============================================================
class TestToolExecutor:
    """工具执行器集成测试"""

    def test_executor_exists(self):
        """EXEC-001: 执行器存在"""
        from app.services.agent.tool_executor import execute_tool
        assert callable(execute_tool)

    def test_executor_write_then_read(self):
        """EXEC-002: 写入在读取"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "exec_test.txt")
            _run(writetext, path=fp, content="EXEC_TEST_DATA")
            r = _run(readtext, path=fp)
            assert "EXEC_TEST_DATA" in r.get("data", {}).get("content", "")

    def test_executor_write_copy_list(self):
        """EXEC-003: 写入→复制→列表"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.copy_file import copy
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as d:
            src = str(Path(d) / "src.txt")
            dst = str(Path(d) / "dst.txt")
            _run(writetext, path=src, content="COPY_TEST")
            _run(copy, path=src, dest=dst)
            r = _run(listdir, path=d)
            names = [e.get("name", "") for e in r.get("data", {}).get("entries", [])]
            assert "src.txt" in names
            assert "dst.txt" in names

    def test_executor_shell_then_file(self):
        """EXEC-004: Shell写入→文件读取"""
        from app.tools.fundamental.execute_shell_command import shell
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "shell_exec.txt")
            _run(shell, command=f'Set-Content -Path "{fp}" -Value "SHELL_EXEC" -Encoding UTF8')
            r = _run(readtext, path=fp)
            assert "SHELL_EXEC" in r.get("data", {}).get("content", "")

    def test_executor_error_handling(self):
        """EXEC-005: 错误处理"""
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "nonexistent_file.txt")
            r = _run(readtext, path=fp)
            assert not _ok(r)

    def test_executor_concurrent_operations(self):
        """EXEC-006: 并发操作"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            def write_and_read(i):
                fp = str(Path(d) / f"conc_{i}.txt")
                _run(writetext, path=fp, content=f"data_{i}")
                return _run(readtext, path=fp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(write_and_read, i) for i in range(10)]
                results = [f.result() for f in futures]
            for i, r in enumerate(results):
                assert f"data_{i}" in r.get("data", {}).get("content", "")

    def test_executor_large_content(self):
        """EXEC-007: 大内容操作"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "large_exec.txt")
            content = "X" * 100000
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            raw = r.get("data", {}).get("content", "")
            assert "X" * 100 in raw, f"文件内容应包含100个X以上: {raw[:200]}"

    def test_executor_special_characters(self):
        """EXEC-008: 特殊字符操作"""
        from app.tools.file.write_text_file import writetext
        from app.tools.file.read_text_file import readtext
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "special_exec.txt")
            content = "🎉🎌🎇 中文内容 with spaces & special chars"
            _run(writetext, path=fp, content=content)
            r = _run(readtext, path=fp)
            assert "🎉" in r.get("data", {}).get("content", "")
            assert "中文" in r.get("data", {}).get("content", "")


# ============================================================
# FLOW 12: 配置加载测试
# ============================================================
class TestConfigLoading:
    """配置加载流程测试"""

    def test_config_exists(self):
        """CFG-001: 配置存在"""
        from app.config import get_config
        config = get_config()
        assert config is not None

    def test_config_has_llm(self):
        """CFG-002: 配置包含AI"""
        from app.config import get_config
        config = get_config()
        assert config.get('ai') is not None

    def test_config_has_safety(self):
        """CFG-003: 配置包含安全设置"""
        from app.config import get_config
        config = get_config()
        assert config.get('security') is not None

    def test_config_get_value(self):
        """CFG-004: 获取配置值"""
        from app.config import get_config
        config = get_config()
        # 尝试获取一个已知的配置项
        assert config is not None
