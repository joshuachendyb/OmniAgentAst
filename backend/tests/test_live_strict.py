"""
严格深度真实集成测试 - 验证返回值正确性，不只是"不报错"
基于运行中的后台服务(127.0.0.1:8000)，零mock

作者: 小健 2026-05-21
"""
import pytest
import httpx
import json
import os
import tempfile
import time
from app.services.agent.llm_response_parser._utils import _normalize_result_to_str
from app.services.agent.llm_response_parser import parse_react_response

BASE = "http://127.0.0.1:8000/api/v1"


def call_tool(tool_name: str, params: dict, timeout: int = 60) -> dict:
    r = httpx.post(f"{BASE}/tool/execute", json={"tool_name": tool_name, "params": params}, timeout=timeout)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    return r.json()


def get_result(tool_name: str, params: dict, timeout: int = 60) -> dict:
    d = call_tool(tool_name, params, timeout)
    assert d["success"] is True, f"{tool_name} API failed: {d.get('error','')}"
    return d["result"]


def result_data(tool_name: str, params: dict, timeout: int = 60) -> dict:
    res = get_result(tool_name, params, timeout)
    return res.get("data", {})


# =============================================================================
# 1. read_file 深度验证 — 内容正确性、分页、批量、错误
# =============================================================================

class TestReadFileDeep:
    TMP = os.path.join(tempfile.gettempdir(), "deep_test.txt")

    @classmethod
    def setup_class(cls):
        with open(cls.TMP, "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3\nline4\nline5\n")

    def test_content_correct(self):
        res = get_result("read_file", {"file_paths": [self.TMP]})
        d = res["data"]
        assert d["success"] is True
        assert d["content"] == "line1\nline2\nline3\nline4\nline5\n"
        assert d["line_count"] == 5
        assert d["total_lines"] == 5

    def test_head_correct(self):
        d = result_data("read_file", {"file_paths": [self.TMP], "head": 2})
        assert d["content"] == "line1\nline2\n"
        assert d["line_count"] == 2

    def test_tail_correct(self):
        d = result_data("read_file", {"file_paths": [self.TMP], "tail": 1})
        assert d["content"] == "line5\n"

    def test_offset_limit_correct(self):
        d = result_data("read_file", {"file_paths": [self.TMP], "offset": 2, "limit": 2})
        assert d["content"] == "line2\nline3\n"

    def test_head_and_tail(self):
        d = result_data("read_file", {"file_paths": [self.TMP], "head": 3})
        assert d["line_count"] == 3
        assert "line1" in d["content"]
        assert "line4" not in d["content"]

    def test_batch_read(self):
        d = result_data("read_file", {"file_paths": [self.TMP, "G:/OmniAgentAs-desk/version.txt"], "head": 1})
        assert d["success"] is True
        assert "results" in d
        assert len(d["results"]) == 2
        assert d["success_count"] == 2
        assert d["failed_count"] == 0

    def test_nonexistent_file_error(self):
        res = get_result("read_file", {"file_paths": ["C:/nonexistent_deep_test_999.txt"]})
        assert res["status"] == "error" or res.get("code", "").startswith("ERR")
        assert res["data"]["success"] is False

    def test_encoding_utf8(self):
        tmp2 = self.TMP.replace(".txt", "_cn.txt")
        with open(tmp2, "w", encoding="utf-8") as f:
            f.write("中文内容测试\n第二行\n")
        d = result_data("read_file", {"file_paths": [tmp2]})
        assert "中文内容测试" in d["content"]
        assert d["line_count"] == 2


# =============================================================================
# 2. 时间工具链深度验证
# =============================================================================

class TestTimeToolsDeep:
    def test_get_time_fields(self):
        d = result_data("get_time", {})
        assert "iso" in d and d["iso"] != ""
        assert "timestamp" in d and isinstance(d["timestamp"], (int, float))
        assert "weekday" in d and d["weekday"] != ""
        assert "timezone" in d

    def test_get_time_iso_format(self):
        d = result_data("get_time", {})
        iso = d["iso"]
        assert "2026" in iso
        assert "T" in iso or " " in iso

    def test_time_add_days(self):
        d = result_data("time_add", {"delta": 1, "unit": "days", "start": "2026-01-01"})
        assert "result_time" in d
        assert "2026-01-02" in d["result_time"] or "01-02" in d["result_time"]

    def test_time_add_hours(self):
        d = result_data("time_add", {"delta": 2, "unit": "hours", "start": "2026-01-01T10:00:00"})
        assert "result_time" in d

    def test_time_diff_days(self):
        d = result_data("time_diff", {"start": "2026-01-01", "end": "2026-01-11"})
        assert d.get("days") == 10 or d.get("total_days") == 10

    def test_time_diff_same_day(self):
        d = result_data("time_diff", {"start": "2026-01-01", "end": "2026-01-01"})
        days = d.get("days", d.get("total_days", 0))
        assert days == 0

    def test_timezone_convert(self):
        d = result_data("timezone_convert", {"time_value": "2026-05-21 12:00:00", "direction": "local_to_utc", "tz": "Asia/Shanghai"})
        assert "result_time" in d or "converted" in d or "utc" in str(d).lower()

    def test_query_calendar_weekend(self):
        d = result_data("query_calendar", {"date": "2026-05-24", "check_type": "weekend"})
        assert d.get("is_weekend") is True or d.get("result") is True or "周末" in str(d)

    def test_query_calendar_workday(self):
        d = result_data("query_calendar", {"date": "2026-05-25", "check_type": "weekend"})
        assert d.get("is_weekend") is False or d.get("result") is False or "工作日" in str(d)


# =============================================================================
# 3. Shell工具深度验证
# =============================================================================

class TestShellToolsDeep:
    def test_echo_output(self):
        d = result_data("execute_shell_command", {"command": "echo verify_output_123", "timeout": 10000})
        assert "verify_output_123" in d.get("stdout", "")
        assert d.get("returncode") == 0

    def test_exit_code_nonzero(self):
        d = result_data("execute_shell_command", {"command": "exit 42", "timeout": 10000})
        assert d.get("returncode") == 42

    def test_stderr_capture(self):
        d = result_data("execute_shell_command", {"command": "python -c \"import sys; sys.stderr.write('err_msg\\n')\"", "timeout": 10000})
        assert "err_msg" in d.get("stderr", "")

    def test_find_command_python(self):
        d = result_data("find_command", {"command": "python"})
        assert d.get("available") is True
        assert "python" in d.get("path", "").lower()

    def test_find_command_nonexistent(self):
        d = result_data("find_command", {"command": "nonexistent_cmd_xyz_999"})
        assert d.get("available") is False

    def test_execute_python_output(self):
        d = result_data("execute_python", {"code": "print('py_output_ok')", "timeout": 10000})
        assert "py_output_ok" in d.get("stdout", "")
        assert d.get("returncode") == 0

    def test_execute_python_calculation(self):
        d = result_data("execute_python", {"code": "result = 6 * 7; print(result)", "timeout": 10000})
        assert "42" in d.get("stdout", "")


# =============================================================================
# 4. 系统工具深度验证
# =============================================================================

class TestSystemToolsDeep:
    def test_system_info_basic_fields(self):
        d = result_data("get_system_info", {})
        basic = d.get("basic", {})
        assert basic.get("platform") == "Windows"
        assert "python_version" in basic
        assert basic.get("hostname", "") != ""

    def test_system_info_cpu(self):
        d = result_data("get_system_info", {})
        cpu = d.get("cpu", {})
        assert cpu.get("physical_cores", 0) > 0
        assert 0 <= cpu.get("cpu_usage_percent", 0) <= 100

    def test_system_info_memory(self):
        d = result_data("get_system_info", {})
        mem = d.get("memory", {})
        assert mem.get("total_gb", 0) > 0
        assert 0 <= mem.get("percent", 0) <= 100

    def test_list_processes_python(self):
        d = result_data("list_processes", {"filter_name": "python", "max_results": 5})
        procs = d.get("processes", [])
        assert len(procs) > 0
        p = procs[0]
        assert p.get("pid", 0) > 0
        assert "python" in p.get("name", "").lower()

    def test_net_connections_8000(self):
        d = result_data("net_connections", {"filter_port": 8000})
        conns = d.get("connections", [])
        assert len(conns) > 0, "port 8000 should have connections (uvicorn is running)"

    def test_get_env_path(self):
        d = result_data("get_env", {"name": "PATH"})
        assert d.get("exists") is True
        assert len(d.get("value", "")) > 0

    def test_get_env_nonexistent(self):
        d = result_data("get_env", {"name": "NONEXISTENT_VAR_XYZ_999"})
        assert d.get("exists") is False


# =============================================================================
# 5. 文件搜索/内容搜索深度验证
# =============================================================================

class TestSearchDeep:
    def test_search_files_pattern(self):
        d = result_data("search_files", {"pattern": "*.py", "search_dir": "G:/OmniAgentAs-desk/backend/app", "max_depth": 1})
        assert d["success"] is True
        assert len(d["matches"]) >= 3
        names = [m["name"] for m in d["matches"]]
        assert "main.py" in names
        assert "config.py" in names

    def test_search_files_type_filter(self):
        d = result_data("search_files", {"pattern": "*", "search_dir": "G:/OmniAgentAs-desk/backend/app", "type": "file", "max_depth": 1})
        for m in d["matches"]:
            assert m["type"] == "file"

    def test_search_files_match_structure(self):
        d = result_data("search_files", {"pattern": "*.py", "search_dir": "G:/OmniAgentAs-desk/backend/app", "max_depth": 1})
        for m in d["matches"]:
            assert "name" in m
            assert "path" in m
            assert "type" in m
            assert "size" in m

    def test_grep_files_with_matches(self):
        d = result_data("grep_file_content", {"pattern": "class BaseAgent", "search_dir": "G:/OmniAgentAs-desk/backend/app/services/agent", "output_mode": "files_with_matches"})
        assert d["success"] is True
        assert len(d["matches"]) >= 1
        assert "base_react.py" in d["matches"][0].get("file", "")

    def test_grep_content_mode(self):
        d = result_data("grep_file_content", {"pattern": "parse_react_response", "search_dir": "G:/OmniAgentAs-desk/backend/app/services/agent", "output_mode": "content", "head_limit": 3})
        assert d["success"] is True
        if d["matches"]:
            m = d["matches"][0]
            assert "file" in m

    def test_grep_case_insensitive(self):
        d1 = result_data("grep_file_content", {"pattern": "fastapi", "search_dir": "G:/OmniAgentAs-desk/backend/app", "ignore_case": True, "output_mode": "files_with_matches"})
        d2 = result_data("grep_file_content", {"pattern": "fastapi", "search_dir": "G:/OmniAgentAs-desk/backend/app", "ignore_case": False, "output_mode": "files_with_matches"})
        assert len(d1.get("matches", [])) > 0, "ignore_case=True should find 'fastapi' (lowercase in code)"


# =============================================================================
# 6. 目录列表深度验证
# =============================================================================

class TestListDirectoryDeep:
    def test_list_mode(self):
        res = get_result("list_directory", {"dir_path": "G:/OmniAgentAs-desk/backend", "format": "list"})
        d = res["data"]
        assert d["success"] is True
        assert len(d["entries"]) > 0
        e = d["entries"][0]
        assert "name" in e and "type" in e

    def test_tree_mode(self):
        res = get_result("list_directory", {"dir_path": "G:/OmniAgentAs-desk/backend/app", "format": "tree", "max_depth": 1})
        d = res["data"]
        assert d["success"] is True
        assert "tree" in d

    def test_entries_have_correct_types(self):
        d = result_data("list_directory", {"dir_path": "G:/OmniAgentAs-desk", "format": "list"})
        types = {e["type"] for e in d["entries"]}
        assert "directory" in types or "file" in types


# =============================================================================
# 7. 网络工具深度验证
# =============================================================================

class TestNetworkDeep:
    def test_ping_localhost(self):
        d = result_data("network_diagnose", {"host": "127.0.0.1", "mode": "ping", "count": 2})
        assert d.get("is_reachable") is True
        assert d.get("packets_lost") == 0

    def test_port_8000_open(self):
        d = result_data("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 8000})
        assert d.get("is_open") is True

    def test_port_9999_closed(self):
        d = result_data("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 9999})
        assert d.get("is_open") is False


# =============================================================================
# 8. META工具深度验证
# =============================================================================

class TestMetaDeep:
    def test_tool_help_structure(self):
        d = result_data("tool_help", {"tool_name": "read_file"})
        assert d.get("name") == "read_file"
        assert "description" in d
        assert "params" in d
        assert "file_paths" in d["params"]

    def test_tool_help_all_major(self):
        for tool in ["read_file", "execute_shell_command", "get_time", "get_system_info", "search_web"]:
            d = result_data("tool_help", {"tool_name": tool})
            assert d.get("name") == tool, f"tool_help for {tool} returned wrong name"

    def test_tool_search_by_keyword(self):
        d = result_data("tool_search", {"query": "file"})
        tools = d.get("tools", d.get("matches", []))
        assert len(tools) > 0, "tool_search('file') should find file-related tools"

    def test_tool_search_by_chinese(self):
        d = result_data("tool_search", {"query": "文件"})
        tools = d.get("tools", d.get("matches", []))
        assert len(tools) > 0, "tool_search('文件') should find file-related tools (Chinese)"


# =============================================================================
# 9. data_file_format 深度验证
# =============================================================================

class TestDataFileFormatDeep:
    def test_read_json(self):
        tmp = os.path.join(tempfile.gettempdir(), "fmt_test.json")
        with open(tmp, "w") as f:
            json.dump({"key": "val", "num": 42}, f)
        res = get_result("data_file_format", {"file_path": tmp, "action": "read"})
        d = res["data"]
        assert d["success"] is True
        assert d["data"]["key"] == "val"
        assert d["data"]["num"] == 42

    def test_read_nonexistent(self):
        res = get_result("data_file_format", {"file_path": "C:/nonexistent_999.json", "action": "read"})
        d = res["data"]
        assert d.get("success") is False


# =============================================================================
# 10. 解析器链深度验证（Python层）
# =============================================================================

class TestParserDeep:
    def test_normalize_result_bool_not_int(self):
        assert _normalize_result_to_str(True) == "True"
        assert _normalize_result_to_str(1) == "1"
        assert _normalize_result_to_str(False) == "False"
        assert _normalize_result_to_str(0) == "0"

    def test_normalize_result_dict_order(self):
        r = _normalize_result_to_str({"a": 1, "b": 2})
        parsed = json.loads(r)
        assert parsed == {"a": 1, "b": 2}

    def test_normalize_result_list(self):
        r = _normalize_result_to_str([1, "two", 3.0])
        parsed = json.loads(r)
        assert parsed == [1, "two", 3.0]

    def test_parse_old_format_finish_all_types(self):
        for val, expected in [(42, "42"), (True, "True"), (3.14, "3.14"), ({"x": 1}, '{"x": 1}'), ([1, 2], "[1, 2]")]:
            r = parse_react_response(json.dumps({"action": "finish", "action_input": {"result": val}}))
            assert r["type"] == "answer", f"val={val!r} type={r['type']} response={r.get('response')}"
            assert isinstance(r["response"], str)

    def test_parse_new_format_finish_all_types(self):
        for val in [42, True, 3.14, {"x": 1}, [1, 2], "ok"]:
            r = parse_react_response({"tool_name": "finish", "tool_params": {"result": val}})
            assert r["type"] == "answer"
            assert isinstance(r["response"], str)

    def test_parse_mixed_text_finish_int(self):
        r = parse_react_response('done\n{"tool_name":"finish","tool_params":{"result":42}}')
        assert r["type"] == "answer"
        assert r["response"] == "42"

    def test_parse_filter_reasoning(self):
        r = parse_react_response({"tool_name": "search_web", "tool_params": {"query": "test", "reasoning": "internal"}})
        assert "reasoning" not in r.get("tool_params", {})

    def test_parse_empty_error(self):
        r = parse_react_response("")
        assert r["type"] == "parse_error"

    def test_parse_none_error(self):
        r = parse_react_response(None)
        assert r["type"] == "parse_error"


# =============================================================================
# 11. Agent/ReAct 端到端深度验证（SSE流内容检查）
# =============================================================================

class TestChatStreamDeep:
    def _collect_events(self, message, max_events=30):
        import uuid
        events = []
        try:
            with httpx.stream("POST", f"{BASE}/chat/stream/v2",
                json={"messages": [{"role": "user", "content": message}], "session_id": str(uuid.uuid4())},
                headers={"Content-Type": "application/json"}, timeout=120) as resp:
                buf = ""
                for chunk in resp.iter_text():
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        ds = line[5:].strip()
                        if ds == "[DONE]":
                            return events
                        try:
                            events.append(json.loads(ds))
                            if len(events) >= max_events:
                                return events
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return events

    def test_time_query_produces_thought_and_action(self):
        events = self._collect_events("现在几点了？")
        types = [e.get("type") or e.get("event") for e in events]
        valid_types = {"thought", "thinking", "action", "tool_call", "answer", "finish", "response", "start", "final", "observation", "step"}
        assert len(events) > 0, "Must produce SSE events"
        actual = set(types) - {None}
        assert len(actual & valid_types) > 0, f"Got unexpected event types: {actual}"

    def test_system_query_events(self):
        events = self._collect_events("查看系统CPU信息")
        assert len(events) > 0, "Must produce SSE events for system query"
