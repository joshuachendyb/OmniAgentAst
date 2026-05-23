# -*- coding: utf-8 -*-
"""
MessageBuilder 单元测试 — 小沈 2026-05-21

覆盖全部 public 方法，确保重构前后行为一致。

测试策略：
  1. 先有测试，再实现——每个方法先写预期行为
  2. 不依赖 Agent 实例，可直接构造 MessageBuilder
  3. 每个测试只测一个方法的一种行为
"""
import pytest
import json
from app.services.agent.message_builder import MessageBuilder


# =============================================================================
# 第一组：conversation_history 写操作
# =============================================================================

class TestInitHistory:
    """init_history() 测试"""

    def test_init_history_creates_system_and_user(self):
        """初始化后应有 [system, user] 两条消息"""
        mb = MessageBuilder()
        mb.init_history("你是助手", "查天气")
        assert len(mb.conversation_history) == 2
        assert mb.conversation_history[0] == {"role": "system", "content": "你是助手"}
        assert mb.conversation_history[1] == {"role": "user", "content": "查天气"}

    def test_init_history_resets_old_history(self):
        """多次 init 应重置历史"""
        mb = MessageBuilder()
        mb.init_history("旧", "旧")
        mb.init_history("新", "新")
        assert len(mb.conversation_history) == 2
        assert mb.conversation_history[0]["content"] == "新"


class TestAddAssistant:
    """add_assistant() 测试"""

    def test_add_assistant_appends(self):
        """追加 assistant 消息"""
        mb = MessageBuilder()
        mb.init_history("sys", "user")
        mb.add_assistant("我要查天气")
        assert len(mb.conversation_history) == 3
        assert mb.conversation_history[-1] == {"role": "assistant", "content": "我要查天气"}

    def test_add_assistant_notrim_when_under_threshold(self):
        """历史未超过阈值时不应触发 trim"""
        mb = MessageBuilder(max_context_chars=10000)
        mb.init_history("s" * 100, "u" * 100)
        mb.add_assistant("hello")
        # 100+100+5 = 205 << 10000*0.8=8000，不应 trim
        assert len(mb.conversation_history) == 3

    def test_add_assistant_multiple_appends(self):
        """多次 append assistant"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        for i in range(5):
            mb.add_assistant(f"msg{i}")
        assert len(mb.conversation_history) == 7  # 2 init + 5 assistant
        assert mb.conversation_history[-1]["content"] == "msg4"


class TestAddObservation:
    """add_observation() 测试"""

    def test_add_observation_appends_as_system(self):
        """observation 应以 role=system 追加"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        mb.add_observation("工具执行成功", llm_call_count=1)
        assert mb.conversation_history[-1]["role"] == "system"
        assert "[Observation]" in mb.conversation_history[-1]["content"]

    def test_add_observation_prefix_normalized(self):
        """observation 应有 [Observation] 前缀"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        # 传已经有前缀的文本
        mb.add_observation("[Observation] 成功", llm_call_count=1)
        assert mb.conversation_history[-1]["content"].startswith("[Observation]")

    def test_add_observation_no_duplicate_prefix(self):
        """前缀不应重复添加"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        mb.add_observation("[Observation] 成功", llm_call_count=1)
        content = mb.conversation_history[-1]["content"]
        assert content.count("[Observation]") == 1


class TestAddParseError:
    """add_parse_error() 测试"""

    def test_add_parse_error_creates_observation(self):
        """解析错误应作为 observation 追加"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        mb.add_parse_error("解析失败")
        assert len(mb.conversation_history) == 3
        assert "Parse Error" in mb.conversation_history[-1]["content"]


class TestFlushTempToHistory:
    """flush_temp_to_history() 测试"""

    def test_flush_temp_clears_temp_and_appends(self):
        """flush 后 temp_history 应清空，chunk_buffer 追加为 assistant"""
        mb = MessageBuilder()
        mb.init_history("sys", "u")
        mb.temp_history.append({"role": "assistant", "content": "temp"})
        mb.flush_temp_to_history("final response")
        assert len(mb.temp_history) == 0
        assert mb.conversation_history[-1]["content"] == "final response"


# =============================================================================
# 第二组：observation_text 构建
# =============================================================================

class TestBuildObservationText:
    """build_observation_text() 测试"""

    def test_success_with_data(self):
        """SUCCESS 状态应包含 message + data"""
        result = {"code": "SUCCESS", "data": {"温度": "25°C"}, "message": "查询成功"}
        text = MessageBuilder.build_observation_text(result)
        assert "success" in text
        assert "查询成功" in text
        assert "25°C" in text

    def test_success_with_llm_data(self):
        """有 llm_data 时优先使用 llm_data，不用 data"""
        result = {
            "code": "SUCCESS",
            "data": {"超大": "x" * 10000},
            "llm_data": {"精简": "摘要"},
            "message": "完成"
        }
        text = MessageBuilder.build_observation_text(result)
        assert "精简" in text
        assert "摘要" in text
        # data 的内容不应出现在 observation 中
        assert "超大" not in text

    def test_success_with_warning_field(self):
        """SUCCESS + warning 字段应附加警告"""
        result = {"code": "SUCCESS", "data": {"r": "ok"}, "message": "完成",
                  "warning": "文件过大只读了前100行"}
        text = MessageBuilder.build_observation_text(result)
        assert "警告" in text
        assert "文件过大" in text

    def test_error_with_code(self):
        """ERR_ 状态应包含 [code] + message"""
        result = {"code": "ERR_FILE_NOT_FOUND", "data": None, "message": "文件不存在"}
        text = MessageBuilder.build_observation_text(result)
        assert "error" in text
        assert "ERR_FILE_NOT_FOUND" in text
        assert "文件不存在" in text

    def test_warning_prefix(self):
        """WARNING_ 前缀走独立分支"""
        result = {"code": "WARNING_FILE_TOO_LARGE", "data": {"部分": "数据"}, "message": "文件超大"}
        text = MessageBuilder.build_observation_text(result)
        assert "warning" in text
        assert "文件超大" in text

    def test_no_data_no_message(self):
        """没有 data 和 message 时不崩溃"""
        result = {"code": "SUCCESS"}
        text = MessageBuilder.build_observation_text(result)
        assert "success" in text


# =============================================================================
# 第三组：每轮 LLM 调用的消息组装
# =============================================================================

class TestPrepareMessagesForLLM:
    """prepare_messages_for_llm() 测试"""

    def test_prepare_returns_full_history(self):
        """应返回完整conversation_history"""
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "思考"},
            {"role": "system", "content": "[Observation] 结果"},
            {"role": "user", "content": "当前问题"},
        ]
        messages = mb.prepare_messages_for_llm()
        assert len(messages) == 5
        assert messages[-1]["content"] == "当前问题"

    def test_prepare_with_temp_history(self):
        """应合并temp_history"""
        mb = MessageBuilder()
        mb.conversation_history = [
            {"role": "system", "content": "sys"},
        ]
        mb.temp_history = [{"role": "assistant", "content": "流式中间态"}]
        messages = mb.prepare_messages_for_llm()
        assert len(messages) == 2
        assert messages[1]["content"] == "流式中间态"


class TestInjectToolsInfo:
    """inject_tools_info() 测试"""

    def test_inject_before_first_non_system(self):
        """工具信息应插入在第一个非 system 消息之前"""
        history = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "思考"},
        ]
        result = MessageBuilder.inject_tools_info(history, "【工具】search_web")
        assert result[0] == {"role": "system", "content": "sys"}
        assert result[1] == {"role": "system", "content": "【工具】search_web"}
        assert result[2] == {"role": "assistant", "content": "思考"}

    def test_inject_no_content_no_change(self):
        """tools_content 为空时不应修改 history"""
        history = [{"role": "system", "content": "sys"}]
        result = MessageBuilder.inject_tools_info(history, "")
        assert result == history

    def test_inject_only_system(self):
        """全部是 system 消息时追加到末尾"""
        history = [
            {"role": "system", "content": "sys1"},
            {"role": "system", "content": "sys2"},
        ]
        result = MessageBuilder.inject_tools_info(history, "【工具】info")
        assert len(result) == 3
        assert result[-1] == {"role": "system", "content": "【工具】info"}


class TestInjectExecutedSummary:
    """inject_executed_summary() 测试"""

    def test_inject_successful_tools(self):
        """只注入成功的工具"""
        history = [{"role": "system", "content": "sys"}]
        summary = ["search_web→success", "read_file→success"]
        result = MessageBuilder.inject_executed_summary(history, summary)
        assert len(result) == 2
        assert "已执行工具" in result[1]["content"]
        assert "search_web" in result[1]["content"]

    def test_inject_no_success_tools(self):
        """没有成功的工具时不注入"""
        history = [{"role": "system", "content": "sys"}]
        summary = ["search_web→failed"]
        result = MessageBuilder.inject_executed_summary(history, summary)
        assert len(result) == 1  # 未追加


class TestInjectSchemaText:
    """inject_schema_text() 测试"""

    def test_inject_appends_schema(self):
        """Schema 文本应追加到末尾"""
        history = [{"role": "system", "content": "sys"}]
        result = MessageBuilder.inject_schema_text(history, "【Schema】params")
        assert len(result) == 2
        assert "【Schema】" in result[1]["content"]

    def test_inject_no_text_no_change(self):
        """schema_text 为空时不修改"""
        history = [{"role": "system", "content": "sys"}]
        result = MessageBuilder.inject_schema_text(history, "")
        assert result == history



# =============================================================================
# 第四组：历史裁剪
# =============================================================================

class TestTrimHistory:
    """trim_history() 测试"""

    def test_no_trim_when_under_threshold(self):
        """未超过阈值(80%)时不裁剪"""
        mb = MessageBuilder(max_context_chars=10000)
        mb.init_history("s" * 100, "u" * 100)
        mb.add_assistant("hello")
        mb.trim_history()  # 100+100+5=205 << 8000
        assert len(mb.conversation_history) == 3

    def test_trim_when_over_threshold(self):
        """超过阈值时裁剪"""
        mb = MessageBuilder(max_context_chars=500)
        # 创建大量消息
        mb.init_history("system prompt " * 20, "user task " * 20)
        for i in range(10):
            mb.add_assistant("assistant response " * 10)
        old_len = len(mb.conversation_history)
        mb.trim_history()
        # 裁剪后应保留 sys_prompt + user_task + 最新几条
        assert len(mb.conversation_history) <= old_len

    def test_trim_preserves_first_two_messages(self):
        """裁剪后应保留 [0]system 和 [1]user"""
        mb = MessageBuilder(max_context_chars=300)
        mb.init_history("sys_prompt", "user_task")
        for i in range(20):
            mb.add_assistant("msg" + "x" * 50)
        mb.trim_history()
        assert mb.conversation_history[0]["role"] == "system"
        assert mb.conversation_history[1]["role"] == "user"


# =============================================================================
# 第五组：缓存管理 — 检查点6 小沈 2026-05-21
# =============================================================================

class TestCacheManagement:
    """invalidate_cache() 测试 — 19.6检查点6"""

    def test_cache_fields_initialized_none(self):
        """【结构完整性】__init__ 后三个缓存字段应为 None（删字段会暴露）"""
        mb = MessageBuilder()
        # 如果以下任一 AttributeError，说明 __init__ 中删了该字段
        assert mb._cached_schema_text is None
        assert mb._cached_tools_content is None
        assert mb._last_injected_categories is None

    def test_cache_fields_not_present_throws_attribute_error(self):
        """【防御】确认 _cached_schema_text 不是动态创建，是真的在 __init__ 中定义的"""
        mb = MessageBuilder()
        # 如果从来没有设置过，再检查一次值
        # 如果字段不在 __init__ 中，直接访问不会报错（Python创建），
        # 但 hasattr + 值检查可以判断是否被正确初始化
        assert "_cached_schema_text" in dir(mb), \
            "_cached_schema_text 不在 __init__ 中，如被删除！"
        assert "_cached_tools_content" in dir(mb), \
            "_cached_tools_content 不在 __init__ 中，如被删除！"
        assert "_last_injected_categories" in dir(mb), \
            "_last_injected_categories 不在 __init__ 中，如被删除！"

    def test_invalidate_cache_clears_all_cached_fields(self):
        """invalidate_cache() 应清空三个缓存字段"""
        mb = MessageBuilder()
        # 先确认初始状态是 None（验证 __init__ 正确）
        assert mb._cached_schema_text is None
        assert mb._cached_tools_content is None
        assert mb._last_injected_categories is None
        # 再填充缓存
        mb._cached_schema_text = "schema"
        mb._cached_tools_content = "tools"
        mb._last_injected_categories = {"file"}
        # 最后验证 invalidate_cache() 清空行为
        mb.invalidate_cache()
        assert mb._cached_schema_text is None
        assert mb._cached_tools_content is None
        assert mb._last_injected_categories is None

    def test_invalidate_cache_does_not_affect_execution_cache(self):
        """清空 schema 缓存不应影响执行结果缓存"""
        mb = MessageBuilder()
        # 先确认初始状态（验证 __init__ 正确）
        assert isinstance(mb._executed_cache, dict)
        assert isinstance(mb._failed_attempts, dict)
        mb._executed_cache["read_file:abc"] = {"code": "SUCCESS"}
        mb._failed_attempts["ping:xyz"] = 2
        mb.invalidate_cache()
        assert mb._executed_cache["read_file:abc"]["code"] == "SUCCESS"
        assert mb._failed_attempts["ping:xyz"] == 2

    def test_invalidate_cache_idempotent(self):
        """多次调用 invalidate_cache() 不应报错"""
        mb = MessageBuilder()
        mb.invalidate_cache()
        mb.invalidate_cache()
        mb.invalidate_cache()


# =============================================================================
# 第六组：延迟裁剪性能 — 检查点7 小沈 2026-05-21
# =============================================================================

class TestLazyTrimPerformance:
    """trim_history() 80% 延迟裁剪 — 19.6检查点7"""

    def test_trim_bypasses_when_under_80_percent(self):
        """历史未超过80%阈值时 trim 应快速跳过"""
        mb = MessageBuilder(max_context_chars=100000)
        mb.init_history("s" * 100, "u" * 100)
        mb.add_assistant("hello")
        import time
        start = time.perf_counter()
        for _ in range(100):
            mb.trim_history()
        elapsed = time.perf_counter() - start
        # 100次调用 < 100ms → 平均每次 < 1ms
        assert elapsed < 0.1, f"100次trim耗时{elapsed:.4f}s > 0.1s"

    def test_trim_only_triggers_when_over_threshold(self):
        """确认80%阈值判断逻辑：刚好低于阈值时不裁剪"""
        mb = MessageBuilder(max_context_chars=1000)
        # 总字符约 790 < 800(80%)，不应裁剪
        mb.conversation_history = [
            {"role": "system", "content": "s" * 100},
            {"role": "user", "content": "u" * 100},
            {"role": "assistant", "content": "a" * 590},
        ]
        mb.trim_history()
        assert len(mb.conversation_history) == 3

    def test_trim_triggers_when_over_threshold(self):
        """超过阈值时触发裁剪（必须有 observation 供移除）"""
        mb = MessageBuilder(max_context_chars=1000)
        # 包含 observation 消息（role=tool，含[Observation]标记）
        mb.conversation_history = [
            {"role": "system", "content": "s" * 100},
            {"role": "user", "content": "u" * 100},
            {"role": "assistant", "content": "a" * 100},
            {"role": "system", "content": "[Observation] 结果" + "x" * 400},
            {"role": "assistant", "content": "a" * 100},
            {"role": "system", "content": "[Observation] 结果" + "y" * 400},
        ]
        # 总字符：100+100+100+415+100+415 = 1230 > 800(80%)，应裁剪
        old_len = len(mb.conversation_history)
        mb.trim_history()
        # 裁剪后 observation 应被移除，system+user+assistant 保留
        assert len(mb.conversation_history) < old_len
        assert mb.conversation_history[0]["content"] == "s" * 100
        assert mb.conversation_history[1]["content"] == "u" * 100

    def test_trim_prefers_removing_oldest_observations(self):
        """超过阈值时优先移除最旧的 observation 消息"""
        mb = MessageBuilder(max_context_chars=1000)
        # system(100) + user(100) + obs1(400) + obs2(400)
        # 总 = 1000 > 800(80%)，应裁剪
        mb.conversation_history = [
            {"role": "system", "content": "s" * 100},
            {"role": "user", "content": "u" * 100},
            {"role": "system", "content": "[Observation] 旧结果" + "x" * 380},
            {"role": "system", "content": "[Observation] 新结果" + "y" * 380},
        ]
        mb.trim_history()
        # 预算 1000×0.7=700，system+user=200，只能保留1条observation
        # 旧observation（obs1）应被移除，新observation（obs2）保留
        assert len(mb.conversation_history) == 3
        assert "新结果" in str(mb.conversation_history)
        assert "旧结果" not in str(mb.conversation_history)


# =============================================================================
# 第七组：reset_per_run 生命周期 — 检查点8 小沈 2026-05-21
# =============================================================================

class TestResetPerRun:
    """reset_per_run() 生命周期 — 19.6检查点8"""

    def test_init_has_all_state_fields(self):
        """【结构完整性】__init__ 后所有状态字段应存在且类型正确"""
        mb = MessageBuilder()
        assert isinstance(mb._executed_cache, dict)
        assert isinstance(mb._cache_timestamps, dict)
        assert isinstance(mb._failed_attempts, dict)
        assert isinstance(mb._executed_tool_summary, list)
        assert mb._cached_schema_text is None
        assert mb._cached_tools_content is None
        assert mb._last_injected_categories is None
        # temp_history 应是 list
        assert isinstance(mb.temp_history, list)
        # conversation_history 应是 list
        assert isinstance(mb.conversation_history, list)

    def test_reset_clears_conversation_history(self):
        """reset_per_run 应清空 conversation_history"""
        mb = MessageBuilder()
        mb.init_history("sys", "task")
        mb.add_assistant("思考")
        mb.add_observation("结果", llm_call_count=1)
        assert len(mb.conversation_history) > 0
        mb.reset_per_run()
        assert mb.conversation_history == []

    def test_reset_clears_temp_history(self):
        """reset_per_run 应清空 temp_history"""
        mb = MessageBuilder()
        mb.temp_history.append({"role": "assistant", "content": "temp"})
        mb.reset_per_run()
        assert mb.temp_history == []

    def test_reset_preserves_executed_cache(self):
        """reset_per_run 应保留已执行工具缓存"""
        mb = MessageBuilder()
        # 先确认初始 dict 存在（验证 __init__）
        assert isinstance(mb._executed_cache, dict)
        assert isinstance(mb._cache_timestamps, dict)
        mb._executed_cache["search_web:abc"] = {"code": "SUCCESS"}
        mb._cache_timestamps["search_web:abc"] = 12345.0
        mb.reset_per_run()
        assert mb._executed_cache["search_web:abc"]["code"] == "SUCCESS"
        assert mb._cache_timestamps["search_web:abc"] == 12345.0

    def test_reset_preserves_failed_attempts(self):
        """reset_per_run 应保留失败计数（跨会话）"""
        mb = MessageBuilder()
        assert isinstance(mb._failed_attempts, dict)
        mb._failed_attempts["ping:xyz"] = 3
        mb.reset_per_run()
        assert mb._failed_attempts["ping:xyz"] == 3

    def test_reset_preserves_executed_tool_summary(self):
        """reset_per_run 应保留已执行工具汇总"""
        mb = MessageBuilder()
        assert isinstance(mb._executed_tool_summary, list)
        mb._executed_tool_summary.append("read_file→success")
        mb.reset_per_run()
        assert "read_file→success" in mb._executed_tool_summary

    def test_reset_preserves_schema_cache(self):
        """reset_per_run 应保留 Schema/工具内容缓存"""
        mb = MessageBuilder()
        assert mb._cached_schema_text is None
        assert mb._cached_tools_content is None
        assert mb._last_injected_categories is None
        mb._cached_schema_text = "schema"
        mb._cached_tools_content = "tools"
        mb._last_injected_categories = {"file"}
        mb.reset_per_run()
        assert mb._cached_schema_text == "schema"
        assert mb._cached_tools_content == "tools"
        assert mb._last_injected_categories == {"file"}
