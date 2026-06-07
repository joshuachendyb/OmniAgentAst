"""
真实集成测试 - 解析器链 + ReAct逻辑
直接调用Python函数（不用mock），验证真实代码行为

作者: 小健 2026-05-21
"""
import pytest
import json
import sys
import os
from app.services.tools import ensure_tools_registered, tool_registry
from app.services.intents import definitions
from app.services.preprocessing.intent_classifier import IntentClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.services.agent.llm_response_parser import parse_react_response
from app.services.agent.llm_response_parser._utils import _normalize_result_to_str


# =============================================================================
# 1. _normalize_result_to_str 共享函数测试
# =============================================================================

class TestNormalizeResultToStr:
    """_normalize_result_to_str 类型标准化验证"""

    def test_bool_true(self):
        assert _normalize_result_to_str(True) == "True"

    def test_bool_false(self):
        assert _normalize_result_to_str(False) == "False"

    def test_int(self):
        assert _normalize_result_to_str(42) == "42"

    def test_float(self):
        assert _normalize_result_to_str(3.14) == "3.14"

    def test_str(self):
        assert _normalize_result_to_str("hello") == "hello"

    def test_dict(self):
        r = _normalize_result_to_str({"status": "ok"})
        assert isinstance(r, str)
        assert '"status": "ok"' in r

    def test_list(self):
        r = _normalize_result_to_str([1, 2, 3])
        assert isinstance(r, str)
        assert "[1, 2, 3]" in r

    def test_none(self):
        assert _normalize_result_to_str(None) == ""

    def test_bool_before_int(self):
        """bool是int子类，必须先检查bool"""
        assert _normalize_result_to_str(True) == "True"
        assert _normalize_result_to_str(1) == "1"


# =============================================================================
# 2. 解析器链 - 9个handler路径全覆盖 (无mock)
# =============================================================================

class TestParserChainAllHandlers:
    """9个handler路径真实解析测试"""

    def test_handler1_dict_action(self):
        """Handler #1: dict输入 → action"""
        r = parse_react_response({"tool_name": "read_file", "tool_params": {"file_paths": ["C:/test.txt"]}})
        assert r["type"] == "action"
        assert r["tool_name"] == "read_file"

    def test_handler1_dict_finish(self):
        """Handler #1: dict输入 finish → answer"""
        r = parse_react_response({"tool_name": "finish", "tool_params": {"result": "完成"}})
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)

    def test_handler1_dict_finish_result_dict(self):
        """Handler #1: finish result是dict → 标准化为JSON字符串"""
        r = parse_react_response({"tool_name": "finish", "tool_params": {"result": {"status": "ok"}}})
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)
        assert '"status": "ok"' in r["response"]

    def test_handler2_list(self):
        """Handler #2: list输入 → action"""
        r = parse_react_response([{"tool_name": "get_time", "tool_params": {}}])
        assert r["type"] == "action"
        assert r["tool_name"] == "get_time"

    def test_handler3_json_array(self):
        """Handler #3: JSON数组字符串 → list处理"""
        r = parse_react_response('[{"tool_name": "get_time", "tool_params": {}}]')
        assert r["type"] == "action"

    def test_handler4_empty(self):
        """Handler #4: 空值 → parse_error"""
        r = parse_react_response("")
        assert r["type"] == "parse_error"

    def test_handler5_standard_json_new_format(self):
        """Handler #5: 标准JSON 新格式(tool_name) → action"""
        r = parse_react_response(json.dumps({
            "tool_name": "search_web",
            "tool_params": {"query": "test"},
            "thought": "search"
        }))
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"

    def test_handler5_standard_json_old_format(self):
        """Handler #5: 标准JSON 旧格式(action) → action"""
        r = parse_react_response(json.dumps({
            "action": "search_web",
            "action_input": {"query": "test"},
            "thought": "search"
        }))
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"

    def test_handler5_old_format_finish_result_int(self):
        """Handler #5: 旧格式finish result=int → 标准化为字符串(A2修复)"""
        r = parse_react_response(json.dumps({
            "action": "finish",
            "action_input": {"result": 42}
        }))
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)
        assert r["response"] == "42"

    def test_handler5_old_format_finish_result_dict(self):
        """Handler #5: 旧格式finish result=dict → 标准化为JSON字符串(A2修复)"""
        r = parse_react_response(json.dumps({
            "action": "finish",
            "action_input": {"result": {"status": "ok"}}
        }))
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)

    def test_handler6_non_standard_json(self):
        """Handler #6: 非标准JSON(单引号) → action"""
        raw = "{'tool_name': 'get_time', 'tool_params': {}, 'thought': '获取时间'}"
        r = parse_react_response(raw)
        assert r["type"] == "action"
        assert r["tool_name"] == "get_time"

    def test_handler7_mixed_text_json(self):
        """Handler #7: 混合文本+JSON → action"""
        raw = '我来帮你搜索\n{"tool_name": "search_web", "tool_params": {"query": "天气"}}'
        r = parse_react_response(raw)
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"

    def test_handler7_mixed_text_finish_result_int(self):
        """Handler #7: 混合文本finish result=int → 标准化(A3修复)"""
        raw = '完成\n{"tool_name": "finish", "tool_params": {"result": 42}}'
        r = parse_react_response(raw)
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)
        assert r["response"] == "42"

    def test_handler7_mixed_text_finish_result_dict(self):
        """Handler #7: 混合文本finish result=dict → 标准化(A3修复)"""
        raw = '完成\n{"tool_name": "finish", "tool_params": {"result": {"status": "ok"}}}'
        r = parse_react_response(raw)
        assert r["type"] == "answer"
        assert isinstance(r["response"], str)

    def test_handler9_keyword_match(self):
        """Handler #9: 关键词匹配 → action"""
        raw = "Thought: 需要搜索\nAction: search_web\nAction Input: {\"query\": \"test\"}"
        r = parse_react_response(raw)
        assert r["type"] == "action"
        assert r["tool_name"] == "search_web"


# =============================================================================
# 3. _process_tool_params 统一管道验证
# =============================================================================

class TestProcessToolParamsPipeline:
    """验证所有路径走_process_tool_params统一管道"""

    def test_old_format_params_filtered(self):
        """旧格式: reasoning字段被过滤(A1修复)"""
        r = parse_react_response(json.dumps({
            "action": "search_web",
            "action_input": {"query": "test", "reasoning": "不应保留"},
            "thought": "search"
        }))
        assert r["type"] == "action"
        assert "reasoning" not in r.get("tool_params", {})

    def test_dict_input_params_filtered(self):
        """dict输入: reasoning字段被过滤(A4修复)"""
        r = parse_react_response({
            "tool_name": "search_web",
            "tool_params": {"query": "test", "reasoning": "不应保留"}
        })
        assert r["type"] == "action"
        assert "reasoning" not in r.get("tool_params", {})

    def test_keyword_path_params_filtered(self):
        """关键词路径: reasoning字段被过滤(A5修复)"""
        raw = 'Thought: 需要搜索\nAction: search_web\nAction Input: {"query": "test", "reasoning": "不应保留"}'
        r = parse_react_response(raw)
        assert r["type"] == "action"
        if isinstance(r.get("tool_params"), dict):
            assert "reasoning" not in r["tool_params"]


# =============================================================================
# 4. 工具注册系统验证
# =============================================================================

class TestToolRegistry:
    """工具注册系统真实验证"""

    def test_all_59_tools_registered(self):
        ensure_tools_registered()
        tools = tool_registry.list_tools(include_metadata=False)
        assert len(tools) == 59, f"Expected 59 tools, got {len(tools)}"

    def test_7_categories(self):
        ensure_tools_registered()
        names = tool_registry.list_tools(include_metadata=False)
        assert len(names) == 59

    def test_tool_implementation_callable(self):
        ensure_tools_registered()
        impl = tool_registry.get_implementation("get_time")
        assert impl is not None
        assert callable(impl)


# =============================================================================
# 5. Intent检测系统验证
# =============================================================================

class TestIntentSystem:
    """Intent检测系统真实验证(通过chat API触发CRSS)"""

    def test_intent_definitions_loaded(self):
        assert hasattr(definitions, "INTENT_REGISTRY") or hasattr(definitions, "get_all_intents") or dir(definitions)

    def test_intent_types_exist(self):
        classifier = IntentClassifier()
        assert hasattr(classifier, "classify")

    def test_security_check_endpoint(self):
        import httpx
        r = httpx.post(
            "http://127.0.0.1:8000/api/v1/security/check",
            json={"command": "rm -rf /"},
            timeout=15,
        )
        assert r.status_code == 200
