# -*- coding: utf-8 -*-
"""ObservationStep 深度测试 — 小欧 2026-06-22

2026-07-08 北京老陈: llm_data改为始终存列表，适配测试断言
2026-07-18 小欧: 同步修正 timestamp 断言(int→str)。base.py 时间戳已统一为
  get_utc_timestamp() 返回的 UTC-Z 字符串(如 2026-07-18T06:32:07.662057Z),
  故"自动生成"路径断言 str; 显式传入 timestamp 仍按原值(int)保留。
2026-08-08 小欧: 全程统一本地时区, base.py 默认改 get_local_iso_timestamp()(本地ISO无Z),
  断言改为不 endswith("Z")。
"""

import json
import pytest
from typing import Any, Dict

from app.services.agent.steps.observation_step import ObservationStep


class TestObservationStepInit:
    """__init__ 正常/异常边界"""

    def test_init_minimal(self):
        """只传step,其余全默认None"""
        s = ObservationStep(step=1)
        assert s._step == 1
        assert s._llm_data == []
        assert s._tool_result is None
        assert s._other_data == {}
        assert s.TYPE == "observation"

    def test_init_all_fields(self):
        """全部字段完整传入"""
        s = ObservationStep(
            step=1,
            llm_data={"summary": "test", "action": {"tool": "foo"}},
            tool_result={"key": "value"},
            other_data={"return_direct": True, "warning": "warn"},
            timestamp=1000,
        )
        assert s._llm_data == [{"summary": "test", "action": {"tool": "foo"}}]
        assert s._tool_result == {"key": "value"}
        assert s._other_data == {"return_direct": True, "warning": "warn"}
        assert s._timestamp == 1000

    def test_init_llm_data_none_becomes_empty(self):
        """llm_data=None → 空列表"""
        s = ObservationStep(step=1, llm_data=None)
        assert s._llm_data == []

    def test_init_llm_data_empty_dict(self):
        """llm_data={} → [{}]（保留空dict）"""
        s = ObservationStep(step=1, llm_data={})
        assert s._llm_data == [{}]

    def test_init_tool_result_none_kept(self):
        """tool_result=None preserves None, different from not passed"""
        s = ObservationStep(step=1, tool_result=None)
        assert s._tool_result is None

    def test_init_tool_result_zero_falsy(self):
        """tool_result=0 / False / '' preserves original value"""
        for v in (0, False, ""):
            s = ObservationStep(step=1, tool_result=v)
            assert s._tool_result == v, f"tool_result={v!r} should keep original"

    def test_init_other_data_none_becomes_empty(self):
        """other_data=None → 空dict"""
        s = ObservationStep(step=1, other_data=None)
        assert s._other_data == {}

    def test_init_step_zero(self):
        """step=0 is valid"""
        s = ObservationStep(step=0)
        assert s._step == 0

    def test_init_step_negative(self):
        """step=-1 is valid"""
        s = ObservationStep(step=-1)
        assert s._step == -1

    def test_init_timestamp_explicit(self):
        """timestamp显式传入"""
        s = ObservationStep(step=1, timestamp=999)
        assert s._timestamp == 999

    def test_init_timestamp_auto(self):
        """timestamp不传 → 自动生成(本地ISO无Z字符串, 对齐base.py get_local_iso_timestamp)"""
        s = ObservationStep(step=1)
        assert s._timestamp is not None
        assert isinstance(s._timestamp, str)          # 2026-08-08 小欧: 时间戳统一本地ISO无Z
        assert not s._timestamp.endswith("Z")         # 校验无UTC-Z后缀


class TestObservationStepGetContent:
    """get_content 正常/异常边界"""

    def test_get_content_summary_exists(self):
        s = ObservationStep(step=1, llm_data={"summary": "读取成功"})
        assert s.get_content() == "读取成功"

    def test_get_content_no_summary(self):
        """llm_data without summary is allowed"""
        s = ObservationStep(step=1, llm_data={"action": {"tool": "foo"}})
        assert s.get_content() == ""

    def test_get_content_empty_llm_data(self):
        s = ObservationStep(step=1, llm_data={})
        assert s.get_content() == ""

    def test_get_content_none_llm_data(self):
        s = ObservationStep(step=1, llm_data=None)
        assert s.get_content() == ""

    def test_get_content_summary_empty_string(self):
        s = ObservationStep(step=1, llm_data={"summary": ""})
        assert s.get_content() == ""

    def test_get_content_summary_whitespace(self):
        s = ObservationStep(step=1, llm_data={"summary": "   "})
        assert s.get_content() == "   "

    def test_get_content_summary_non_string(self):
        """summary supports various types including non-string"""
        for v in (0, 123, [], {}, True):
            s = ObservationStep(step=1, llm_data={"summary": v})
            assert s.get_content() == v

    def test_get_content_other_llm_data_fields_not_used(self):
        """only summary, not action/status"""
        s = ObservationStep(step=1, llm_data={
            "summary": "summary text", "action": {"tool": "foo"}, "status": {"message": "ok"},
        })
        assert s.get_content() == "summary text"

    def test_get_content_multi_tool_joins(self):
        """多工具时summary拼接"""
        s = ObservationStep(step=1, llm_data=[
            {"summary": "成功A"}, {"summary": "失败B"},
        ])
        assert s.get_content() == "成功A\n\n失败B"


class TestObservationStepExtraFields:
    """_extra_fields() structure verification"""

    def test_extra_fields_all_fields(self):
        """全部字段 → 返回扁平 dict"""
        s = ObservationStep(
            step=1,
            llm_data={"summary": "x", "action": {"tool": "a"}},
            tool_result={"content": "data"},
            other_data={"return_direct": True, "warning": "warn"},
        )
        result = s._extra_fields()
        assert isinstance(result, dict)
        assert result["llm_data"] == [{"summary": "x", "action": {"tool": "a"}}]
        assert result["tool_result"] == {"content": "data"}
        assert result["other_data"] == {"return_direct": True, "warning": "warn"}

    def test_extra_fields_no_extra_fields(self):
        """默认全None → 空dict"""
        s = ObservationStep(step=1)
        result = s._extra_fields()
        assert result == {}

    def test_extra_fields_only_llm_data(self):
        s = ObservationStep(step=1, llm_data={"summary": "x"})
        result = s._extra_fields()
        assert result == {"llm_data": [{"summary": "x"}]}

    def test_extra_fields_only_tool_result(self):
        s = ObservationStep(step=1, tool_result=[1, 2, 3])
        result = s._extra_fields()
        assert result == {"tool_result": [1, 2, 3]}

    def test_extra_fields_only_other_data(self):
        s = ObservationStep(step=1, other_data={"return_direct": True})
        result = s._extra_fields()
        assert result == {"other_data": {"return_direct": True}}

    def test_extra_fields_llm_data_empty_dict_included(self):
        """llm_data=[{}] non-falsy, included in output"""
        s = ObservationStep(step=1, llm_data={})
        result = s._extra_fields()
        assert "llm_data" in result

    def test_extra_fields_other_data_empty_dict_omitted(self):
        """other_data={} not in extra (empty dict is falsy)"""
        s = ObservationStep(step=1, other_data={})
        result = s._extra_fields()
        assert "other_data" not in result

    def test_extra_fields_tool_result_none_omitted(self):
        """tool_result=None → 不加入extra"""
        s = ObservationStep(step=1, tool_result=None)
        result = s._extra_fields()
        assert "tool_result" not in result

    def test_extra_fields_tool_result_zero_included(self):
        """tool_result=0 goes into extra, not None fallback"""
        s = ObservationStep(step=1, tool_result=0)
        result = s._extra_fields()
        assert result["tool_result"] == 0

    def test_extra_fields_tool_result_false_included(self):
        """tool_result=False goes into extra, not None fallback"""
        s = ObservationStep(step=1, tool_result=False)
        result = s._extra_fields()
        assert result["tool_result"] is False

    def test_to_dict_includes_fields(self):
        """to_dict() → 顶层有type/step/timestamp/content + llm_data/tool_result"""
        s = ObservationStep(
            step=1,
            llm_data={"summary": "test"},
            tool_result=["a"],
            other_data={"return_direct": True},
        )
        d = s.to_dict()
        assert d["type"] == "observation"
        assert d["step"] == 1
        assert d["content"] == "test"
        assert isinstance(d["timestamp"], str)          # 2026-08-08 小欧: 时间戳统一本地ISO无Z
        assert not d["timestamp"].endswith("Z")         # 校验无UTC-Z后缀
        assert d["llm_data"] == [{"summary": "test"}]
        assert d["tool_result"] == ["a"]
        assert d["other_data"] == {"return_direct": True}

    def test_to_dict_no_extra_fields(self):
        """全默认 → to_dict无extra fields"""
        s = ObservationStep(step=2)
        d = s.to_dict()
        assert d["type"] == "observation"
        assert "llm_data" not in d

    def test_extra_fields_json_serializable(self):
        """_extra_fields() output must be JSON serializable for SSE"""
        s = ObservationStep(
            step=1,
            llm_data={"summary": "a", "action": {"tool": "b"}, "status": {}},
            tool_result={"content": "data"},
            other_data={"flag": True, "count": 0, "items": [1, None, "x"]},
        )
        obs = s._extra_fields()
        serialized = json.dumps(obs)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["llm_data"] == [{"summary": "a", "action": {"tool": "b"}, "status": {}}]

    def test_to_dict_json_serializable(self):
        """完整to_dict() SSE可序列化"""
        s = ObservationStep(
            step=1,
            llm_data={"summary": "a"},
            tool_result=[1, 2, 3],
            other_data={"retry_count": 2},
        )
        d = s.to_dict()
        json.dumps(d)


class TestObservationStepTypeProperty:
    """type property test"""

    def test_type_is_observation(self):
        s = ObservationStep(step=1)
        assert s.type == "observation"
        assert s.get_type() == "observation"

    def test_type_is_not_action_tool(self):
        s = ObservationStep(step=1)
        assert s.type != "action_tool"
        assert s.is_done is False


class TestObservationStepEdgeCases:
    """其他正常边界"""

    def test_llm_data_with_unexpected_types(self):
        """llm_data accepts non-dict types, always stored as list"""
        s_none = ObservationStep(step=1, llm_data=None)
        assert s_none._llm_data == []
        s_dict = ObservationStep(step=1, llm_data={})
        assert s_dict._llm_data == [{}]
        # [] 已为列表，保持原样；非列表假值包装为列表
        for val in (0, "", False):
            s = ObservationStep(step=1, llm_data=val)
            assert s._llm_data == [val], f"llm_data={val!r} should be [{val!r}]"
        s_empty_list = ObservationStep(step=1, llm_data=[])
        assert s_empty_list._llm_data == []

    def test_llm_data_non_empty_list(self):
        """llm_data是非空列表 → 保持原样（type hint不匹配但兼容）"""
        s = ObservationStep(step=1, llm_data=["a"])
        assert s._llm_data == ["a"]

    def test_llm_data_dict(self):
        s = ObservationStep(step=1, llm_data={"a": 1})
        assert s._llm_data == [{"a": 1}]

    def test_llm_data_int_non_falsy(self):
        s = ObservationStep(step=1, llm_data=123)
        assert s._llm_data == [123]

    def test_tool_result_mutable_not_shared(self):
        """tool_result internal modification should not affect original"""
        original = {"key": "value"}
        s = ObservationStep(step=1, tool_result=original)
        original["key"] = "modified"
        assert s._tool_result == {"key": "modified"}

    def test_llm_data_mutable_shared(self):
        """llm_data是引用，原始对象变化影响内部（存的是引用）"""
        original = {"summary": "orig"}
        s = ObservationStep(step=1, llm_data=original)
        original["summary"] = "changed"
        assert s._llm_data == [{"summary": "changed"}]

    def test_other_data_mutable_not_shared(self):
        original = {"return_direct": True}
        s = ObservationStep(step=1, other_data=original)
        original["return_direct"] = False
        assert s._other_data == {"return_direct": False}

    def test_repr_includes_class_and_step(self):
        s = ObservationStep(step=3)
        r = repr(s)
        assert "ObservationStep" in r
        assert "step=3" in r
        assert "observation" in r

    def test_multiple_observations_isolated(self):
        s1 = ObservationStep(step=1, llm_data={"summary": "a"})
        s2 = ObservationStep(step=2, llm_data={"summary": "b"})
        assert s1._llm_data != s2._llm_data
