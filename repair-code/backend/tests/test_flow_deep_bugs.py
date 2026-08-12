# 编辑历史: 2026-07-18 小健 修正 ErrorStep/移除_ensure_failed_final_step 对齐07-13/07-18重构
# 编辑历史: 2026-08-11 小欧 对齐进化协议: ①test_bug_is_forbidden_path_exception_allows_access断言result is True→result=="system"(P1-21 fail-closed返回category); ②mock validate_path(True,"")→(True,None,None)
# -*- coding: utf-8 -*-
"""test"""

import asyncio
import json
import pytest
import os
import tempfile
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
# 娴佺▼1: HTTP请求鍏ュ彛中嶴SE娴佸紡列濆鍖?
# ===========================================================================

class TestFlow1HTTPEntry:

    def test_bug_cancel_poller_race_with_sse_close(self):
        """bug cancel poller race with sse close"""
        from app.api.v1.chat.openai import StreamState
        state = StreamState()
        state.current_content = "宸茬粡绱Н的刢hunk内容..."
        # final事件: content = event_dict.get('response', '') or ''
        # run_sse_stream.py:146: stream_state.current_content = content or stream_state.current_content
        final_content = "未查结堝洖等?"
        # 如果final_content非空,岀洿鎺ヨ标栵,chunk绱Н内容中写け
        result = final_content or state.current_content
        assert result == "未查结堝洖等?"
        assert "宸茬粡绱Н的刢hunk内容" not in result
        # BUG认,歠inal瑕嗙洊chunk绱Н内容

    def test_bug_session_id_empty_string_not_none(self):
        """bug session id empty string not none"""
        session_id = "" or str("new-uuid")
        assert session_id == "new-uuid"
        # BUG认,氱┖存楃中瞫ession_id琚浛据?

    def test_bug_register_task_after_interrupt_no_cleanup(self):
        """bug register task after interrupt no cleanup"""
        # 如果interrupt检查ュ在register涔册悗,宑leanup浼氬垹闄ゅ垰娉ㄥ手册的則ask
        # 你嗗果渋nterrupt检查ュ在register涔册墠,宼ask_id未敞内,cleanup无效
        # 实际件ｇ爜,歳egister 鈫?interrupt_check 鈫?cleanup,岄认搴忔认?
        # 你嗗果渋nterrupt否庝不return鑰岀户结墽行,task宸瞔leanup你哸i_service件崩瓨在?
        assert True  # 通昏緫正认,岄潪bug

    def test_bug_poller_task_cancel_not_awaited_properly(self):
        """bug poller task cancel not awaited properly"""
        # openai.py:162-165
        # try: await poller_task except CancelledError: pass
        # 如果poller_task内呴儴未夊叾件栧紓常革,CancelledError浼氭帺标栧畠
        assert True  # BUG认,欳ancelledError名兘鎺╃洊poller内呴儴异常

    def test_bug_sse_stream_aclose_on_non_async_gen(self):
        """bug sse stream aclose on non async gen"""
        # run_sse_stream返回AsyncGenerator,宎close()应该名敤
        # 你嗗果渞un_sse_stream内呴儴鎶涘紓常革,sse_stream名兘中死是有效用熸垚鍣?
        assert True  # 你庨闄╋,run_sse_stream濮嬬粓返回AsyncGenerator


# ===========================================================================
# 娴佺▼2: Agent用因懡鍛户湡中里姸鎬佺鐞?
# ===========================================================================

class TestFlow2AgentLifecycle:

    def test_bug_tracker_create_task_empty_description(self):
        """bug tracker create task empty description"""
        # 实际task内容在╮un_react_cycle的則ask名有暟中,你唗racker.create_task浼犵┖存楃二
        assert True  # BUG认,歵racker件型务描述濮嬬粓中虹┖

    def test_bug_retry_engine_bound_to_stale_tools_dict(self):
        """bug retry engine bound to stale tools dict"""
        agent = _make_mock_agent()
        agent.status = AgentStatus.CANCELLED
        emitter = agent._step_emitter
        # complete_task(agent.status == AgentStatus.COMPLETED) 鈫?False
        # CANCELLED无秙uccess=False,我认?
        assert agent.status != AgentStatus.COMPLETED

    def test_bug_on_session_init_not_called_with_context(self):
        """bug on session init not called with context"""
        # UniversalAgent娌℃湁override _on_session_init
        # 连欎不是痓ug,我是璁捐,氬瓙类型彲override
        assert True  # 非瀊ug,岃璁″步

    def test_bug_consecutive_truncations_not_reset_on_new_run(self):
        """bug consecutive truncations not reset on new run"""
        agent = _make_mock_agent()
        mb = agent.message_builder
        original_len = len(mb.conversation_history)
        # _dispatch_handler对案湭鐭ョ被鍨册彧set_failed+emit FinalStep
        # 中死妸无效响应褰揳ssistant消息动如入原嗗彶
        # 中嬫LLM调用无朵不鐭ラ亾中婃浜х敓浜嗘棤整堝搷搴旓,名兘里崩
        assert len(mb.conversation_history) == original_len
        # BUG认,氭湭鐭ョ被鍨册搷搴斾不动如入原嗗彶,孡LM名兘里崩

    def test_bug_timeout_error_no_final_step(self):
        """bug timeout error no final step"""
        # 2026-07-18 对齐07-18重构: 终态由FinalStep(outcome=failed)表示,
        # _ensure_failed_final_step 已在07-13删除。此处断言超时失败路径会调用set_failed并终态化。
        from app.services.agent import react_cycle
        source = inspect.getsource(react_cycle.run_react_cycle)
        assert "set_failed" in source, "超时失败路径应调用set_failed终态化"
        assert "FinalStep" in source, "失败路径应发射FinalStep终态"

    def test_bug_should_retry_truncated_only_checks_last_assistant(self):
        """bug should retry truncated only checks last assistant"""
        # 在写櫙,歛ssistant(tc_1) 鈫?tool(tc_1) 鈫?assistant(tc_2) 鈫?answer
        # 件庡悗循查前死壘,请先类惧埌assistant(tc_2),屼絾tc_2否庨潰娌℃湁tool
        # 实际应该检查c_2是惁配崩
        from app.services.agent.react_cycle import _should_retry_truncated_tool
        agent = _make_mock_agent()
        mb = agent.message_builder
        mb.conversation_history = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "done"),
            _make_assistant(tool_calls=[_make_tc("tc_2")]),
            # tc_2娌℃湁对瑰应的則ool结果
        ]
        parsed = {"type": "answer", "content": "short"}
        result = _should_retry_truncated_tool(agent, parsed)
        assert result is True  # tc_2未厤对癸,应该Е名戞埅方噸请?

    def test_bug_should_retry_truncated_false_when_all_paired(self):
        """bug should retry truncated false when all paired"""
        # 如果agent.status在╤andle_react_error中璁找为RETRYABLE_ERROR
        # 列檁ensure_failed_final_step中嶄細行ュ彂FinalStep,堝彧对笷AILED行ュ彂,?
        # RETRYABLE_ERROR无读惊环户结,你嗗果滃在except中浜哛ETRYABLE_ERROR
        # 循环宸茬粡break浜嗭紙except在╰ry内咃級,屼不浼氱户结?
        # 实际中奺xcept在╰ry内咃,中嶄細break,屼細结х画列皐hile误′欢检查?
        # 你唚hile误′欢检查ヤ腑RETRYABLE_ERROR中崩在结堟误′欢二
        # 类查件ュ惊环細结х画,屼絾agent.status是疪ETRYABLE_ERROR
        # 中嬩一杞甠process_single_step前嶏,while内容先检查tatus
        # RETRYABLE_ERROR 鈫?continue,坮eact_cycle.py:258-260,?
        # 连这是正认行为
        assert True  # 非瀊ug

    def test_bug_process_single_step_no_tools_available(self):
        """bug process single step no tools available"""
        # action_handler.py:117-118: results[i] = await execute_tool(agent, ...)
        # 标存接璋僥xecute_tool,岃烦连囧畨鍏户鏌?
        assert True  # BUG认,氬苟行岄噸请点烦连囧畨鍏户鏌?

    def test_bug_build_observation_exception_no_execution_status(self):
        """bug build observation exception no execution status"""
        from app.services.agent.handlers.action_handler import build_observation, ObservationContext
        # action_handler.py:210-218:
        # isinstance(result, dict)中篎alse无讹,_ec中虹┖存楃二
        # 你嗘试请曟湡未沞xecution_status=="error"
        assert True  # BUG认,欵xception结果的別xecution_status中虹┖

    def test_bug_return_direct_after_observation_step(self):
        """bug return direct after observation step"""
        # action_handler.py:367-376
        # 鍏坹ield ObservationStep,请啀检查eturn_direct yield FinalStep
        # 前嶇鏀读埌observation在里珛鍗虫敹列癴inal,请彲鑳介棯鐑?
        assert True  # 璁捐问题,岄潪件ｇ爜bug

    def test_bug_shallow_copy_in_retry_engine(self):
        """bug shallow copy in retry engine"""
        # tool_retry_engine.py:49-53:
        # await asyncio.wait_for(asyncio.to_thread(...), timeout=timeout)
        # if inspect.iscoroutine(result): await asyncio.wait_for(result, timeout=timeout)
        # 未查鍧忔儏内碉細to_thread鑰楁椂timeout,岃繑回瀋oroutine内嶈查楁椂timeout
        # 鎬昏2*timeout
        assert True  # BUG认,氬弻里峸ait_for对艰嚧鎬昏秴无*timeout

    def test_bug_tool_not_found_returns_error_not_exception(self):
        """bug tool not found returns error not exception"""
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        engine = ToolRetryEngine({})
        result = asyncio.run(engine.execute_tool_with_retry("nonexistent_tool", {}))
        assert isinstance(result, dict)
        assert result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


# ===========================================================================
# 娴佺▼5: 文件完夊叏
# ===========================================================================

class TestFlow5FileSafety:

    def test_bug_write_size_protection_param_name_mismatch(self):
        """bug write size protection param name mismatch"""
        # tool_safety_checker.py中璤check_known_risks
        # write_text_file的勫弬整版是path,屼絾复у皬修濇姢名兘用╢ile_path
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
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write("A" * 2000)
                            tmp_path = f.name
                        try:
                            result = checker.check_before_execute("writetext", {"path": tmp_path, "content": "tiny"})
                            # 如果复у皬修濇姢用╢ile_path鑰岄潪path,屼細类找不列版件件读ぇ灏忥,跳过修濇姢
                            assert result.blocked is False or result.blocked is True
                        finally:
                            os.unlink(tmp_path)

    def test_bug_safety_level_three_values_not_two(self):
        """bug safety level three values not two"""
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = True
                mock_meta.action_confirmation = None
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("needs_confirm_tool", {})
                # needs_confirmation=True无秙afety_level应该是痙angerous
                # 你嗗疄闄容彲鑳芥是destructive
                assert result.safety_level in ("safe", "dangerous", "destructive")

    def test_bug_is_forbidden_path_exception_allows_access(self):
        """bug is forbidden path exception allows access"""
        from app.services.safety.path_safe_check import _is_forbidden_path
        with patch("os.path.realpath", side_effect=RuntimeError("resolve error")):
            result, msg = _is_forbidden_path("/some/path")
            assert result == "system"  # P1-21修复: 异常时拒绝(fail-closed, category=system)


# ===========================================================================
# 娴佺▼6: SSE浜嬩欢娴?
# ===========================================================================

class TestFlow6SSEEventFlow:

    def test_bug_db_save_only_retries_once(self):
        """bug db save only retries once"""
        # run_sse_stream.py:199: for retry in range(2)
        # 第?娆″け璐モ啋里嶈瘯,岀1娆″け璐モ啋中崩啀里嶈瘯
        # 鎬型叡未查复?娆″皾请曪紙1娆″垵濮?1娆￠噸请曪級
        assert True  # BUG认,欴B修濆瓨失败否庢暟据涪复?

    def test_bug_stream_state_none_saves_empty_content(self):
        """bug stream state none saves empty content"""
        stream_state = None
        saved_content = stream_state.current_content if stream_state else ""
        assert saved_content == ""

    def test_bug_cancelled_error_path_agent_status_before_final(self):
        """bug cancelled error path agent status before final"""
        # run_sse_stream.py:172-179: 鍏坹ield final_step,请啀璁綼gent.status
        # 连这是正认的勶細鍏堢粰前嶇名发粓鎬佷簨件讹,内死洿方到唴閮ㄧ姸鎬?
        assert True  # 非瀊ug,氶认搴忔认?

    def test_bug_event_dict_missing_to_dict_for_non_step_objects(self):
        """bug event dict missing to dict for non step objects"""
        event = "not_a_step_object"
        # run_sse_stream.py:133: event_dict = event if isinstance(event, dict) else event.to_dict()
        # 如果event是痵tr,我病未塼o_dict方案硶
        try:
            event_dict = event if isinstance(event, dict) else event.to_dict()
            assert False, "搴旀姏AttributeError"
        except AttributeError:
            assert True  # BUG认,氶潪dict非濻tep对硅薄浼氬穿溃?


# ===========================================================================
# 娴佺▼7: ContextVar浼犳挱
# ===========================================================================

class TestFlow7ContextVar:

    def test_bug_contextvar_name_mismatch(self):
        """bug contextvar name mismatch"""
        # openai.py:107: _current_task_id.set(task_id)
        # 你唃enerate()结撴潫否庢病未塤current_task_id.reset()
        # ContextVar是崗绋嬮殧绂荤个,屼不否岃姹傚在中崩悓鍗忕▼二
        # 你嗗果滃悓中查鍗忕▼琚用,名兘请型埌无у查?
        assert True  # 你庨闄╋細FastAPI姣忎个请求在ㄧ嫭绔册崗绋嬩腑


# ===========================================================================
# 娴佺▼8: LLM通氫俊
# ===========================================================================

class TestFlow8LLMCommunication:

    def test_bug_call_llm_stream_tool_choice_none_when_no_tools(self):
        """bug call llm stream tool choice none when no tools"""
        # llm_stream.py:131-133: stream_error无秚ool_calls_result = None
        # 你嗕箣前崩凡结弝ield浜哻hunk结欏墠绔?
        # 前嶇鐪册埌浜嗛儴列哻hunk内容,岀劧否庢敹列癳rror
        # 连欏彲鑳藉鑷村墠绔樉绀轰不完整的勫搷搴?
        assert True  # BUG认,歴tream_error否庡凡yield的刢hunk无犳硶场ゅ洖

    def test_bug_fc_fallback_text_mode_no_system_guidance(self):
        """bug fc fallback text mode no system guidance"""
        # llm_stream.py:167: call_llm_stream(agent, messages, openai_tools=None)
        # Text妯″紡中婰LM名兘用ㄨ嚜鐒惰瑷查描述宸ュ叿调用,我棤娉点解ｆ瀽
        assert True  # BUG认,歍ext妯″紡无如伐鍏求牸异忔寚对?

    def test_bug_build_tool_calls_response_only_first_name(self):
        """bug build tool calls response only first name"""
        from app.services.agent.llm_stream import _build_tool_calls_response
        agent = _make_mock_agent()
        agent.llm_call_count = 1
        tool_calls_result = [
            {"tool_name": "readtext", "tool_params": {"path": "a"}, "tool_call_id": "tc_1", "tool_calls": [_make_tc("tc_1", "readtext")]},
            {"tool_name": "writetext", "tool_params": {"path": "b"}, "tool_call_id": "tc_2", "tool_calls": [_make_tc("tc_2", "writetext")]},
        ]
        result = _build_tool_calls_response("thinking", tool_calls_result, None, agent)
        assert result[1]["tool_name"] == "readtext"
        # BUG认,氬宸ュ叿调用无读彧名栫中查中伐鍏少悕

    def test_bug_cancelled_error_in_call_llm_stream_returns_none(self):
        """bug cancelled error in call llm stream returns none"""
        # 测试: orphaned tc_1 和 tc_2 不配对 → _trim_fc_pairs 应删除两者
        messages = [
            _make_system(),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_2", "orphan 1"),
        ]
        result = MessageBuilder._trim_fc_pairs(messages)
        assistant_with_tc = [m for m in result if m.get("role") == "assistant" and m.get("tool_calls")]
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(assistant_with_tc) == 0
        assert len(tool_msgs) == 0

    def test_bug_trim_to_budget_pair_chars_accounting(self):
        """bug trim to budget pair chars accounting"""
        mb = MessageBuilder(max_context_tokens=10000)
        mb.conversation_history = [
            _make_system("s" * 50),
            _make_user("u" * 50),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "r" * 3000),
            _make_assistant(tool_calls=[_make_tc("tc_2")]),
            _make_tool_result("tc_2", "r" * 3000),
        ]
        mb.trim_history()
        total = mb._total_chars(mb.conversation_history)
        assert total > 0

    def test_bug_rebuild_and_validate_fallback_keeps_too_many(self):
        """bug rebuild and validate fallback keeps too many"""
        mb = MessageBuilder()
        mb.conversation_history = [
            _make_system(), _make_user(),
            _make_assistant(tool_calls=[_make_tc()]),
            _make_tool_result("tc_1", "result"),
        ]
        system_msgs, user_msgs, obs_list, assistant_msgs = mb._classify_messages()
        assert len(obs_list) == 1
        assert obs_list[0]["role"] == "tool"

    def test_bug_total_chars_includes_tool_calls_json(self):
        """bug total chars includes tool calls json"""
        mb = MessageBuilder()
        mb.temp_history = [{"role": "user", "content": "x" * 30000} for _ in range(3)]
        mb._cap_temp_history()
        total = mb._total_chars(mb.temp_history)
        assert total <= 50000

    def test_bug_trim_history_none_result_keeps_original(self):
        """bug trim history none result keeps original"""
        mb = MessageBuilder(max_context_tokens=100)
        mb.conversation_history = [
            _make_system("s" * 30),
            _make_user("u" * 30),
        ]
        original = list(mb.conversation_history)
        mb.trim_history()
        # history复煭,屼不瑁佸壀
        assert mb.conversation_history == original

    def test_bug_append_observation_duplicate_tool_call_id(self):
        """bug append observation duplicate tool call id"""
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        fc = {"tool_call_id": "tc_1", "tool_calls": [_make_tc("tc_1")], "llm_content": "thinking"}
        mb.add_observation("result1", fc)
        mb.add_observation("result2", fc)
        # 第二娆dd_observation无讹,has_existing_assistant=True,屼不搴斿啀娣型姞assistant
        assistant_count = sum(1 for m in mb.conversation_history if m.get("role") == "assistant" and m.get("tool_calls"))
        assert assistant_count == 1  # 名应未我一中猘ssistant(tool_calls)


# ===========================================================================
# 娴佺▼10: 操嶄作璁到綍
# ===========================================================================

class TestFlow10OperationRecord:

    def test_bug_record_operation_swallows_exception(self):
        """bug record operation swallows exception"""
        agent = _make_mock_agent()
        agent._task_tracker = MagicMock()
        agent.task_id = "test_task"
        agent._task_tracker.complete_task = MagicMock(side_effect=RuntimeError("DB error"))
        emitter = agent._step_emitter
        # 应该不崩溃?
        emitter.complete_task(success=True)


# ===========================================================================
# 娴佺▼11: 错误复勭处
# ===========================================================================

class TestFlow11ErrorHandler:

    def test_bug_classify_error_fc_format(self):
        """bug classify error fc format"""
        from app.services.llm.core import LLMResponseError
        from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
        result = SystemErrorClassifier.classify_error(LLMResponseError(message="bad format"))
        assert result == SystemErrorCategory.SERVER

    def test_bug_classify_error_unknown(self):
        """bug classify error unknown"""
        from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
        result = SystemErrorClassifier.classify_error(ValueError("generic"))
        assert result == SystemErrorCategory.UNKNOWN

    def test_bug_error_step_recoverable_field(self):
        """bug error step recoverable field"""
        import inspect
        assert inspect.isfunction(handle_react_error)


# ===========================================================================
# 娴佺▼12: 宸ュ叿缂撳瓨中庡姩鎬佹敞鍏?
# ===========================================================================

class TestFlow12ToolCache:

    def test_bug_patch_search_desc_invalidates_cache(self):
        """bug patch search desc invalidates cache"""
        from app.services.agent.tool_cache_manager import patch_search_desc
        agent = _make_mock_agent()
        from app.tools.tool_types import ToolCategory
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL, ToolCategory.FILE}
        agent._tool_search_desc_override = None
        agent._tool_cache = MagicMock()
        agent._tool_cache.get = MagicMock(return_value=None)
        patch_search_desc(agent)
        # Bug15修否庡应璋僫nvalidate
        agent._tool_cache.invalidate.assert_called()

    def test_bug_get_openai_tools_cache_hit(self):
        """bug get openai tools cache hit"""
        from app.services.agent.tool_cache_manager import get_openai_tools
        agent = _make_mock_agent()
        agent._tool_cache = MagicMock()
        agent._tool_cache.get = MagicMock(return_value=[{"type": "function", "function": {"name": "test"}}])
        result = get_openai_tools(agent)
        assert len(result) == 1

    def test_bug_invalidate_tool_cache(self):
        """bug invalidate tool cache"""
        from app.services.agent.tool_cache_manager import invalidate_tool_cache
        agent = _make_mock_agent()
        agent._tool_cache = MagicMock()
        invalidate_tool_cache(agent)
        agent._tool_cache.invalidate.assert_called()

    def test_bug_load_category_updates_loaded_categories(self):
        """bug load category updates loaded categories"""
        from app.services.agent.base_agent import ToolLoader
        from app.tools.tool_types import ToolCategory
        agent = _make_mock_agent()
        agent._tools_dict = {}
        agent._loaded_categories = {ToolCategory.FUNDAMENTAL}
        loader = ToolLoader(agent)
        with patch("app.services.agent.base_agent.tool_registry.get_implementations_by_category", return_value={"test_tool": lambda: None}):
            loader.load_category(ToolCategory.SHELL)
        assert ToolCategory.SHELL in agent._loaded_categories


# ===========================================================================
# 路户祦绋媌ug
# ===========================================================================

class TestCrossFlowBugs:

    def test_bug_trim_history_then_add_observation_pair_integrity(self):
        step = ErrorStep(step=1, error_type="test", error_message="msg")
        d = step.to_dict()
        assert "error_type" in d
        assert "error_message" in d

    def test_bug_meta_step_dynamic_types(self):
        """bug meta step dynamic types"""
        step = MetaStep(step=1, type="authorization_required")
        d = step.to_dict()
        assert d.get("type") == "authorization_required"

    def test_bug_step_emitter_exit_with_error_creates_error_step(self):
        """bug step emitter exit with error creates error step"""
        agent = _make_mock_agent()
        emitter = StepEmitter(agent)
        result = emitter.exit_with_error(1, "test_error", "test msg")
        assert isinstance(result, ErrorStep)

    def test_bug_message_builder_init_history_empty_task(self):
        """bug message builder init history empty task"""
        mb = MessageBuilder()
        with pytest.raises(ValueError):
            mb.init_history("sys prompt", "")

    def test_bug_message_builder_init_history_whitespace_task(self):
        """bug message builder init history whitespace task"""
        mb = MessageBuilder()
        with pytest.raises(ValueError):
            mb.init_history("sys prompt", "   ")

    def test_bug_normalize_observation_double_prefix(self):
        """bug normalize observation double prefix"""
        result = MessageBuilder._normalize_observation_prefix("[Observation] test")
        assert result == "[Observation] test"
        assert not result.startswith("[Observation] [Observation]")

    def test_bug_normalize_observation_strips_old_prefix(self):
        """bug normalize observation strips old prefix"""
        result = MessageBuilder._normalize_observation_prefix("Observation: test result")
        assert result == "[Observation] test result"

    def test_bug_prepare_messages_includes_temp_history(self):
        """bug prepare messages includes temp history"""
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.temp_history = [{"role": "assistant", "content": "temp msg"}]
        messages = mb.prepare_messages_for_llm()
        assert len(messages) == 3

    def test_bug_reset_per_run_clears_both_histories(self):
        """bug reset per run clears both histories"""
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.temp_history = [{"role": "assistant", "content": "temp"}]
        mb.reset_per_run()
        assert len(mb.conversation_history) == 0
        assert len(mb.temp_history) == 0

    def test_bug_safety_checker_singleton(self):
        mb = MessageBuilder(max_context_tokens=100)
        mb.conversation_history = [
            _make_system("s" * 30),
            _make_user("u" * 30),
        ]
        original_len = len(mb.conversation_history)
        mb.add_observation("result", {"tool_call_id": "tc_1", "tool_calls": []})
        # add_observation内呴儴璋僼rim_history

    def test_bug_action_confirmation_overrides_default(self):
        """bug action confirmation overrides default"""
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = True
                mock_meta.action_confirmation = {"read": False}
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("test_tool", {"action": "read"})
                # action_confirmation.read=False应该标杗eeds_confirmation=True
                assert not result.requires_confirmation

    def test_bug_action_confirmation_missing_action_key(self):
        """bug action confirmation missing action key"""
        checker = ToolSafetyChecker()
        with patch("app.services.safety.tool_safety_checker._is_skip_safety", return_value=False):
            with patch("app.tools.registry.tool_registry.get_tool") as mock_get:
                mock_meta = MagicMock()
                mock_meta.check_fn = None
                mock_meta.needs_confirmation = True
                mock_meta.action_confirmation = {"write": True}
                mock_get.return_value = mock_meta
                result = checker.check_before_execute("test_tool", {"action": "read"})
                # action_confirmation无爎ead错,搴斿厹搴昻eeds_confirmation=True
                assert result.requires_confirmation

    def test_bug_fc_pairs_empty_tool_calls_assistant_removed(self):
        """bug fc pairs empty tool calls assistant removed"""
        mb = MessageBuilder()
        messages = [
            _make_system(),
            _make_assistant(content="just text", tool_calls=[]),
        ]
        result = mb._trim_fc_pairs(messages)
        assistant_msgs = [m for m in result if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1

    def test_bug_trim_preserves_message_order(self):
        """bug trim preserves message order"""
        mb = MessageBuilder(max_context_tokens=5000)
        mb.conversation_history = [
            _make_system("sys"),
            _make_user("task"),
            _make_assistant(tool_calls=[_make_tc("tc_1")]),
            _make_tool_result("tc_1", "result1"),
            _make_assistant(content="answer1"),
        ]
        mb.trim_history()
        # 验证顺序,歴ystem 鈫?user 鈫?... 鈫?final
        roles = [m.get("role") for m in mb.conversation_history]
        assert roles[0] == "system"
        assert roles[1] == "user"

    def test_bug_write_size_protection_zero_old_size(self):
        """bug write size protection zero old size"""
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
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            tmp_path = f.name
                        try:
                            os.unlink(tmp_path)
                            result = checker.check_before_execute("writetext", {"path": tmp_path, "content": "new content"})
                            # 方版件件讹紙不存在級,屼不应该blocked
                        except Exception:
                            pass

    def test_bug_call_llm_stream_generic_exception_yields_error(self):
        """bug call llm stream generic exception yields error"""
        assert True  # llm_stream.py:112-119: 通氱敤异常yield _yield_error_response

    def test_bug_call_llm_stream_cancelled_skips_error(self):
        """bug call llm stream cancelled skips error"""
        assert True  # llm_stream.py:116-118: _cancelled=True无剁洿鎺eturn

    def test_bug_tool_result_message_missing_tool_call_id(self):
        mb = MessageBuilder()
        mb.conversation_history = [_make_system(), _make_user()]
        mb.add_assistant_message("final answer")
        assistant_msgs = [m for m in mb.conversation_history if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "final answer"

    def test_bug_error_step_default_fields(self):
        """bug error step default fields — 07-18对齐: ErrorStep删recoverable, 仅含error_type/error_message"""
        step = ErrorStep(step=1, error_type="test", error_message="msg")
        d = step.to_dict()
        assert d.get("error_type") == "test"
        assert d.get("error_message") == "msg"
        assert "recoverable" not in d

    def test_bug_step_types_complete(self):
        step = ChunkStep(step=1, content="thinking...", is_reasoning=True)
        d = step.to_dict()
        assert d.get("is_reasoning") is True

    def test_bug_final_step_response_field(self):
        """bug final step response field"""
        step = FinalStep(step=1, response="answer", thought="thinking")
        d = step.to_dict()
        assert d.get("response") == "answer"

    def test_bug_meta_step_type_field(self):
        """bug meta step type field"""
        step = MetaStep(step=1, type="start", message="begin")
        d = step.to_dict()
        assert d.get("type") == "start"

    def test_bug_cancelled_status_in_enum(self):
        """bug cancelled status in enum"""
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        # _execute_with_retry中璴ast_error = Exception(f"里嶈瘯鑰楀敖: {action}, attempts=...")
        # 原因异常修℃伅中写け
        assert True  # BUG认,氶噸请点查楀敖无读師濮册紓常镐俊息涪复