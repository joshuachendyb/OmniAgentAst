# -*- coding: utf-8 -*-
"""ActionStep 深度测试 鈥?小欧 2026-06-22"""

import json
import pytest
from typing import Any, Dict

from app.services.agent.steps.action_step import ActionStep


class TestActionStepInit:
    """__init__ 输照晫/异常在写櫙"""

    def test_init_minimal(self):
        s = ActionStep(step=1, tool_name="test_tool", tool_params={"arg": "val"})
        assert s._step == 1
        assert s._tool_name == "test_tool"
        assert s._tool_params == {"arg": "val"}
        assert s._execution_status == "success"
        assert s._execution_result is None
        assert s._action_retry_count == 0
        assert s._execution_time_ms == 0
        assert s.TYPE == "action_tool"

    def test_init_all_fields(self):
        s = ActionStep(
            step=2,
            tool_name="read_file",
            tool_params={"path": "/a"},
            execution_status="error",
            execution_result={"data": "content"},
            action_retry_count=3,
            execution_time_ms=1500,
            timestamp=8888,
        )
        assert s._tool_name == "read_file"
        assert s._execution_status == "error"
        assert s._execution_result == {"data": "content"}
        assert s._action_retry_count == 3
        assert s._execution_time_ms == 1500
        assert s._timestamp == 8888

    def test_init_step_zero_or_negative(self):
        for step in (0, -1, -999):
            s = ActionStep(step=step, tool_name="t", tool_params={})
            assert s._step == step

    def test_init_tool_name_empty_string(self):
        s = ActionStep(step=1, tool_name="", tool_params={})
        assert s._tool_name == ""

    def test_init_tool_params_empty(self):
        s = ActionStep(step=1, tool_name="t", tool_params={})
        assert s._tool_params == {}

    def test_init_execution_result_none(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_result=None)
        assert s._execution_result is None

    def test_init_execution_result_empty_dict(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_result={})
        assert s._execution_result == {}


class TestActionStepGetContent:
    """get_content 鈥?濮嬬粓返回空哄瓧第︿覆"""

    def test_get_content_empty(self):
        s = ActionStep(step=1, tool_name="t", tool_params={})
        assert s.get_content() == ""

    def test_get_content_with_result(self):
        """鍗充究未塭xecution_result涔熻繑回炵┖"""
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_result={"data": "x"})
        assert s.get_content() == ""

    def test_get_content_error_status(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status="error")
        assert s.get_content() == ""


class TestActionStepIsError:
    """is_error 输照晫在写櫙"""

    def test_is_error_false_by_default(self):
        s = ActionStep(step=1, tool_name="t", tool_params={})
        assert s.is_error is False

    def test_is_error_true_when_error(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status="error")
        assert s.is_error is True

    def test_is_error_false_for_success(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status="success")
        assert s.is_error is False

    def test_is_error_false_for_warning(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status="warning")
        assert s.is_error is False

    def test_is_error_case_sensitive(self):
        """复у写/棣栧瓧姣崩ぇ内?鈫?中嶈中写是error"""
        for status in ("Error", "ERROR", "eRrOr"):
            s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status=status)
            assert s.is_error is False, f"execution_status={status!r} 应该繑回濬alse"

    def test_is_error_empty_status(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_status="")
        assert s.is_error is False


class TestActionStepExtraFields:
    """_extra_fields() 结撴瀯标￠獙"""

    def test_extra_fields_full(self):
        s = ActionStep(
            step=1, tool_name="my_tool", tool_params={"a": 1},
            execution_status="success", execution_result={"data": "x"},
            action_retry_count=2, execution_time_ms=500,
        )
        ef = s._extra_fields()
        assert ef == {
            "tool_name": "my_tool",
            "tool_params": {"a": 1},
            "execution_status": "success",
            "execution_result": {"data": "x"},
            "action_retry_count": 2,
            "execution_time_ms": 500,
        }

    def test_extra_fields_tool_name_empty(self):
        s = ActionStep(step=1, tool_name="", tool_params={})
        ef = s._extra_fields()
        assert ef["tool_name"] == ""

    def test_extra_fields_tool_name_none_fallthrough(self):
        """标墠tool_name是痵tr类型,屼不名兘是疦one銆有试请曠┖存楃中插洖通查"""
        s = ActionStep(step=1, tool_name="", tool_params={})
        assert s._extra_fields()["tool_name"] == ""

    def test_extra_fields_execution_result_none(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_result=None)
        assert s._extra_fields()["execution_result"] is None

    def test_to_dict_includes_action_tool_fields(self):
        s = ActionStep(
            step=1, tool_name="t", tool_params={"p": 1},
            execution_status="success", execution_result={"data": "x"},
        )
        d = s.to_dict()
        assert d["type"] == "action_tool"
        assert d["step"] == 1
        assert d["content"] == ""
        assert d["tool_name"] == "t"
        assert d["tool_params"] == {"p": 1}
        assert d["execution_status"] == "success"
        assert d["execution_result"] == {"data": "x"}

    def test_to_dict_json_serializable(self):
        s = ActionStep(
            step=1, tool_name="a", tool_params={"b": 2},
            execution_result=[1, 2, 3],
        )
        json.dumps(s.to_dict())

    def test_to_dict_not_have_observation_key(self):
        """ActionStep to_dict should not contain observation key"""
        s = ActionStep(step=1, tool_name="t", tool_params={})
        d = s.to_dict()
        assert "observation" not in d


class TestActionStepTypeProperty:
    def test_type(self):
        s = ActionStep(step=1, tool_name="t", tool_params={})
        assert s.type == "action_tool"
        assert s.get_type() == "action_tool"


class TestActionStepEdgeCases:
    def test_retry_count_big(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, action_retry_count=9999)
        assert s._action_retry_count == 9999

    def test_execution_time_ms_big(self):
        s = ActionStep(step=1, tool_name="t", tool_params={}, execution_time_ms=86400000)
        assert s._execution_time_ms == 86400000

    def test_tool_params_mutation_after_init(self):
        original = {"key": "val"}
        s = ActionStep(step=1, tool_name="t", tool_params=original)
        original["key"] = "changed"
        assert s._tool_params["key"] == "changed"

    def test_repr(self):
        s = ActionStep(step=2, tool_name="my_tool", tool_params={"a": 1})
        r = repr(s)
        assert "ActionStep" in r
        assert "step=2" in r
        assert "action_tool" in r
