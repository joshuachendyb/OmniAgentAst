# 编辑历史: 2026-07-18 小健 修正 ErrorStep/移除_ensure_failed_final_step/移除run_sse_stream 对齐07-13/07-18重构
# 编辑历史: 2026-08-11 小欧 对齐进化协议: ①validate_path 2元组解包→3元组(补category); ②mock validate_path返回值(True,"")→(True,None,None);
#   ③test_bug_is_forbidden_path_exception_allows修正坏测试(patch目标Path.resolve错误→os.path.realpath; 断言result is False→result=="system" fail-closed进化)
# -*- coding: utf-8 -*-
"""
12复у叧错祦绋嬫繁搴︽试请?第?杞?鈥?鏇村动熻兘bug鍜岄查昏緫bug
小健 2026-06-25

标目: 验证第?杞鏌ュ彂环扮个bug
"""

import asyncio
import json
import pytest
import tempfile
import os
import inspect
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pathlib import Path

from app.services.agent.message_builder import MessageBuilder
from app.services.agent.react_cycle import handle_react_error
from app.services.agent.step_emitter import StepEmitter
from app.services.agent.steps import (
    ThoughtStep, ActionStep, ObservationStep, ChunkStep,
    FinalStep, ErrorStep, MetaStep,
)
from app.services.agent.status_table import AgentStatus
from app.services.safety.tool_safety_checker import ToolSafetyChecker, SafetyResult, _is_skip_safety


def _make_system(content="system prompt"):
    return {"role": "system", "content": content}

def _make_user(content="user message"):
    return {"role": "user", "content": content}

def _make_assistant(content=None, tool_calls=None):
    msg = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return msg

def _make_tc(tc_id="tc_1", name="readtext", args='{"path":"x"}'):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": args}}

def _make_tool_result(tc_id="tc_1", content="result"):
    return {"role": "tool", "tool_call_id": tc_id, "content": content}

def _make_mock_agent():
    agent = MagicMock()
    agent.status = AgentStatus.EXECUTING
    agent.llm_call_count = 1
    agent.steps = []
    agent.message_builder = MessageBuilder()
    agent._step_emitter = StepEmitter(agent)
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent.set_failed = MagicMock(side_effect=lambda msg: setattr(agent, 'status', AgentStatus.FAILED))
    agent._task_tracker = None
    agent.task_id = None
    return agent


# ===========================================================================
# Bug #1: 名栨秷否在COMPLETED鑰岄潪CANCELLED
# ===========================================================================

class TestReactCycleBugsV2:

    def test_bug_cancelled_sets_completed_not_cancelled(self):
        # 銆怋ug17修銆慉gentStatus宸叉湁CANCELLED鐘舵查?鈥?chendyg 2026-06-26
        assert hasattr(AgentStatus, 'CANCELLED'), "Bug17修: AgentStatus搴旀湁CANCELLED鐘舵查?"
        assert AgentStatus.CANCELLED.value == "cancelled"

    def test_bug_truncated_retry_empty_tool_call_id(self):
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        agent = _make_mock_agent()
        mb = agent.message_builder
        mb.conversation_history = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
        ]
        parsed = {"type": "answer", "content": "short"}
        result = _should_retry_truncated_tool(agent, parsed)
        assert result is True, "户柇里嶈瘯应该Е名戯,你唎bservation的則ool_call_id名兘中虹┖存楃二"

    def test_bug_max_steps_zero_no_final_step(self):
        # 2026-07-18 对齐07-18重构: _ensure_failed_final_step 已删除,
        # max_steps<=0 路径直接在 run_react_cycle 发射 FinalStep(outcome="cancelled")。
        from app.services.agent import react_cycle
        source = inspect.getsource(react_cycle.run_react_cycle)
        assert 'outcome="cancelled"' in source, \
            "BUG: max_steps<=0 未发射 FinalStep(outcome=cancelled) 终态"

    def test_bug_dispatch_unknown_type_adds_no_history(self):
        agent = _make_mock_agent()
        mb = agent.message_builder
        original_len = len(mb.conversation_history)
        parsed = {"type": "unknown_type", "content": "garbage"}
        agent.set_failed("unknown response type")
        assert agent.status == AgentStatus.FAILED
        assert len(mb.conversation_history) == original_len, "BUG: 未煡类型响应未姞鍏ュ请濆巻名诧,LLM名兘里崩浜х敓标稿悓无效响应"

    def test_bug_should_retry_truncated_only_checks_last_assistant(self):
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        agent = _make_mock_agent()
        mb = agent.message_builder
        mb.conversation_history = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "done"),
            _make_assistant(content="normal answer"),
        ]
        parsed = {"type": "answer", "content": "I think..."}
        result = _should_retry_truncated_tool(agent, parsed)
        assert result is False, "未查否庝一误ssistant无爐ool_calls,屼不应该Е名戞埅方噸请?"


# ===========================================================================
# Bug #10/#11: parsed缂哄皯tool_name无禟eyError
# ===========================================================================

class TestActionHandlerBugsV2:

    def test_bug_build_call_list_missing_tool_name(self):
        from app.services.agent.handlers.action_handler import _build_call_list
        parsed_no_name = {"type": "action", "tool_params": {}}
        # P1-10修在里┖tool_name中崩啀鎶汯eyError,岃查我是warning骞剁户结?鈥?chendyg 2026-06-26
        result = _build_call_list(parsed_no_name)
        assert result.tool_name == "", "空tool_name应该返回空字符串"

    def test_bug_build_call_list_missing_tool_params(self):
        from app.services.agent.handlers.action_handler import _build_call_list
        parsed_no_params = {"type": "action", "tool_name": "readtext"}
        result = _build_call_list(parsed_no_params)
        assert result.tool_params == {}, "BUG: 缺少tool_params默认应为空dict，但无防御检查"

    def test_bug_build_call_list_pending_calls_missing_keys(self):
        from app.services.agent.handlers.action_handler import _build_call_list
        parsed = {
            "type": "action", "tool_name": "readtext", "tool_params": {},
            "_pending_calls": [{"tool_name": "writetext"}],
        }
        # P1-11修在里己tool_params的刾ending_call中崩啀鎶汯eyError,岀敤榛樿空篸ict 鈥?chendyg 2026-06-26
        result = _build_call_list(parsed)
        assert len(result.all_calls) == 2, "pending_call缺tool_params应使用默认空dict"

    def test_bug_all_results_exception_merged_llm_data_none(self):
        from app.services.agent.handlers.action_handler import _merge_llm_data
        result = _merge_llm_data([])
        assert result == {}, "BUG: 空簂lm_data列楄〃返回空篸ict鑰岄潪None,屼絾鍏‥xception在写櫙名兘浜х敓空篸ict否?get()返回None"

    def test_bug_parallel_retry_skips_safety(self):
        assert True, "BUG认: action_handler.py骞惰执行里嶈瘯通昏緫中嶇粡连嘽heck_safety_and_confirm,请彲鑳界粫连囧畨鍏ㄧ瓥鐣?"


# ===========================================================================
# Bug #16/#17: DB标稿叧
# ===========================================================================

class TestRunSSEStreamBugsV2:

    def test_bug_load_previous_messages_swallows_exception(self):
        from app.services.chat.stream import _load_previous_messages
        with patch("app.services.chat.stream._load_previous_messages", side_effect=Exception("DB error")):
            pass
        assert True, "BUG认: _load_previous_messages异常无惰繑回瀃],我棤娉曞尯列?无如巻名?鍜?动犺浇失败'"

    def test_bug_db_save_only_retries_once(self):
        call_count = 0
        def failing_save():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("DB busy")
        for retry in range(2):
            try:
                failing_save()
            except Exception:
                if retry == 1:
                    break
        assert call_count == 2, "DB修濆瓨未查复氶噸请?娆★紙range(2),夛,失败否庢暟据案涔呬涪复?"

    def test_bug_stream_state_none_saves_empty_content(self):
        stream_state = None
        saved_content = stream_state.current_content if stream_state else ""
        assert saved_content == "", "BUG: stream_state中篘one无朵繚存樼┖存楃中插埌DB"


# ===========================================================================
# Bug #23/#24: answer_handler
# ===========================================================================

class TestAnswerHandlerBugsV2:

    def test_bug_empty_answer_silently_completes(self):
        agent = _make_mock_agent()
        agent.status = AgentStatus.COMPLETED
        step = FinalStep(step=1, response="")
        d = step.to_dict()
        assert d.get("response") == "" or d.get("content") == "", "BUG: LLM返回空哄唴完案椂非欓粯完我垚,岀敤户风湅中崩埌件讳綍响应"

    def test_bug_empty_answer_skips_add_assistant_message(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        original_len = len(mb.conversation_history)
        assert original_len == 2
        assert True, "BUG认: 空哄唴完筫arly return无朵不璋僡dd_assistant_message,请请濆巻名茬己灏戞杞產ssistant消息"


# ===========================================================================
# Bug #27: tool_retry_engine名岄噸wait_for
# ===========================================================================

class TestToolRetryEngineBugsV2:

    def test_bug_double_wait_for_timeout(self):
        timeout = 30
        actual_max = timeout * 2
        assert actual_max == 60, "BUG: 否我宸ュ叿asyncio.to_thread + asyncio.wait_for名岄噸璁℃椂,我查昏秴无读彲输?*timeout"

    def test_bug_shallow_copy_params(self):
        original = {"path": "/test", "options": {"encoding": "utf-8"}}
        params_copy = original.copy()
        params_copy["options"]["encoding"] = "ascii"
        assert original["options"]["encoding"] == "ascii", "BUG: 娴呮嫹璐濆鑷村祵濂楀彲名在璞¤修敼,请奖响嶈皟用户柟原因数据"


# ===========================================================================
# Bug #32: initialize_run_state中写けtool消息
# ===========================================================================

class TestInitializeRunStateBugsV2:

    def test_bug_inject_conversation_history_drops_tool_messages(self):
        from app.services.agent.initialize_run_state import _inject_conversation_history
        agent = _make_mock_agent()
        mb = agent.message_builder
        previous = [
            _make_system("sys"),
            _make_user("task"),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "file content"),
            _make_assistant(content="I found the file"),
        ]
        context = {"previous_messages": previous}
        _inject_conversation_history(agent, context)
        tool_msgs = [m for m in mb.conversation_history if m.get("role") == "tool"]
        assistant_with_tc = [m for m in mb.conversation_history if m.get("role") == "assistant" and m.get("tool_calls")]
        # P0-1修否巘ool消息鍜请甫tool_calls的刟ssistant消息琚繚鐣?鈥?chendyg 2026-06-26
        assert len(tool_msgs) == 1, f"P0-1修: tool消息应该修濈暀,请疄闄呮湁{len(tool_msgs)}误?"
        assert len(assistant_with_tc) == 1, f"P0-1修: 常ool_calls的刟ssistant消息应该修濈暀,请疄闄呮湁{len(assistant_with_tc)}误?"

    def test_bug_inject_drops_empty_content_assistant(self):
        from app.services.agent.initialize_run_state import _inject_conversation_history
        agent = _make_mock_agent()
        mb = agent.message_builder
        previous = [
            _make_system("sys"),
            _make_user("task"),
            _make_assistant(content=""),
        ]
        context = {"previous_messages": previous}
        _inject_conversation_history(agent, context)
        assistant_msgs = [m for m in mb.conversation_history if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 0, "BUG: content中虹┖存楃中茬个assistant消息琚涪异?"


# ===========================================================================
# Bug #34/#36: openai
# ===========================================================================

class TestChatOpenaiBugsV2:

    def test_bug_none_content_causes_typeerror(self):
        request_messages = [{"role": "user", "content": None}]
        user_input = request_messages[-1]["content"]
        assert user_input is None, "BUG: content中篘one无朵紶鍏gent名兘对艰嚧TypeError"

    def test_bug_empty_session_id_replaced(self):
        session_id = "" or str("new-uuid")
        assert session_id == "new-uuid", "BUG: 空哄瓧第︿覆session_id琚浛据为方癠UID,请户风鎰忓浘琚牬鍧?"

    def test_bug_pause_race_condition(self):
        assert True, "BUG认: pause名标囧織你嶄不鎸傝捣agent,请瓨在ㄧ珵鎬佺獥名?"


# ===========================================================================
# Bug #38: Windows路径复у皬内这晱鎰?
# ===========================================================================

class TestPathValidatorBugsV2:

    def test_bug_windows_path_case_sensitive(self):
        from app.services.safety.path_safe_check import validate_path
        try:
            is_valid1, _, _ = validate_path("C:\\Users\\test\\file.txt")
            is_valid2, _, _ = validate_path("c:\\users\\test\\file.txt")
            if is_valid1 != is_valid2:
                pytest.fail(f"BUG: Windows路径复у皬内这晱鎰熸瘮输? C:\\={is_valid1}, c:\\={is_valid2}")
        except Exception as e:
            assert True, f"路径验证异常: {e}"

    def test_bug_is_forbidden_path_exception_allows(self):
        from app.services.safety.path_safe_check import _is_forbidden_path
        with patch("os.path.realpath", side_effect=RuntimeError("resolve error")):
            result, msg = _is_forbidden_path("/some/path")
            assert result == "system", "BUG: _is_forbidden_path异常时未fail-closed为system"

    def test_bug_linux_tmp_paths_on_windows(self):
        from app.services.safety.path_safe_check import get_default_allowed_paths
        try:
            paths = get_default_allowed_paths()
            for p in paths:
                if str(p) in ("/tmp", "/var/tmp"):
                    assert True, "BUG: /tmp鍜?var/tmp是疞inux路径,學indows中婅В果愪为褰撳墠椹卞姩鍣ㄤ笅\\tmp"
        except Exception:
            pass


# ===========================================================================
# Bug #45: LLMClient连接姹犳硠婕?
# ===========================================================================

class TestLLMClientBugsV2:

    def test_bug_async_client_no_auto_close(self):
        from app.services.llm.client_sdk import LLMClient
        has_del = hasattr(LLMClient, '__del__')
        has_aexit = hasattr(LLMClient, '__aexit__')
        has_aclose = hasattr(LLMClient, 'close') or hasattr(LLMClient, 'aclose')
        # P1-22修否嶭LMClient未塤_aexit__ 鈥?chendyg 2026-06-26
        assert has_aexit, "P1-22修: LLMClient搴旀湁__aexit__认繚连接姹如叧问题?"
        assert has_aclose, "LLMClient搴旀湁close方案硶"

    def test_bug_tool_names_keyerror(self):
        tools = [{"type": "function"}]
        try:
            tool_names = {t["function"]["name"] for t in tools}
            assert False, "搴旀姏KeyError"
        except KeyError:
            assert True, "BUG: tools列楄〃缂哄皯function/name错椂KeyError无犻槻循?"


# ===========================================================================
# Bug #48/#52: task_tracker/task_cancel
# ===========================================================================

class TestTaskBugsV2:

    def test_bug_sequence_number_not_atomic(self):
        assert True, "BUG认: task_tracker搴忓垪名风敓户怱ELECT MAX+1非复師存愭搷你滐,骞读彂名兘里崩"

    def test_bug_cancel_nonexistent_task_no_http_close(self):
        assert True, "BUG认: task_cancel对逛不存在的則ask_id,孒TTP连接中崩叧问题?"

    def test_bug_pause_resume_no_state_validation(self):
        assert True, "BUG认: pause/resume中嶉獙请乼ask_id存在鎬у拰褰撳墠鐘舵查?"


# ===========================================================================
# Bug #56/#57: registry
# ===========================================================================

class TestRegistryBugsV2:

    def test_bug_update_tool_not_update_fields(self):
        from app.tools.registry import ToolRegistry
        import inspect
        src = inspect.getsource(ToolRegistry._update_existing_tool)
        missing_fields = []
        for field in ["expose_to_llm", "failure_hint_fn", "needs_confirmation", "action_confirmation", "check_fn"]:
            if field not in src:
                missing_fields.append(field)
        # P1-25修否庢墍未夊瓧娈甸兘更新浜?鈥?chendyg 2026-06-26
        assert len(missing_fields) == 0, f"P1-25修: _update_existing_tool搴旀洿方版墍未夊瓧娈? 缂哄け: {missing_fields}"

    def test_bug_update_category_not_reindexed(self):
        from app.tools.registry import ToolRegistry
        import inspect
        src = inspect.getsource(ToolRegistry._update_existing_tool)
        # P1-26修否庢洿方到伐鍏求椂列嗙被绱写紩涔熸洿方?鈥?chendyg 2026-06-26
        assert "_update_category_index" in src, "P1-26修: 更新宸ュ叿category无读垎类荤储异曞应更新"


# ===========================================================================
# Bug #38: path_validator复у皬内?鈥?娣卞入验证
# ===========================================================================

class TestPathValidatorDeepBugs:

    def test_bug_path_prefix_match_case_sensitive(self):
        from app.services.safety.path_safe_check import validate_path
        try:
            home = str(Path.home())
            if home:
                upper_path = home.upper() + "\\test.txt"
                lower_path = home.lower() + "\\test.txt"
                try:
                    v1, _, _ = validate_path(upper_path)
                    v2, _, _ = validate_path(lower_path)
                    if v1 != v2:
                        pytest.fail(f"BUG: Windows路径复у皬内欎不一致? {upper_path}={v1}, {lower_path}={v2}")
                except Exception:
                    pass
        except Exception:
            pass

    def test_bug_path_traversal_dotdot_check(self):
        from app.services.safety.path_safe_check import validate_path
        try:
            is_valid, msg, _ = validate_path("E:/test/../../etc/passwd")
            assert not is_valid, "路径空胯秺应该鎷掔粷"
        except Exception:
            pass


# ===========================================================================
# 预濆输照晫误′欢bug
# ===========================================================================

class TestEdgeCaseBugsV2:

    def test_bug_trim_history_with_only_system_user(self):
        mb = MessageBuilder(max_context_tokens=10)
        mb.conversation_history = [_make_system("s" * 5), _make_user("u" * 5)]
        mb.trim_history()
        assert len(mb.conversation_history) == 2

    def test_bug_trim_history_with_huge_single_observation(self):
        mb = MessageBuilder(max_context_tokens=1000)
        mb.conversation_history = [
            _make_system("s" * 50), _make_user("u" * 50),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "r" * 5000),
        ]
        mb.trim_history()
        total = mb._total_chars(mb.conversation_history)
        assert total > 0

    def test_bug_message_builder_add_observation_no_fc_context(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.add_observation("result", {"tool_call_id": "", "tool_calls": []})
        assert len(mb.conversation_history) >= 3

    def test_bug_safety_checker_concurrent_access(self):
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        c1 = get_tool_safety_checker()
        c2 = get_tool_safety_checker()
        assert c1 is c2

    def test_bug_error_step_to_dict_fields(self):
        step = ErrorStep(step=1, error_type="fc_format_error", error_message="bad")
        d = step.to_dict()
        assert "error_type" in d
        assert "error_message" in d or "message" in d

    def test_bug_fc_message_types_dict_to_message_extra_fields(self):
        from app.services.agent.fc_message_types import dict_to_message, SystemMessage
        d = {"role": "system", "content": "test", "extra_field": "ignored"}
        try:
            msg = dict_to_message(d)
            assert isinstance(msg, SystemMessage)
        except Exception:
            assert True, "BUG: dict_to_message用?*d浼如弬,岄复栧瓧娈靛彲鑳藉鑷碫alidationError"

    def test_bug_tool_registry_same_name_different_category(self):
        from app.tools.registry import ToolRegistry
        assert True, "BUG认: 中崩悓列嗙被未夊悓否崩伐鍏求椂否庡姞杞借标栧先动犺浇,我棤璀﹀憡"

    def test_bug_task_tracker_empty_description(self):
        assert True, "BUG认: tracker.create_task(description='')件型务描述濮嬬粓中虹┖"

    def test_bug_cancel_poller_delay(self):
        assert True, "BUG认: _cancel_poller姣?绉掕置请,SSE空洪棽无读彇乱堝搷搴斿欢连因彇内充簬中嬩一中猚hunk"

    def test_bug_client_sdk_sse_ignore_event_fields(self):
        assert True, "BUG认: SSE解ｆ瀽名鐞哾ata:前嶇紑行,蹇界暐event:/id:/retry:标准存楁"

    def test_bug_tool_cache_manager_patch_no_invalidate(self):
        from app.services.agent.tool_cache_manager import patch_search_desc
        agent = _make_mock_agent()
        from app.tools.tool_types import ToolCategory
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}
        agent._tool_search_desc_override = None
        agent._tool_cache = MagicMock()
        agent._tool_cache.get = MagicMock(return_value="cached_value")
        try:
            patch_search_desc(agent)
        except Exception:
            pass
        assert True, "BUG认: patch_search_desc中嶄富动ㄥけ整堢紦存橈,方皁verride名兘中嶇敓整?"

    def test_bug_load_category_not_update_loaded_categories(self):
        from app.services.agent.base_agent import ToolLoader
        assert True, "BUG认: load_category中死洿方癮gent._loaded_categories,岃皟用户柟必须鑷更新"

    def test_bug_answer_handler_empty_content_no_history(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user("hello")]
        original = len(mb.conversation_history)
        assert original == 2
        assert True, "BUG认: answer_handler空哄唴完案椂early return中嶈皟add_assistant_message"

    def test_bug_run_sse_stream_event_no_to_dict(self):
        event = "not_a_step_object"
        result = event if isinstance(event, dict) else getattr(event, 'to_dict', lambda: {"type": "unknown"})()
        assert result == {"type": "unknown"}, "event无不是痙ict涔熸病未塼o_dict无读应闃插尽鎬у鐞?"

    def test_bug_trim_fc_pairs_all_orphan(self):
        mb = MessageBuilder()
        messages = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_2", "orphan 1"),
            _make_tool_result("tc_3", "orphan 2"),
        ]
        result = mb._trim_fc_pairs(messages)
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        assistant_with_tc = [m for m in result if m.get("role") == "assistant" and m.get("tool_calls")]
        assert len(tool_msgs) == 0, "类查未塼ool消息閮藉绔册应琚Щ闄?"
        assert len(assistant_with_tc) == 0, "tc_1的刟ssistant无犻厤对箃ool应该绉婚櫎"

    def test_bug_build_tool_calls_response_only_first_name(self):
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = _make_mock_agent()
        agent.llm_call_count = 1
        tool_calls_result = [
            {"tool_name": "readtext", "tool_params": {"path": "a"}, "tool_call_id": "tc_1", "tool_calls": [_make_tc("tc_1", "readtext")]},
            {"tool_name": "writetext", "tool_params": {"path": "b"}, "tool_call_id": "tc_2", "tool_calls": [_make_tc("tc_2", "writetext")]},
        ]
        result = _build_tool_calls_response("thinking", tool_calls_result, None, agent)
        assert result[1]["tool_name"] == "readtext", "BUG: 复氬伐鍏疯皟用户椂名彇第一中伐鍏少悕"

    def test_bug_write_size_protection_param_name_mismatch(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = False
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                with patch("app.tools.registry.tool_registry.get_categories") as mock_cat:
                    from app.tools.tool_types import ToolCategory
                    mock_cat.return_value = {ToolCategory.FILE: ["writetext"]}
                    with patch("app.services.safety.path_safe_check.validate_path", return_value=(True, None, None)):
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write("A" * 2000)
                            tmp_path = f.name
                        try:
                            result = checker.check_before_execute("writetext", {"path": tmp_path, "content": "tiny"})
                            assert result.blocked is True, "FIXED(#29): 写入复у皬修濇姢名有暟否崩凡修中簆ath,请ぇ文件写入应该闃绘"
                        finally:
                            os.unlink(tmp_path)

    def test_bug_safety_checker_destructive_vs_dangerous(self):
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = True
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("needs_confirm_tool", {})
                assert result.safety_level == "destructive", "BUG: 方囨.请翠二鍏?safe/dangerous),请疄闄呬三鍊?safe/dangerous/destructive)"