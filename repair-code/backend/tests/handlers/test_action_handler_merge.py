# -*- coding: utf-8 -*-
"""action_handler merge出芥暟 深度测试 鈥?小欧 2026-06-22

测试标目:
  - _merge_llm_data: 骞惰在写櫙llm_data否堝苟,堟寜严重绋册害鎺掑簭,?  - _merge_other_data: 骞惰在写櫙other_data否堝苟,坵arning/attachment/return_direct,?"""

import pytest
from typing import Any, Dict, List

from app.services.agent.handlers.action_handler import (
    _merge_llm_data,
    _merge_other_data,
)


# ============================================================
# _merge_llm_data
# ============================================================

class TestMergeLlmData:
    """_merge_llm_data 深度测试"""

    def test_empty_list(self):
        assert _merge_llm_data([]) == {}

    def test_single_entry(self):
        data = [{"summary": "x", "action": {"tool": "a"}, "status": {"exec_code": "success"}}]
        assert _merge_llm_data(data) == data[0]

    def test_single_entry_returns_same_ref(self):
        """merge simple two items"""
        data = [{"summary": "test"}]
        merged = _merge_llm_data(data)
        assert merged is data[0]

    def test_multiple_entries_merges_summary(self):
        data = [
            {"summary": "first_item", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 100, "metrics": {"lines": {"value": 10}}},
            {"summary": "second_item", "action": {"tool": "b"}, "status": {"exec_code": "success"}, "duration_ms": 200, "metrics": {"bytes": {"value": 100}}},
        ]
        merged = _merge_llm_data(data)
        assert "first_item\n\nsecond_item" == merged["summary"]

    def test_multiple_priority_error_first(self):
        """error severity highest, prefer action/status with error"""
        data = [
            {"summary": "ok", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10},
            {"summary": "err", "action": {"tool": "b"}, "status": {"exec_code": "error", "message": "失败"}, "duration_ms": 20},
            {"summary": "warn", "action": {"tool": "c"}, "status": {"exec_code": "warning"}, "duration_ms": 30},
        ]
        merged = _merge_llm_data(data)
        assert merged["action"]["tool"] == "b"
        assert merged["status"]["exec_code"] == "error"

    def test_multiple_priority_warning_before_success(self):
        """warning > success"""
        data = [
            {"summary": "ok", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10},
            {"summary": "warn", "action": {"tool": "b"}, "status": {"exec_code": "warning"}, "duration_ms": 20},
        ]
        merged = _merge_llm_data(data)
        assert merged["action"]["tool"] == "b"
        assert merged["status"]["exec_code"] == "warning"

    def test_duration_ms_max(self):
        data = [
            {"summary": "a", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 100, "metrics": {}},
            {"summary": "b", "action": {"tool": "b"}, "status": {"exec_code": "success"}, "duration_ms": 300, "metrics": {}},
            {"summary": "c", "action": {"tool": "c"}, "status": {"exec_code": "success"}, "duration_ms": 200, "metrics": {}},
        ]
        merged = _merge_llm_data(data)
        assert merged["duration_ms"] == 300

    def test_metrics_merged_with_tool_prefix(self):
        data = [
            {"summary": "a", "action": {"tool": "read"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {"read": {"value": 10}}},
            {"summary": "b", "action": {"tool": "write"}, "status": {"exec_code": "success"}, "duration_ms": 20, "metrics": {"bytes": {"value": 100, "text": "100存楄妭"}}},
        ]
        merged = _merge_llm_data(data)
        assert "read.read" in merged["metrics"]
        assert "write.bytes" in merged["metrics"]
        assert merged["metrics"]["read.read"] == {"value": 10}
        assert merged["metrics"]["write.bytes"] == {"value": 100, "text": "100存楄妭"}

    def test_metrics_duplicate_names_different_tools(self):
        files_metrics = {"lines": {"value": 15}}
        grep_metrics = {"lines": {"value": 3}}
        data = [
            {"summary": "a", "action": {"tool": "readtext"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": files_metrics},
            {"summary": "b", "action": {"tool": "grep"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": grep_metrics},
        ]
        merged = _merge_llm_data(data)
        assert "readtext.lines" in merged["metrics"]
        assert "grep.lines" in merged["metrics"]

    def test_metrics_from_same_tool_overwrites(self):
        """same tool, same metric -> later overwrites earlier"""
        data = [
            {"summary": "a", "action": {"tool": "tool_x"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {"count": {"value": 1}}},
            {"summary": "b", "action": {"tool": "tool_x"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {"count": {"value": 2}}},
        ]
        merged = _merge_llm_data(data)
        assert merged["metrics"]["tool_x.count"]["value"] == 2

    def test_no_status_key(self):
        """status code dedup prefers higher severity"""
        data = [
            {"summary": "a", "action": {"tool": "a"}, "duration_ms": 10, "metrics": {}},
            {"summary": "b", "action": {"tool": "b"}, "duration_ms": 20, "metrics": {}},
        ]
        merged = _merge_llm_data(data)
        assert "summary" in merged

    def test_status_not_dict(self):
        """status not dict -> .get('exec_code', 'success') returns 'success'"""
        data = [
            {"summary": "a", "action": {"tool": "a"}, "duration_ms": 10, "metrics": {}, "status": "unexpected_string"},
            {"summary": "b", "action": {"tool": "b"}, "duration_ms": 20, "metrics": {}, "status": None},
        ]
        merged = _merge_llm_data(data)
        assert isinstance(merged, dict)

    def test_all_identical_status(self):
        """extra fields merged into observation"""
        data = [
            {"summary": "x", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {}},
            {"summary": "y", "action": {"tool": "b"}, "status": {"exec_code": "success"}, "duration_ms": 20, "metrics": {}},
        ]
        merged = _merge_llm_data(data)
        assert merged["action"]["tool"] == "a"

    def test_unknown_exec_code_lowest_priority(self):
        data = [
            {"summary": "x", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {}},
            {"summary": "y", "action": {"tool": "b"}, "status": {"exec_code": "unknown_code"}, "duration_ms": 20, "metrics": {}},
        ]
        merged = _merge_llm_data(data)
        assert merged["action"]["tool"] == "a"

    def test_metrics_field_missing_from_some(self):
        data = [
            {"summary": "a", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {"x": 1}},
            {"summary": "b", "action": {"tool": "b"}, "status": {"exec_code": "success"}, "duration_ms": 20},
        ]
        merged = _merge_llm_data(data)
        assert "a.x" in merged["metrics"]
        assert "b" not in merged["metrics"]

    def test_unknown_exec_code_treated_as_success(self):
        """exec_code already in severity_order uses its severity"""
        data = [
            {"summary": "a", "action": {"tool": "a"}, "status": {"exec_code": "cancelled"}, "duration_ms": 10, "metrics": {}},
            {"summary": "b", "action": {"tool": "b"}, "status": {"exec_code": "error"}, "duration_ms": 20, "metrics": {}},
        ]
        merged = _merge_llm_data(data)
        assert merged["action"]["tool"] == "b"
        assert merged["status"]["exec_code"] == "error"

    def test_merge_llm_data_none_entry_filtered(self):
        """None value stripped from merged result"""
        data = [
            {"summary": "a", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {}},
            None,
        ]
        merged = _merge_llm_data(data)
        assert merged["summary"] == "a"

    def test_merge_llm_data_non_dict_entry_filtered(self):
        """non-dict attachment stripped from merged result"""
        data = [
            {"summary": "a", "action": {"tool": "a"}, "status": {"exec_code": "success"}, "duration_ms": 10, "metrics": {}},
            "not_a_dict",
        ]
        merged = _merge_llm_data(data)
        assert merged["summary"] == "a"


class TestMergeOtherData:
    """_merge_other_data deep test"""

    def test_empty_list(self):
        assert _merge_other_data([]) == {}

    def test_single_entry(self):
        data = [{"warning": "灏忓績", "return_direct": True, "attachment": "file.txt"}]
        merged = _merge_other_data(data)
        assert merged["warning"] == "灏忓績"
        assert merged["return_direct"] is True
        assert merged["attachment"] == "file.txt"

    def test_single_entry_returns_filtered(self):
        """merge same key different type raises error"""
        data = [{"return_direct": True}]
        merged = _merge_other_data(data)
        assert merged["return_direct"] is True

    def test_multiple_warnings_merged_newline(self):
        data = [
            {"warning": "璀﹀憡A"},
            {"warning": "璀﹀憡B"},
            {"warning": "璀﹀憡C"},
        ]
        merged = _merge_other_data(data)
        assert merged["warning"] == "璀﹀憡A\n\n璀﹀憡B\n\n璀﹀憡C"

    def test_some_warning_none_ignored(self):
        data = [
            {"warning": "璀﹀憡A"},
            {"warning": None},
            {"warning": ""},
        ]
        merged = _merge_other_data(data)
        assert merged["warning"] == "璀﹀憡A"

    def test_warning_missing_key(self):
        data = [
            {"return_direct": True},
            {"warning": "璀﹀憡B"},
        ]
        merged = _merge_other_data(data)
        assert merged["warning"] == "璀﹀憡B"

    def test_multiple_attachments_merged_to_list(self):
        data = [
            {"attachment": "文件A"},
            {"attachment": "文件B"},
            {"attachment": "文件C"},
        ]
        merged = _merge_other_data(data)
        assert merged["attachment"] == ["文件A", "文件B", "文件C"]

    def test_single_attachment_remains_single(self):
        data = [
            {"attachment": "文件A"},
            {"attachment": None},
        ]
        merged = _merge_other_data(data)
        assert merged["attachment"] == "文件A"

    def test_attachment_none_all_ignored(self):
        data = [
            {"attachment": None},
            {"attachment": None},
        ]
        merged = _merge_other_data(data)
        assert "attachment" not in merged

    def test_return_direct_true_wins(self):
        """return_direct=True keeps result as True"""
        data = [
            {"return_direct": False},
            {"return_direct": False},
            {"return_direct": True},
        ]
        merged = _merge_other_data(data)
        assert merged["return_direct"] is True

    def test_return_direct_all_false(self):
        data = [
            {"return_direct": False},
            {"return_direct": False},
        ]
        merged = _merge_other_data(data)
        assert "return_direct" not in merged

    def test_return_direct_mixed_types(self):
        """non-tool truthy value preserved"""
        data = [
            {"return_direct": 0},
            {"return_direct": True},
        ]
        merged = _merge_other_data(data)
        assert merged["return_direct"] is True

    def test_retry_count_first_non_none_wins(self):
        data = [
            {"retry_count": None},
            {"retry_count": 3},
            {"retry_count": 5},
        ]
        merged = _merge_other_data(data)
        assert merged["retry_count"] == 3

    def test_retry_count_all_none(self):
        data = [
            {"retry_count": None},
            {"retry_count": None},
        ]
        merged = _merge_other_data(data)
        assert "retry_count" not in merged

    def test_no_retry_count_key(self):
        data = [
            {"warning": "娉户剰"},
            {"warning": "娉户剰2"},
        ]
        merged = _merge_other_data(data)
        assert "retry_count" not in merged

    def test_unknown_fields_not_in_output(self):
        data = [
            {"unknown_field": "unknown"},
        ]
        merged = _merge_other_data(data)
        assert "unknown_field" not in merged

    def test_all_empty_returns_empty(self):
        data = [{}, {}, {}]
        merged = _merge_other_data(data)
        assert merged == {}

    def test_all_none_in_list(self):
        """merge two items -> returns {}"""
        data = [None, None]
        merged = _merge_other_data(data)
        assert merged == {}

    def test_mixed_none_and_dict(self):
        """None + non-None dict -> normal"""
        data = [None, {"warning": "warning_msg"}, None, {"return_direct": True}]
        merged = _merge_other_data(data)
        assert merged["warning"] == "warning_msg"
        assert merged["return_direct"] is True

    def test_attachment_dict_merged_to_list(self):
        """attachment is list type key promoted"""
        data = [
            {"attachment": {"name": "a.txt"}},
            {"attachment": {"name": "b.txt"}},
        ]
        merged = _merge_other_data(data)
        assert merged["attachment"] == [{"name": "a.txt"}, {"name": "b.txt"}]

    def test_attachment_various_types(self):
        """non-list type attachment preserved"""
        data = [
            {"attachment": "attachment_item"},
            {"attachment": 123},
            {"attachment": ["list"]},
        ]
        merged = _merge_other_data(data)
        assert merged["attachment"] == ["attachment_item", 123, ["list"]]
